"""
Konfigurasi stealth browser bersama (Tier 2/3) dan solver Cloudflare.

Mengikuti pendekatan Scrapling v0.5: fingerprint diatur lewat flag native Chromium
(bukan patch JS yang terdeteksi via `Function.toString`), User-Agent disamakan dengan
versi Chromium yang benar-benar berjalan, dan challenge Cloudflare dibedakan per `cType`.
"""

import atexit
import json
import random
import re
import shutil
import sys
import tempfile
import threading
import time
import weakref
from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

FALLBACK_CHROME_MAJOR = 148
STEALTH_LOCALE = "zh-CN"
# Chromium penuh dalam mode headless baru. Tanpa channel, Playwright memakai
# chromium-headless-shell: plugins=0, window.chrome undefined, WebGL SwiftShader.
STEALTH_CHANNEL = "chromium"
_VIEWPORT = {"width": 1920, "height": 1080}

# (token UA, navigator.platform, platform Client Hints, platformVersion)
if sys.platform == "win32":
    _UA_PLATFORM, _NAV_PLATFORM, _CH_PLATFORM, _CH_PLATFORM_VERSION = (
        "Windows NT 10.0; Win64; x64", "Win32", "Windows", "10.0.0"
    )
elif sys.platform == "darwin":
    _UA_PLATFORM, _NAV_PLATFORM, _CH_PLATFORM, _CH_PLATFORM_VERSION = (
        "Macintosh; Intel Mac OS X 10_15_7", "MacIntel", "macOS", "10.15.7"
    )
else:
    _UA_PLATFORM, _NAV_PLATFORM, _CH_PLATFORM, _CH_PLATFORM_VERSION = (
        "X11; Linux x86_64", "Linux x86_64", "Linux", ""
    )

# Salinan `disabledFeatures` di chromiumSwitches Playwright/Patchright (dijaga tes drift).
# Chromium hanya memakai --disable-features TERAKHIR, dan args kita ditaruh setelah flag
# bawaan, jadi daftar ini harus ikut disebut ulang agar tidak aktif kembali.
PLAYWRIGHT_DEFAULT_DISABLED_FEATURES = (
    "AvoidUnnecessaryBeforeUnloadCheckSync",
    "BoundaryEventDispatchTracksNodeRemoval",
    "DestroyProfileOnBrowserClose",
    "DialMediaRouteProvider",
    "GlobalMediaControls",
    "HttpsUpgrades",
    "LensOverlay",
    "MediaRouter",
    "PaintHolding",
    "ThirdPartyStoragePartitioning",
    "Translate",
    "AutoDeElevate",
    "RenderDocument",
    "OptimizationHints",
    "msForceBrowserSignIn",
    "msEdgeUpdateLaunchServicesPreferredVersion",
)
# IsolateOrigins hanya berlaku di headless shell; Chromium penuh tetap memakai site isolation,
# sehingga iframe lintas-situs menjadi target OOPIF yang dijaga guard CDP lewat auto-attach
# (stealth_base, ADR-126).
_STEALTH_DISABLED_FEATURES = ("IsolateOrigins", "site-per-process")

# Subset aman dari STEALTH_ARGS Scrapling. Sengaja TANPA --enable-features dan hanya SATU
# --disable-features (gabungan daftar bawaan + milik kita).
_BASE_LAUNCH_ARGS = (
    "--disable-blink-features=AutomationControlled",
    "--disable-features=" + ",".join(PLAYWRIGHT_DEFAULT_DISABLED_FEATURES + _STEALTH_DISABLED_FEATURES),
    "--disable-infobars",
    "--no-first-run",
    "--no-default-browser-check",
    "--no-pings",
    "--password-store=basic",
    "--use-mock-keychain",
    "--disable-sync",
    "--disable-translate",
    "--disable-dev-shm-usage",
    "--mute-audio",
    "--hide-scrollbars",
    "--force-color-profile=srgb",
    "--blink-settings=primaryHoverType=2,availableHoverTypes=2,primaryPointerType=4,availablePointerTypes=4",
    # Noise canvas native, menggantikan patch toDataURL berbasis JS.
    "--fingerprinting-canvas-image-data-noise",
    # WebRTC tidak boleh membuka UDP di luar proxy: cegah bocor IP lokal dan jalan pintas
    # ke host internal yang tidak melewati egress proxy.
    "--webrtc-ip-handling-policy=disable_non_proxied_udp",
    "--force-webrtc-ip-handling-policy",
)

_PLAIN_PLAYWRIGHT_STEALTH_JS = """
try {
    Object.defineProperty(navigator, "webdriver", { get: () => undefined });
    window.chrome = window.chrome || { runtime: {}, loadTimes: function(){}, csi: function(){} };
} catch (e) {}
"""


def _needs_no_sandbox() -> bool:
    # Di Linux (terutama container: root, atau non-root tanpa user namespace) sandbox Chromium
    # sering tidak tersedia dan launch gagal. Di headless flag ini tidak terlihat dari JS.
    return sys.platform.startswith("linux")


def _accept_language(locale: str) -> str:
    base_lang = locale.split("-")[0].lower()
    return f"{locale},{base_lang}" if base_lang != locale.lower() else locale


def build_launch_args(locale: str = STEALTH_LOCALE) -> List[str]:
    args = list(_BASE_LAUNCH_ARGS)
    # Locale lewat flag (bukan override navigator.languages) agar Worker, Intl, dan header
    # Accept-Language konsisten.
    args += [f"--lang={locale}", f"--accept-lang={_accept_language(locale)}"]
    if _needs_no_sandbox():
        args.append("--no-sandbox")
    return args


# Browser hasil fallback ke headless shell; hanya mereka yang masih butuh override Client Hints.
_HEADLESS_SHELL_BROWSERS: "weakref.WeakSet[Any]" = weakref.WeakSet()


def launch_stealth_browser(pw: Any) -> Any:
    """Chromium penuh bila terpasang; headless shell hanya sebagai fallback agar scraping tetap jalan."""
    args = build_launch_args()
    try:
        return pw.chromium.launch(headless=True, channel=STEALTH_CHANNEL, args=args)
    except Exception as exc:
        print(f"⚠️ [Stealth] Chromium penuh tidak tersedia ({exc}); fallback ke headless shell.")
    browser = pw.chromium.launch(headless=True, args=args)
    _HEADLESS_SHELL_BROWSERS.add(browser)
    return browser


# --- Profil persisten -------------------------------------------------------------

PROFILE_DIR_PREFIX = "readomni-stealth-profile-"
_PROFILE_RMTREE_ATTEMPTS = 3
_PROFILE_RMTREE_DELAY_S = 0.2
_PROFILE_EXIT_RMTREE_ATTEMPTS = 10
# Sisa profil dari proses yang mati paksa (SIGKILL/taskkill, atexit tidak jalan). Context dibuang
# setelah CONTEXT_MAX_AGE_S (30 menit, stealth_base), jadi ambang 2 jam aman bagi proses lain yang
# masih hidup sekaligus membatasi berapa lama cookie (termasuk ghost) tertinggal di disk.
STALE_PROFILE_AGE_S = 2 * 3600.0
# Context hasil fallback ke headless shell (pasangan _HEADLESS_SHELL_BROWSERS untuk profil persisten).
_HEADLESS_SHELL_CONTEXTS: "weakref.WeakSet[Any]" = weakref.WeakSet()
_live_profile_dirs: Set[str] = set()
_pending_profile_removals: Set[str] = set()
_profile_dirs_lock = threading.Lock()
_stale_sweep_done = False


def read_driven_chromium_version(package_root: Union[str, Path]) -> Optional[str]:
    """Versi Chromium yang dikendalikan paket engine, dari driver/package/browsers.json (cara Scrapling)."""
    path = Path(package_root) / "driver" / "package" / "browsers.json"
    try:
        browsers = json.loads(path.read_text(encoding="utf-8")).get("browsers", [])
    except (OSError, ValueError, AttributeError):
        return None
    for entry in browsers:
        if not isinstance(entry, dict) or entry.get("name") != "chromium":
            continue
        version = entry.get("browserVersion")
        if isinstance(version, str) and re.match(r"\d+\.", version):
            return version
    return None


@lru_cache(maxsize=1)
def _driven_version() -> str:
    for package in ("patchright", "playwright"):
        spec = find_spec(package)
        if spec is not None and spec.origin:
            version = read_driven_chromium_version(Path(spec.origin).parent)
            if version:
                return version
    return f"{FALLBACK_CHROME_MAJOR}.0.0.0"


def _remove_profile_dir(profile_dir: str, attempts: int = _PROFILE_RMTREE_ATTEMPTS) -> None:
    # Windows bisa masih mengunci file sesaat setelah Chromium keluar.
    for attempt in range(attempts):
        try:
            shutil.rmtree(profile_dir)
            break
        except FileNotFoundError:
            break
        except OSError:
            if attempt + 1 < attempts:
                time.sleep(_PROFILE_RMTREE_DELAY_S)
    else:
        # Masih terkunci: dicoba lagi di launch berikutnya dan saat proses keluar.
        with _profile_dirs_lock:
            _pending_profile_removals.add(profile_dir)
        return
    with _profile_dirs_lock:
        _live_profile_dirs.discard(profile_dir)
        _pending_profile_removals.discard(profile_dir)


def _retry_pending_profile_removals() -> None:
    with _profile_dirs_lock:
        pending = list(_pending_profile_removals)
    for profile_dir in pending:
        _remove_profile_dir(profile_dir, attempts=1)


def sweep_stale_profile_dirs(base_dir: Optional[Union[str, Path]] = None, now: Optional[float] = None) -> None:
    """Hapus profil ber-prefix kita yang tidak dipakai proses ini dan sudah basi."""
    base = Path(base_dir or tempfile.gettempdir())
    cutoff = (time.time() if now is None else now) - STALE_PROFILE_AGE_S
    with _profile_dirs_lock:
        live = set(_live_profile_dirs)
    try:
        candidates = [d for d in base.iterdir() if d.name.startswith(PROFILE_DIR_PREFIX)]
    except OSError:
        return
    for profile_dir in candidates:
        try:
            if str(profile_dir) in live or not profile_dir.is_dir() or profile_dir.stat().st_mtime > cutoff:
                continue
        except OSError:
            continue
        shutil.rmtree(profile_dir, ignore_errors=True)


@atexit.register
def _sweep_profile_dirs() -> None:
    with _profile_dirs_lock:
        leftovers = list(_live_profile_dirs | _pending_profile_removals)
    for profile_dir in leftovers:
        # Chromium bisa masih keluar dan mengunci profil saat atexit jalan (Windows).
        _remove_profile_dir(profile_dir, attempts=_PROFILE_EXIT_RMTREE_ATTEMPTS)


class PersistentProfileLauncher:
    """
    Pengganti `Browser.new_context` dengan antarmuka yang sama (`version`, `new_context`):
    tiap context adalah `launch_persistent_context` dengan profil sementara sendiri.

    Context incognito dari `new_context` mudah dikenali: kuota storage kecil dan
    `navigator.languages` hanya berisi nilai `--lang`. Profil biasa tidak. Direktori profil
    dihapus saat context ditutup, jadi cookie (termasuk workspace ghost) tidak tertinggal di disk.
    """

    def __init__(self, pw: Any, executable_path: Optional[str] = None):
        self._pw = pw
        self._executable_path = executable_path
        self._contexts: "weakref.WeakSet[Any]" = weakref.WeakSet()
        # Launch gagal (mis. driver Playwright mati): pemilik thread-local mengganti launcher ini.
        self.broken = False
        # UA harus diset saat launch, sebelum ada objek Browser yang bisa ditanya versinya.
        self.version = _driven_version()
        global _stale_sweep_done
        if not _stale_sweep_done:
            _stale_sweep_done = True
            sweep_stale_profile_dirs()

    def _launch(self, profile_dir: str, options: Dict[str, Any], full_chromium: bool) -> Any:
        kwargs = dict(options, user_data_dir=profile_dir, headless=True, args=build_launch_args())
        if self._executable_path:
            kwargs["executable_path"] = self._executable_path
        elif full_chromium:
            kwargs["channel"] = STEALTH_CHANNEL
        return self._pw.chromium.launch_persistent_context(**kwargs)

    def new_context(self, **options: Any) -> Any:
        _retry_pending_profile_removals()
        profile_dir = tempfile.mkdtemp(prefix=PROFILE_DIR_PREFIX)
        with _profile_dirs_lock:
            _live_profile_dirs.add(profile_dir)
        try:
            try:
                context = self._launch(profile_dir, options, full_chromium=True)
            except Exception as exc:
                if self._executable_path:
                    raise
                print(f"⚠️ [Stealth] Chromium penuh tidak tersedia ({exc}); fallback ke headless shell.")
                context = self._launch(profile_dir, options, full_chromium=False)
                _HEADLESS_SHELL_CONTEXTS.add(context)
        except Exception:
            self.broken = True
            _remove_profile_dir(profile_dir)
            raise
        context.on("close", lambda _ctx: _remove_profile_dir(profile_dir))
        self._contexts.add(context)
        return context

    def close(self) -> None:
        for context in list(self._contexts):
            try:
                context.close()
            except Exception:
                pass


def _browser_full_version(browser: Any) -> str:
    version = getattr(browser, "version", None)
    if isinstance(version, str) and re.match(r"\d+\.", version):
        return version
    return f"{FALLBACK_CHROME_MAJOR}.0.0.0"


def _browser_major_version(browser: Any) -> int:
    return int(_browser_full_version(browser).split(".", 1)[0])


def build_context_options(browser: Any) -> Dict[str, Any]:
    """UA headless asli memuat 'HeadlessChrome'; ganti dengan UA yang versinya sama dengan Sec-CH-UA."""
    major = _browser_major_version(browser)
    return {
        "user_agent": (
            f"Mozilla/5.0 ({_UA_PLATFORM}) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"
        ),
        "viewport": dict(_VIEWPORT),
        "screen": dict(_VIEWPORT),
    }


def build_ua_metadata(browser: Any) -> Dict[str, Any]:
    """Client Hints seperti Chromium headful: tanpa brand 'HeadlessChrome'."""
    full = _browser_full_version(browser)
    major = full.split(".", 1)[0]
    brands = [("Chromium", major, full), ("Not/A)Brand", "99", "99.0.0.0")]
    return {
        "brands": [{"brand": b, "version": v} for b, v, _ in brands],
        "fullVersionList": [{"brand": b, "version": fv} for b, _, fv in brands],
        "fullVersion": full,
        "platform": _CH_PLATFORM,
        "platformVersion": _CH_PLATFORM_VERSION,
        "architecture": "x86",
        "bitness": "64",
        "model": "",
        "mobile": False,
        "wow64": False,
    }


def apply_client_hints(context: Any, page: Any, browser: Any, locale: str = STEALTH_LOCALE) -> None:
    """
    Hanya untuk headless shell: di sana opsi `user_agent` Playwright tidak menyentuh
    navigator.userAgentData / Sec-CH-UA, sehingga brand 'HeadlessChrome' bocor. Override per
    halaman via CDP, sebelum goto. Chromium penuh sudah bersih dan dibiarkan native: override
    di sana mengubah urutan brand GREASE dan membuat navigator.languages halaman != Worker.
    """
    if browser not in _HEADLESS_SHELL_BROWSERS and context not in _HEADLESS_SHELL_CONTEXTS:
        return
    try:
        cdp = context.new_cdp_session(page)
        cdp.send(
            "Emulation.setUserAgentOverride",
            {
                "userAgent": build_context_options(browser)["user_agent"],
                "acceptLanguage": _accept_language(locale),
                "platform": _NAV_PLATFORM,
                "userAgentMetadata": build_ua_metadata(browser),
            },
        )
    except Exception:
        pass  # Best effort: halaman tetap jalan dengan UA dari opsi context.


def is_patchright_object(obj: Any) -> bool:
    return type(obj).__module__.split(".", 1)[0] == "patchright"


def inject_stealth_scripts(context: Any) -> None:
    """Patchright sudah menambal kebocoran CDP di level driver; patch JS tambahan malah terdeteksi."""
    if is_patchright_object(context):
        return
    try:
        context.add_init_script(_PLAIN_PLAYWRIGHT_STEALTH_JS)
    except Exception:
        pass


# --- Cloudflare ----------------------------------------------------------------

CF_MAX_SOLVE_ATTEMPTS = 3
CF_RETRY_INTERVAL_S = 3.0
# Tunggu singkat (≈ satu interval polling) agar loop polling Tier 2/3 tidak molor; iframe yang
# belum terlihat dicoba lagi di poll berikutnya.
CF_IFRAME_VISIBLE_TIMEOUT_MS = 400
_CF_CTYPES = ("non-interactive", "managed", "interactive")
_CF_BLOCKING_MARKERS = (
    "Just a moment...",
    "cf-browser-verification",
    "Enable JavaScript and cookies to continue",
    "cf-chl-widget",
)
_CF_EMBEDDED_MARKER = "challenges.cloudflare.com/turnstile"
_CF_FRAME_HINTS = ("challenges.cloudflare.com", "turnstile", "cf-chl-widget")
_CF_IFRAME_SELECTORS = (
    "iframe[src*='challenges.cloudflare.com']",
    "iframe[src*='turnstile']",
    "#turnstile-wrapper iframe",
    ".cf-turnstile iframe",
    "#cf-turnstile",
    ".cf-turnstile",
)


def detect_cloudflare_type(raw_html: str) -> Optional[str]:
    """
    'non-interactive' | 'managed' | 'interactive' = halaman challenge penuh (memblokir).
    'embedded' = widget Turnstile di dalam halaman yang isinya sudah ada.
    """
    if not raw_html:
        return None
    for ctype in _CF_CTYPES:
        if f"cType: '{ctype}'" in raw_html:
            return ctype
    if any(m in raw_html for m in _CF_BLOCKING_MARKERS):
        return "managed"
    if _CF_EMBEDDED_MARKER in raw_html:
        return "embedded"
    return None


def is_cloudflare_challenge(raw_html: str) -> bool:
    return detect_cloudflare_type(raw_html) is not None


def _click_box(page: Any, box: Optional[dict]) -> bool:
    if not box or box.get("width", 0) <= 20 or box.get("height", 0) <= 20:
        return False
    # Offset checkbox Turnstile dari pojok kiri-atas widget (sama dengan Scrapling).
    x = box["x"] + random.randint(26, 28)
    y = box["y"] + random.randint(25, 27)
    page.mouse.click(x, y, delay=random.randint(100, 200))
    return True


def _wait_visible(element: Any) -> bool:
    try:
        element.wait_for_element_state("visible", timeout=CF_IFRAME_VISIBLE_TIMEOUT_MS)
        return True
    except Exception:
        return False


def try_solve_cloudflare_turnstile(page: Any, challenge_type: Optional[str] = None) -> bool:
    """True hanya bila klik benar-benar dikirim ke iframe/widget challenge yang terlihat."""
    if challenge_type == "non-interactive":
        return False  # Challenge JS selesai sendiri; klik justru mengganggu.
    try:
        for frame in getattr(page, "frames", []):
            frame_url = (getattr(frame, "url", "") or "").lower()
            if not any(k in frame_url for k in _CF_FRAME_HINTS):
                continue
            try:
                element = frame.frame_element()
                if not _wait_visible(element):
                    continue  # Masih dirender / tersembunyi: klik sekarang akan meleset.
                if _click_box(page, element.bounding_box()):
                    return True
            except Exception:
                continue
            try:
                frame.locator("input[type='checkbox']").first.click(timeout=1200, delay=random.randint(100, 200))
                return True
            except Exception:
                continue

        for iframe_sel in _CF_IFRAME_SELECTORS:
            try:
                el = page.query_selector(iframe_sel)
                if el and _wait_visible(el) and _click_box(page, el.bounding_box()):
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def new_cloudflare_state() -> Dict[str, Any]:
    return {"attempts": 0, "last_click": None, "embedded_done": False}


def cloudflare_poll_step(page: Any, raw_html: str, state: Dict[str, Any], *, solve: bool = True) -> bool:
    """
    Dipanggil tiap iterasi polling. True = challenge pemblokir masih ada, lanjut menunggu.
    Klik dibatasi CF_MAX_SOLVE_ATTEMPTS dan diberi jeda agar verifikasi yang sedang
    berjalan tidak di-reset oleh klik beruntun.
    """
    ctype = detect_cloudflare_type(raw_html)
    if ctype is None:
        return False
    if ctype == "embedded":
        if solve and not state["embedded_done"]:
            state["embedded_done"] = bool(try_solve_cloudflare_turnstile(page, challenge_type=ctype))
        return False
    if not solve or ctype == "non-interactive":
        return True

    now = time.monotonic()
    last = state["last_click"]
    if state["attempts"] < CF_MAX_SOLVE_ATTEMPTS and (last is None or now - last >= CF_RETRY_INTERVAL_S):
        # Hanya klik nyata yang dihitung: iframe yang belum muncul tidak menghabiskan jatah.
        if try_solve_cloudflare_turnstile(page, challenge_type=ctype):
            state["attempts"] += 1
            state["last_click"] = now
    return True
