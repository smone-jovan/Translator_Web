"""
Konfigurasi stealth browser bersama (Tier 2/3) dan solver Cloudflare.

Mengikuti pendekatan Scrapling v0.5: fingerprint diatur lewat flag native Chromium
(bukan patch JS yang terdeteksi via `Function.toString`), User-Agent disamakan dengan
versi Chromium yang benar-benar berjalan, dan challenge Cloudflare dibedakan per `cType`.
"""

import random
import re
import sys
import time
from typing import Any, Dict, List, Optional

FALLBACK_CHROME_MAJOR = 148
STEALTH_LOCALE = "zh-CN"
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

# Subset aman dari STEALTH_ARGS Scrapling. Sengaja TANPA --disable-features/--enable-features
# lain: Chromium hanya memakai kemunculan terakhir, dan flag IsolateOrigins di bawah wajib
# bertahan agar iframe lintas-situs tetap di target yang dijaga guard CDP SSRF (ADR-126).
_BASE_LAUNCH_ARGS = (
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
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
    Opsi `user_agent` Playwright tidak menyentuh navigator.userAgentData / header Sec-CH-UA,
    sehingga brand 'HeadlessChrome' tetap bocor. Override per halaman via CDP, sebelum goto.
    """
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


def try_solve_cloudflare_turnstile(page: Any, challenge_type: Optional[str] = None) -> bool:
    if challenge_type == "non-interactive":
        return False  # Challenge JS selesai sendiri; klik justru mengganggu.
    try:
        for frame in getattr(page, "frames", []):
            frame_url = (getattr(frame, "url", "") or "").lower()
            if not any(k in frame_url for k in _CF_FRAME_HINTS):
                continue
            try:
                if _click_box(page, frame.frame_element().bounding_box()):
                    return True
            except Exception:
                pass
            try:
                frame.locator("input[type='checkbox']").first.click(timeout=1200, delay=random.randint(100, 200))
                return True
            except Exception:
                continue

        for iframe_sel in _CF_IFRAME_SELECTORS:
            try:
                el = page.query_selector(iframe_sel)
                if el and _click_box(page, el.bounding_box()):
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
            state["embedded_done"] = True
            try_solve_cloudflare_turnstile(page, challenge_type=ctype)
        return False
    if not solve or ctype == "non-interactive":
        return True

    now = time.monotonic()
    last = state["last_click"]
    if state["attempts"] < CF_MAX_SOLVE_ATTEMPTS and (last is None or now - last >= CF_RETRY_INTERVAL_S):
        state["attempts"] += 1
        state["last_click"] = now
        try_solve_cloudflare_turnstile(page, challenge_type=ctype)
    return True
