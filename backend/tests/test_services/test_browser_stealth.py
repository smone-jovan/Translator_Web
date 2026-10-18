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


def test_apply_client_hints_sends_ua_override_with_metadata():
    browser = MagicMock()
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
    context = MagicMock()
    context.new_cdp_session.side_effect = RuntimeError("target closed")
    bs.apply_client_hints(context, MagicMock(), MagicMock())  # tidak boleh raise


def test_launch_args_use_native_fingerprint_flags():
    args = bs.build_launch_args()
    assert "--disable-blink-features=AutomationControlled" in args
    assert "--fingerprinting-canvas-image-data-noise" in args
    assert "--webrtc-ip-handling-policy=disable_non_proxied_udp" in args
    assert "--force-webrtc-ip-handling-policy" in args
    assert "--lang=zh-CN" in args


def test_launch_args_keep_site_isolation_off_for_ssrf_guard():
    """Iframe lintas-situs harus tetap di target halaman yang dijaga guard CDP (ADR-126)."""
    args = bs.build_launch_args()
    disable_features = [a for a in args if a.startswith("--disable-features=")]
    # Chromium hanya memakai --disable-features terakhir; jangan sampai ada yang menimpa.
    assert disable_features == ["--disable-features=IsolateOrigins,site-per-process"]
    assert not [a for a in args if a.startswith("--enable-features=")]


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
    solver = MagicMock()
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


def test_poll_step_embedded_widget_clicks_once_and_does_not_block(monkeypatch):
    _clock(monkeypatch)
    solver = MagicMock()
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
