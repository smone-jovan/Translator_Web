import json
import re
from unittest.mock import MagicMock

import pytest

import services.scrapers.browser_stealth as bs
from services.scrapers.adaptive_dom import _extract_domain


# --- Adaptive store key -------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("https://www.wuxiaworld.com/novel/1", "wuxiaworld.com"),
        ("www.wuxiaworld.com", "wuxiaworld.com"),
        ("https://web.example/ch/1", "web.example"),
        ("w.example", "w.example"),
    ],
)
def test_extract_domain_strips_only_www_prefix(raw, expected):
    assert _extract_domain(raw) == expected


# --- Fingerprint konsisten ----------------------------------------------------

def test_context_options_user_agent_matches_real_browser_version():
    browser = MagicMock()
    browser.version = "148.0.7778.96"
    opts = bs.build_context_options(browser)
    assert "Chrome/148.0.0.0" in opts["user_agent"]
    assert "Headless" not in opts["user_agent"]
    assert opts["screen"] == opts["viewport"]


def test_context_options_fall_back_when_version_unknown():
    browser = MagicMock()
    browser.version = MagicMock()  # bukan string
    opts = bs.build_context_options(browser)
    assert f"Chrome/{bs.FALLBACK_CHROME_MAJOR}.0.0.0" in opts["user_agent"]


def test_client_hints_drop_headless_brand_and_match_version():
    browser = MagicMock()
    browser.version = "148.0.7778.96"
    meta = bs.build_ua_metadata(browser)
    brands = {b["brand"]: b["version"] for b in meta["brands"]}
    assert "HeadlessChrome" not in brands
    assert brands["Chromium"] == "148"
    assert meta["fullVersion"] == "148.0.7778.96"
    assert all("Headless" not in b["brand"] for b in meta["fullVersionList"])


def _fake_pw(*, full_chromium_ok=True):
    pw = MagicMock()
    shell = MagicMock(name="headless-shell")
    full = MagicMock(name="full-chromium")

    def launch(**kwargs):
        if kwargs.get("channel") == "chromium":
            if not full_chromium_ok:
                raise RuntimeError("Executable doesn't exist at ...chromium-1223...")
            return full
        return shell

    pw.chromium.launch.side_effect = launch
    return pw, full, shell


def test_launch_uses_full_chromium_channel_with_stealth_args():
    """Tanpa channel, Playwright memakai chromium-headless-shell (plugins=0, tanpa window.chrome)."""
    pw, full, _ = _fake_pw()
    assert bs.launch_stealth_browser(pw) is full
    kwargs = pw.chromium.launch.call_args.kwargs
    assert kwargs["channel"] == "chromium"
    assert kwargs["headless"] is True
    assert kwargs["args"] == bs.build_launch_args()


def test_launch_falls_back_to_headless_shell_when_full_chromium_missing():
    pw, _, shell = _fake_pw(full_chromium_ok=False)
    assert bs.launch_stealth_browser(pw) is shell
    assert "channel" not in pw.chromium.launch.call_args.kwargs


def test_apply_client_hints_leaves_full_chromium_native():
    """Chromium penuh sudah bersih; override CDP malah membuat navigator.languages halaman != Worker."""
    pw, full, _ = _fake_pw()
    browser = bs.launch_stealth_browser(pw)
    context = MagicMock()
    bs.apply_client_hints(context, MagicMock(), browser)
    context.new_cdp_session.assert_not_called()


def test_apply_client_hints_sends_ua_override_with_metadata():
    pw, _, browser = _fake_pw(full_chromium_ok=False)
    bs.launch_stealth_browser(pw)  # headless shell: brand 'HeadlessChrome' harus diganti
    browser.version = "148.0.7778.96"
    context, page, cdp = MagicMock(), MagicMock(), MagicMock()
    context.new_cdp_session.return_value = cdp

    bs.apply_client_hints(context, page, browser)

    method, params = cdp.send.call_args.args
    assert method == "Emulation.setUserAgentOverride"
    assert params["userAgent"] == bs.build_context_options(browser)["user_agent"]
    assert params["acceptLanguage"] == "zh-CN,zh"
    assert "HeadlessChrome" not in str(params["userAgentMetadata"])


def test_apply_client_hints_is_best_effort():
    pw, _, browser = _fake_pw(full_chromium_ok=False)
    bs.launch_stealth_browser(pw)
    context = MagicMock()
    context.new_cdp_session.side_effect = RuntimeError("target closed")
    bs.apply_client_hints(context, MagicMock(), browser)  # tidak boleh raise
    context.new_cdp_session.assert_called_once()


def test_launch_args_use_native_fingerprint_flags():
    args = bs.build_launch_args()
    assert "--disable-blink-features=AutomationControlled" in args
    assert "--fingerprinting-canvas-image-data-noise" in args
    assert "--webrtc-ip-handling-policy=disable_non_proxied_udp" in args
    assert "--force-webrtc-ip-handling-policy" in args
    assert "--lang=zh-CN" in args


def _disabled_features(args):
    flags = [a for a in args if a.startswith("--disable-features=")]
    # Chromium hanya memakai --disable-features terakhir; jangan sampai ada yang menimpa.
    assert len(flags) == 1
    return flags[0].split("=", 1)[1].split(",")


def test_launch_args_keep_site_isolation_off_for_ssrf_guard():
    """Di headless shell iframe lintas-situs tetap di target halaman (Chromium penuh: lihat guard OOPIF)."""
    args = bs.build_launch_args()
    features = _disabled_features(args)
    assert {"IsolateOrigins", "site-per-process"} <= set(features)
    assert not [a for a in args if a.startswith("--enable-features=")]


def test_launch_args_keep_playwright_default_disabled_features():
    # Flag kita ditaruh SETELAH --disable-features bawaan Patchright dan menang; tanpa daftar
    # bawaan, ThirdPartyStoragePartitioning/RenderDocument/PaintHolding dkk. aktif kembali.
    features = _disabled_features(bs.build_launch_args())
    assert {"ThirdPartyStoragePartitioning", "RenderDocument", "PaintHolding", "Translate",
            "OptimizationHints", "HttpsUpgrades"} <= set(features)
    assert len(features) == len(set(features))


def test_playwright_default_disabled_features_match_installed_driver():
    """Deteksi drift saat Patchright di-upgrade: daftar salinan harus sama dengan driver terpasang."""
    patchright = pytest.importorskip("patchright")
    from pathlib import Path

    bundle = Path(patchright.__file__).parent / "driver" / "package" / "lib" / "coreBundle.js"
    if not bundle.is_file():
        pytest.skip("coreBundle.js Patchright tidak ditemukan")
    source = bundle.read_text(encoding="utf-8")
    match = re.search(r"disabledFeatures = \[(.*?)\]\.filter", source, re.S)
    assert match, "struktur chromiumSwitches Patchright berubah"
    installed = re.findall(r'^\s*"([^"]+)",?\s*$', match.group(1), re.M)
    assert list(bs.PLAYWRIGHT_DEFAULT_DISABLED_FEATURES) == installed


@pytest.mark.parametrize("platform, expected", [("linux", True), ("win32", False), ("darwin", False)])
def test_launch_args_disable_sandbox_only_on_linux(monkeypatch, platform, expected):
    monkeypatch.setattr(bs.sys, "platform", platform)
    assert ("--no-sandbox" in bs.build_launch_args()) is expected


def test_js_stealth_skipped_for_patchright_context(monkeypatch):
    context = MagicMock()
    monkeypatch.setattr(bs, "is_patchright_object", lambda obj: True)
    bs.inject_stealth_scripts(context)
    context.add_init_script.assert_not_called()


def test_js_stealth_for_plain_playwright_has_no_detectable_canvas_or_webrtc_patch(monkeypatch):
    context = MagicMock()
    monkeypatch.setattr(bs, "is_patchright_object", lambda obj: False)
    bs.inject_stealth_scripts(context)
    script = context.add_init_script.call_args.args[0]
    assert "webdriver" in script
    assert "toDataURL" not in script
    assert "RTCPeerConnection" not in script


def test_is_patchright_object_reads_module_name():
    class Fake:
        pass

    Fake.__module__ = "patchright._impl._browser_context"
    assert bs.is_patchright_object(Fake()) is True
    assert bs.is_patchright_object(MagicMock()) is False


# --- Deteksi & solver Cloudflare ---------------------------------------------

@pytest.mark.parametrize(
    "html, expected",
    [
        ("<script>window._cf_chl_opt={cType: 'non-interactive'}</script>", "non-interactive"),
        ("<script>window._cf_chl_opt={cType: 'managed'}</script>", "managed"),
        ("<script>window._cf_chl_opt={cType: 'interactive'}</script>", "interactive"),
        ("<html><title>Just a moment...</title></html>", "managed"),
        ("<div class='cf-browser-verification'></div>", "managed"),
        ("<p>isi</p><script src='https://challenges.cloudflare.com/turnstile/v0/api.js'></script>", "embedded"),
        ("<html><body>Normal Chapter Content</body></html>", None),
        ("", None),
    ],
)
def test_detect_cloudflare_type(html, expected):
    assert bs.detect_cloudflare_type(html) == expected


def test_is_cloudflare_challenge_stays_boolean_superset():
    assert bs.is_cloudflare_challenge("<html><title>Just a moment...</title></html>") is True
    assert bs.is_cloudflare_challenge("<script>{cType: 'managed'}</script>") is True
    assert bs.is_cloudflare_challenge("<html><body>ok</body></html>") is False


def _clock(monkeypatch, start=1000.0):
    now = {"t": start}
    monkeypatch.setattr(bs.time, "monotonic", lambda: now["t"])
    return now


def test_poll_step_waits_without_clicking_on_non_interactive(monkeypatch):
    _clock(monkeypatch)
    solver = MagicMock()
    monkeypatch.setattr(bs, "try_solve_cloudflare_turnstile", solver)
    state = bs.new_cloudflare_state()
    assert bs.cloudflare_poll_step(MagicMock(), "{cType: 'non-interactive'}", state) is True
    solver.assert_not_called()


def test_poll_step_caps_solve_attempts_and_spaces_them(monkeypatch):
    now = _clock(monkeypatch)
    solver = MagicMock(return_value=True)
    monkeypatch.setattr(bs, "try_solve_cloudflare_turnstile", solver)
    state = bs.new_cloudflare_state()
    page = MagicMock()
    html = "{cType: 'managed'}"

    assert bs.cloudflare_poll_step(page, html, state) is True
    assert bs.cloudflare_poll_step(page, html, state) is True  # terlalu cepat, tidak klik lagi
    assert solver.call_count == 1
    for _ in range(10):
        now["t"] += bs.CF_RETRY_INTERVAL_S
        assert bs.cloudflare_poll_step(page, html, state) is True
    assert solver.call_count == bs.CF_MAX_SOLVE_ATTEMPTS


def test_poll_step_counts_only_real_clicks_and_retries_until_iframe_appears(monkeypatch):
    _clock(monkeypatch)
    clicked = iter([False, False, True])  # iframe challenge belum muncul dua kali
    solver = MagicMock(side_effect=lambda *a, **k: next(clicked))
    monkeypatch.setattr(bs, "try_solve_cloudflare_turnstile", solver)
    state = bs.new_cloudflare_state()

    for _ in range(3):  # tanpa jeda CF_RETRY_INTERVAL_S: tidak ada klik yang perlu ditunggu
        assert bs.cloudflare_poll_step(MagicMock(), "{cType: 'managed'}", state) is True
    assert solver.call_count == 3
    assert state["attempts"] == 1


def test_poll_step_embedded_widget_retries_until_clicked(monkeypatch):
    _clock(monkeypatch)
    clicked = iter([False, True])
    solver = MagicMock(side_effect=lambda *a, **k: next(clicked))
    monkeypatch.setattr(bs, "try_solve_cloudflare_turnstile", solver)
    state = bs.new_cloudflare_state()
    html = "<p>isi</p><script src='https://challenges.cloudflare.com/turnstile/v0/api.js'></script>"
    for _ in range(3):
        assert bs.cloudflare_poll_step(MagicMock(), html, state) is False
    assert solver.call_count == 2


def _cf_frame(box=None, visible=True):
    frame = MagicMock()
    frame.url = "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/turnstile/if/ov2"
    element = frame.frame_element.return_value
    element.bounding_box.return_value = box or {"x": 100.0, "y": 200.0, "width": 300.0, "height": 65.0}
    if not visible:
        element.wait_for_element_state.side_effect = TimeoutError("element is not visible")
    return frame, element


def test_solver_waits_for_challenge_iframe_to_be_visible_before_clicking():
    frame, element = _cf_frame()
    page = MagicMock()
    page.frames = [frame]
    order = []
    element.wait_for_element_state.side_effect = lambda state, **k: order.append(("wait", state))
    page.mouse.click.side_effect = lambda *a, **k: order.append(("click",))

    assert bs.try_solve_cloudflare_turnstile(page, challenge_type="managed") is True
    assert order == [("wait", "visible"), ("click",)]


def test_solver_does_not_click_hidden_challenge_iframe():
    frame, _ = _cf_frame(visible=False)
    page = MagicMock()
    page.frames = [frame]
    page.query_selector.return_value = None

    assert bs.try_solve_cloudflare_turnstile(page, challenge_type="managed") is False
    page.mouse.click.assert_not_called()
    frame.locator.assert_not_called()


def test_solver_reports_no_click_when_challenge_iframe_absent():
    page = MagicMock()
    page.frames = []
    page.query_selector.return_value = None
    assert bs.try_solve_cloudflare_turnstile(page, challenge_type="managed") is False
    page.mouse.click.assert_not_called()


def test_poll_step_embedded_widget_clicks_once_and_does_not_block(monkeypatch):
    _clock(monkeypatch)
    solver = MagicMock(return_value=True)
    monkeypatch.setattr(bs, "try_solve_cloudflare_turnstile", solver)
    state = bs.new_cloudflare_state()
    html = "<p>isi</p><script src='https://challenges.cloudflare.com/turnstile/v0/api.js'></script>"
    assert bs.cloudflare_poll_step(MagicMock(), html, state) is False
    assert bs.cloudflare_poll_step(MagicMock(), html, state) is False
    assert solver.call_count == 1


def test_poll_step_without_solve_never_clicks(monkeypatch):
    _clock(monkeypatch)
    solver = MagicMock()
    monkeypatch.setattr(bs, "try_solve_cloudflare_turnstile", solver)
    state = bs.new_cloudflare_state()
    assert bs.cloudflare_poll_step(MagicMock(), "{cType: 'managed'}", state, solve=False) is True
    solver.assert_not_called()


def test_solver_clicks_challenge_iframe_at_checkbox_offset():
    frame = MagicMock()
    frame.url = "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/turnstile/if/ov2"
    frame.frame_element.return_value.bounding_box.return_value = {"x": 100.0, "y": 200.0, "width": 300.0, "height": 65.0}
    page = MagicMock()
    page.frames = [frame]

    assert bs.try_solve_cloudflare_turnstile(page, challenge_type="managed") is True
    x, y = page.mouse.click.call_args.args
    assert 126 <= x <= 128 and 225 <= y <= 227


def test_native_fetch_uses_consistent_fingerprint_and_google_referer(monkeypatch):
    import services.scrapers.stealth_base as sb

    class _Proxy:
        server_url = "http://127.0.0.1:9"
        handled = 0
        blocked = 0

    proxy = _Proxy()
    page = MagicMock()
    page.url = "https://public.example/x"
    page.content.return_value = "<html><body>ok</body></html>"

    def goto(*a, **k):
        proxy.handled += 1
        return MagicMock(status=200)

    page.goto.side_effect = goto
    context = MagicMock()
    context.new_page.return_value = page
    browser = MagicMock()
    browser.version = "148.0.7778.96"
    browser.new_context.return_value = context
    monkeypatch.setattr(sb, "_get_thread_browser", lambda: browser)
    monkeypatch.setattr(sb, "get_egress_proxy", lambda: proxy)

    sb.StealthyNovelAdapter()._fetch_playwright_sync("https://public.example/x", disable_resources=False)

    ctx_kwargs = browser.new_context.call_args.kwargs
    assert "Chrome/148.0.0.0" in ctx_kwargs["user_agent"]
    assert ctx_kwargs["screen"] == ctx_kwargs["viewport"]
    assert ctx_kwargs["service_workers"] == "block"
    assert page.goto.call_args.kwargs.get("referer") == "https://www.google.com/"


def test_solver_does_not_click_non_interactive():
    page = MagicMock()
    page.frames = []
    assert bs.try_solve_cloudflare_turnstile(page, challenge_type="non-interactive") is False
    page.mouse.click.assert_not_called()


def test_thread_browser_launches_full_chromium(monkeypatch):
    import threading

    import patchright.sync_api as patchright_api
    import services.scrapers.novalpie as nv

    pw, full, _ = _fake_pw()
    monkeypatch.setattr(patchright_api, "sync_playwright", lambda: MagicMock(start=lambda: pw))
    got = {}
    t = threading.Thread(target=lambda: got.setdefault("browser", nv._get_thread_browser()))
    t.start()
    t.join()
    with nv._browsers_lock:
        nv._all_active_browsers.remove((pw, got["browser"]))

    assert got["browser"] is full
    assert pw.chromium.launch.call_args.kwargs["channel"] == "chromium"


# --- Browser sungguhan (dilewati bila Chromium penuh tidak tersedia) ----------

_PROBE_HTML = """<html><body><script>
(async () => {
  const w = new Worker(URL.createObjectURL(new Blob(['postMessage(navigator.languages)'])));
  const workerLanguages = await new Promise(r => { w.onmessage = e => r(e.data); });
  return {
    plugins: navigator.plugins.length,
    chrome: typeof window.chrome,
    brands: navigator.userAgentData.brands.map(b => b.brand),
    ua: navigator.userAgent,
    languages: navigator.languages,
    workerLanguages,
  };
})().then(r => { document.body.dataset.probe = JSON.stringify(r); });
</script></body></html>"""


def test_real_browser_fingerprint_matches_headful_chromium():
    try:
        from patchright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover
        from playwright.sync_api import sync_playwright
    launch = bs.launch_stealth_browser
    pw = sync_playwright().start()
    try:
        try:
            browser = launch(pw)
        except Exception as exc:  # pragma: no cover - Chromium belum terpasang
            pytest.skip(f"Chromium tidak bisa dijalankan: {exc}")
        if browser in bs._HEADLESS_SHELL_BROWSERS:  # pragma: no cover
            browser.close()
            pytest.skip("Chromium penuh (channel='chromium') tidak terpasang")
        try:
            context = browser.new_context(**bs.build_context_options(browser))
            # Tanpa DNS/jaringan: dokumen dilayani route. https karena userAgentData hanya ada di secure context.
            context.route("https://probe.test/**", lambda route: route.fulfill(status=200, content_type="text/html", body=_PROBE_HTML))
            page = context.new_page()
            bs.apply_client_hints(context, page, browser)
            page.goto("https://probe.test/")
            # Lewat DOM, bukan evaluate: Patchright mengevaluasi di isolated world.
            result = json.loads(page.wait_for_selector("body[data-probe]").get_attribute("data-probe"))
        finally:
            browser.close()
    finally:
        pw.stop()

    assert result["plugins"] > 0
    assert result["chrome"] == "object"
    assert not [b for b in result["brands"] if "Headless" in b]
    assert "Headless" not in result["ua"]
    assert result["languages"] == result["workerLanguages"]
