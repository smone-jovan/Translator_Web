"""
SSRF lewat hop redirect di Tier 1b (curl_cffi) dan Tier 3 (Playwright native).

ADR-120 mencatat bahwa hanya URL akhir yang divalidasi, sehingga hop perantara ke host
internal tetap diminta (blind SSRF). Tes ini memastikan setiap hop divalidasi SEBELUM
request dikirim (ADR-126).
"""

import http.server
import os
import socket
import socketserver
import sys
import threading
import types
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse

import pytest
from fastapi import HTTPException

PUBLIC_IP = "104.21.5.10"


@pytest.fixture(autouse=True)
def _fresh_context_cache():
    import services.scrapers.stealth_base as sb

    sb.close_thread_contexts()
    yield
    sb.close_thread_contexts()


def _dns(mapping: dict):
    def fake(host, port, *a, **k):
        name = host.decode() if isinstance(host, bytes) else host
        ip = mapping.get(name, PUBLIC_IP)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 0))]
    return fake


class _Resp:
    def __init__(self, status_code=200, text="", headers=None, url=""):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.url = url


# --- helper redirect manual -----------------------------------------------------

@pytest.mark.asyncio
async def test_follow_redirects_safely_blocks_private_hop_before_requesting_it(monkeypatch):
    from services.security import follow_redirects_safely

    monkeypatch.setattr(socket, "getaddrinfo", _dns({"internal.example": "10.0.0.5"}))
    requested = []

    async def get(url):
        requested.append(url)
        if url == "https://public.example/start":
            return _Resp(302, headers={"location": "http://internal.example/admin"}, url=url)
        return _Resp(200, "secret", url=url)

    with pytest.raises(HTTPException) as exc:
        await follow_redirects_safely(get, "https://public.example/start")
    assert exc.value.status_code == 400
    assert requested == ["https://public.example/start"]


@pytest.mark.asyncio
async def test_follow_redirects_safely_follows_public_relative_chain():
    from services.security import follow_redirects_safely

    async def get(url):
        if url.endswith("/a"):
            return _Resp(301, headers={"Location": "/b"}, url=url)
        if url.endswith("/b"):
            return _Resp(307, headers={"location": "https://cdn.example/c"}, url=url)
        return _Resp(200, "ok", url=url)

    resp, final_url = await follow_redirects_safely(get, "https://public.example/a")
    assert resp.text == "ok"
    assert final_url == "https://cdn.example/c"


@pytest.mark.asyncio
async def test_follow_redirects_safely_caps_hops():
    from services.security import TooManyRedirects, follow_redirects_safely

    async def get(url):
        return _Resp(302, headers={"location": url + "x"}, url=url)

    with pytest.raises(TooManyRedirects):
        await follow_redirects_safely(get, "https://public.example/loop", max_redirects=5)


# --- Tier 1b: fetch_html_adaptive + curl_cffi --------------------------------------

def _install_fake_curl(monkeypatch, responder):
    calls = []

    class FakeSession:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url, **kwargs):
            calls.append(("get", url, kwargs))
            return responder(url)

    mod = types.ModuleType("curl_cffi.requests")
    mod.AsyncSession = FakeSession
    pkg = types.ModuleType("curl_cffi")
    pkg.requests = mod
    monkeypatch.setitem(sys.modules, "curl_cffi", pkg)
    monkeypatch.setitem(sys.modules, "curl_cffi.requests", mod)
    return calls


def _challenge_resp():
    r = MagicMock()
    r.status_code = 200
    r.text = "<html><title>Just a moment...</title><div class='cf-browser-verification'></div></html>"
    r.url = "https://public.example/ch/1"
    r.raise_for_status = lambda: None
    return r


@pytest.mark.asyncio
async def test_tier1b_never_requests_private_redirect_hop(monkeypatch):
    from routers.scrape import fetch_html_adaptive

    monkeypatch.setattr(socket, "getaddrinfo", _dns({"internal.example": "10.0.0.5"}))

    def responder(url):
        if url == "https://public.example/ch/1":
            return _Resp(302, headers={"location": "http://internal.example/admin"}, url=url)
        return _Resp(200, "<html><body><article><p>internal secret</p></article></body></html>", url=url)

    calls = _install_fake_curl(monkeypatch, responder)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_challenge_resp()):
        with pytest.raises(HTTPException) as exc:
            await fetch_html_adaptive("https://public.example/ch/1", allow_playwright_fallback=False)
    assert exc.value.status_code == 400

    gets = [c for c in calls if c[0] == "get"]
    assert [g[1] for g in gets] == ["https://public.example/ch/1"]
    for kind, *rest in calls:
        kwargs = rest[-1]
        assert kwargs.get("allow_redirects") is False, f"{kind} must disable automatic redirects"


@pytest.mark.asyncio
async def test_tier1b_follows_validated_redirect_to_content(monkeypatch):
    from routers.scrape import fetch_html_adaptive

    body = "<html><head><title>Bab 1</title></head><body><article>" + "<p>Isi bab yang cukup panjang.</p>" * 10 + "</article></body></html>"

    def responder(url):
        if url == "https://public.example/ch/1":
            return _Resp(301, headers={"location": "/ch/1-new"}, url=url)
        return _Resp(200, body, url=url)

    _install_fake_curl(monkeypatch, responder)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_challenge_resp()):
        html, final_url = await fetch_html_adaptive("https://public.example/ch/1", allow_playwright_fallback=False)
    assert "Isi bab" in html
    assert final_url == "https://public.example/ch/1-new"


# --- Tier 3: Playwright native -----------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_html_adaptive_requests_strict_ssrf_from_tier3(monkeypatch):
    from routers.scrape import fetch_html_adaptive
    from services.scrapers.stealth_base import StealthyNovelAdapter

    _install_fake_curl(monkeypatch, lambda url: _Resp(403, "", url=url))
    page = MagicMock()
    page.html = "<html><title>Bab</title><article>" + "<p>Konten setelah Turnstile.</p>" * 5 + "</article></html>"
    page.url = "https://public.example/ch/1"
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_challenge_resp()):
        with patch.object(StealthyNovelAdapter, "fetch_stealth_page", new_callable=AsyncMock, return_value=page) as pw:
            await fetch_html_adaptive("https://public.example/ch/1", workspace="main")
    assert pw.call_args.kwargs.get("strict_ssrf") is True


@pytest.mark.asyncio
async def test_strict_ssrf_bypasses_scrapling_for_guarded_native_path(monkeypatch):
    import services.scrapers.stealth_base as sb

    fake_fetcher = MagicMock()
    fake_fetcher.async_fetch = AsyncMock(return_value="scrapling-page")
    monkeypatch.setattr(sb, "HAS_SCRAPLING", True)
    monkeypatch.setattr(sb, "StealthyFetcher", fake_fetcher, raising=False)
    native = MagicMock(return_value="native-page")
    monkeypatch.setattr(sb.StealthyNovelAdapter, "_fetch_playwright_sync", lambda self, url, **kw: native(url, **kw))

    adapter = sb.StealthyNovelAdapter(workspace="main")
    assert await adapter.fetch_stealth_page("https://public.example/x", strict_ssrf=True) == "native-page"
    fake_fetcher.async_fetch.assert_not_called()

    # Pemanggil lain (adapter situs tetap) masih boleh memakai Scrapling.
    assert await adapter.fetch_stealth_page("https://public.example/x") == "scrapling-page"


class _FakeProxy:
    server_url = "http://127.0.0.1:9"

    def __init__(self):
        self.handled = 0
        self.blocked = 0


def _mock_browser(monkeypatch, *, cdp_send=None, goto=None, proxy=None):
    import services.scrapers.stealth_base as sb

    cdp = MagicMock()
    if cdp_send:
        cdp.send.side_effect = cdp_send
    page = MagicMock()
    page.url = "https://public.example/x"
    page.content.return_value = "<html><body>ok</body></html>"
    if goto:
        page.goto.side_effect = goto
    context = MagicMock()
    context.new_page.return_value = page
    context.new_cdp_session.return_value = cdp
    browser = MagicMock()
    browser.new_context.return_value = context
    monkeypatch.setattr(sb, "_get_thread_browser", lambda: browser)
    proxy = proxy or _FakeProxy()
    monkeypatch.setattr(sb, "get_egress_proxy", lambda: proxy)
    return sb, browser, context, page, cdp, proxy


def test_native_fetch_installs_guard_and_proxy_before_navigation(monkeypatch):
    order = []
    proxy = _FakeProxy()

    def goto(*a, **k):
        order.append(("goto", a[0]))
        proxy.handled += 1  # browser benar-benar lewat proxy
        return MagicMock(status=200)

    sb, browser, *_ = _mock_browser(
        monkeypatch, cdp_send=lambda method, params=None: order.append(("cdp", method)), goto=goto, proxy=proxy
    )
    sb.StealthyNovelAdapter()._fetch_playwright_sync("https://public.example/x", disable_resources=False)

    kwargs = browser.new_context.call_args.kwargs
    assert kwargs.get("service_workers") == "block"
    assert kwargs.get("proxy", {}).get("server") == proxy.server_url
    assert "<-loopback>" in kwargs["proxy"].get("bypass", "")
    assert ("cdp", "Fetch.enable") in order
    assert order.index(("cdp", "Fetch.enable")) < order.index(("goto", "https://public.example/x"))


def test_native_fetch_fails_closed_when_proxy_was_not_used(monkeypatch):
    sb, *_ = _mock_browser(monkeypatch, goto=lambda *a, **k: MagicMock(status=200))
    with pytest.raises(RuntimeError, match="proxy"):
        sb.StealthyNovelAdapter()._fetch_playwright_sync("https://public.example/x", disable_resources=False)


def test_native_fetch_fails_closed_when_guard_cannot_be_installed(monkeypatch):
    sb, _, context, page, _, _ = _mock_browser(monkeypatch)
    context.new_cdp_session.side_effect = RuntimeError("CDP not supported")

    with pytest.raises(Exception):
        sb.StealthyNovelAdapter()._fetch_playwright_sync("https://public.example/x")
    page.goto.assert_not_called()


# --- Cache context per (workspace, domain): cookie cf_clearance bertahan antar bab ----

def _cache_browser(monkeypatch, proxy=None):
    """Browser palsu yang membuat context baru tiap new_context; tiap context mencatat halamannya."""
    import services.scrapers.stealth_base as sb

    proxy = proxy or _FakeProxy()
    created = []
    behavior = {"goto_error": None, "uses_proxy": True}

    def make_context(**kwargs):
        context = MagicMock()
        context.options = kwargs
        context.pages = []

        def new_page():
            page = MagicMock()
            page.content.return_value = "<html><body>ok</body></html>"

            def goto(url, **kw):
                if behavior["goto_error"]:
                    raise behavior["goto_error"]
                page.url = url
                if behavior["uses_proxy"]:
                    proxy.handled += 1
                return MagicMock(status=200, headers={})

            page.goto.side_effect = goto
            context.pages.append(page)
            return page

        context.new_page.side_effect = new_page
        created.append(context)
        return context

    browser = MagicMock()
    browser.new_context.side_effect = make_context
    monkeypatch.setattr(sb, "_get_thread_browser", lambda: browser)
    monkeypatch.setattr(sb, "get_egress_proxy", lambda: proxy)
    return sb, browser, proxy, created, behavior


def _fetch(sb, url="https://novel.example/ch1", workspace="main"):
    return sb.StealthyNovelAdapter(workspace=workspace)._fetch_playwright_sync(
        url, solve_cloudflare=False, disable_resources=False
    )


def test_native_fetch_reuses_context_for_same_workspace_and_domain(monkeypatch):
    sb, browser, proxy, created, _ = _cache_browser(monkeypatch)

    _fetch(sb, "https://novel.example/ch1")
    _fetch(sb, "https://NOVEL.example/ch2")

    assert len(created) == 1
    context = created[0]
    assert context.options["proxy"]["server"] == proxy.server_url  # proxy per context
    assert context.new_page.call_count == 2
    assert context.new_cdp_session.call_count == 2  # guard SSRF dipasang per halaman baru
    assert all(page.close.called for page in context.pages)
    context.close.assert_not_called()


def test_native_fetch_closes_leftover_popups_after_each_fetch(monkeypatch):
    sb, _, _, created, _ = _cache_browser(monkeypatch)
    _fetch(sb)
    popup = MagicMock()
    created[0].pages.append(popup)  # mis. window.open() dari halaman sebelumnya

    _fetch(sb, "https://novel.example/ch2")
    popup.close.assert_called()


def test_native_fetch_never_shares_context_across_workspaces(monkeypatch):
    sb, _, _, created, _ = _cache_browser(monkeypatch)

    _fetch(sb, workspace="main")
    _fetch(sb, workspace="ghost")
    _fetch(sb, workspace="main")

    assert len(created) == 2
    assert created[0].new_page.call_count == 2
    assert created[1].new_page.call_count == 1


def test_native_fetch_uses_separate_context_per_domain(monkeypatch):
    sb, _, _, created, _ = _cache_browser(monkeypatch)

    _fetch(sb, "https://a.example/1")
    _fetch(sb, "https://b.example/1")

    assert len(created) == 2


def test_cached_context_expires_after_idle_ttl(monkeypatch):
    sb, _, _, created, _ = _cache_browser(monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr(sb, "_now", lambda: clock[0])

    _fetch(sb)
    clock[0] += sb.CONTEXT_IDLE_TTL_S + 1
    _fetch(sb)

    assert len(created) == 2
    created[0].close.assert_called_once()


def test_cached_context_expires_after_max_age_even_when_busy(monkeypatch):
    sb, _, _, created, _ = _cache_browser(monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr(sb, "_now", lambda: clock[0])

    while clock[0] - 1000.0 <= sb.CONTEXT_MAX_AGE_S:
        _fetch(sb)
        clock[0] += sb.CONTEXT_IDLE_TTL_S - 1
    assert len(created) == 1
    _fetch(sb)

    assert len(created) == 2
    created[0].close.assert_called_once()


def test_context_cache_is_bounded_and_evicts_least_recently_used(monkeypatch):
    sb, _, _, created, _ = _cache_browser(monkeypatch)

    for i in range(sb.MAX_CACHED_CONTEXTS):
        _fetch(sb, f"https://site{i}.example/")
    _fetch(sb, "https://site0.example/again")  # site0 jadi yang terbaru dipakai
    _fetch(sb, "https://extra.example/")

    assert len(created) == sb.MAX_CACHED_CONTEXTS + 1
    created[1].close.assert_called_once()
    created[0].close.assert_not_called()


def test_cached_contexts_dropped_when_thread_browser_is_recycled(monkeypatch):
    sb, first_browser, _, created, _ = _cache_browser(monkeypatch)
    _fetch(sb)

    second_browser = MagicMock()
    second_browser.new_context.side_effect = first_browser.new_context.side_effect
    monkeypatch.setattr(sb, "_get_thread_browser", lambda: second_browser)
    _fetch(sb)

    assert second_browser.new_context.call_count == 1
    created[0].close.assert_called_once()


def test_context_cache_is_thread_local(monkeypatch):
    sb, _, _, created, _ = _cache_browser(monkeypatch)
    _fetch(sb)

    errors = []

    def other_thread():
        try:
            _fetch(sb)
            sb.close_thread_contexts()
        except Exception as exc:  # pragma: no cover - diagnosa
            errors.append(exc)

    worker = threading.Thread(target=other_thread)
    worker.start()
    worker.join()

    assert errors == []
    assert len(created) == 2


def test_failed_fetch_evicts_cached_context(monkeypatch):
    sb, _, _, created, behavior = _cache_browser(monkeypatch)
    _fetch(sb)

    behavior["goto_error"] = RuntimeError("net::ERR_CONNECTION_RESET")
    with pytest.raises(RuntimeError):
        _fetch(sb)
    created[0].close.assert_called_once()

    behavior["goto_error"] = None
    _fetch(sb)
    assert len(created) == 2


def test_reused_context_tolerates_proxy_tunnel_reuse_once_verified(monkeypatch):
    """Tunnel CONNECT yang dipakai ulang tidak menambah koneksi proxy; context sudah terverifikasi."""
    sb, _, _, created, behavior = _cache_browser(monkeypatch)
    _fetch(sb)

    behavior["uses_proxy"] = False
    assert "ok" in _fetch(sb, "https://novel.example/ch2").html
    assert len(created) == 1


def test_unverified_context_fails_closed_and_is_evicted_when_proxy_bypassed(monkeypatch):
    sb, _, _, created, behavior = _cache_browser(monkeypatch)
    behavior["uses_proxy"] = False

    with pytest.raises(RuntimeError, match="proxy"):
        _fetch(sb)
    created[0].close.assert_called_once()
    with pytest.raises(RuntimeError, match="proxy"):
        _fetch(sb)
    assert len(created) == 2


def test_context_recreated_when_egress_proxy_changes(monkeypatch):
    sb, _, proxy, created, _ = _cache_browser(monkeypatch)
    _fetch(sb)

    proxy.server_url = "http://127.0.0.1:10"
    _fetch(sb)

    assert len(created) == 2
    assert created[1].options["proxy"]["server"] == "http://127.0.0.1:10"
    created[0].close.assert_called_once()


def _paused_handler(monkeypatch, validator, frame_tree_main="MAIN"):
    import services.scrapers.stealth_base as sb

    sent = []
    handlers = {}
    cdp = MagicMock()

    def send(method, params=None):
        sent.append((method, params))
        if method == "Page.getFrameTree":
            return {"frameTree": {"frame": {"id": frame_tree_main}}}
        return None

    cdp.send.side_effect = send
    cdp.on.side_effect = lambda name, fn: handlers.__setitem__(name, fn)
    context = MagicMock()
    context.new_cdp_session.return_value = cdp
    monkeypatch.setattr(sb, "validate_external_url", validator)
    state = sb._install_ssrf_guard(context, MagicMock())
    return handlers["Fetch.requestPaused"], sent, state


def test_guard_fails_request_when_validator_raises_unexpected_error(monkeypatch):
    def boom(url):
        raise UnicodeError("label too long")

    on_paused, sent, _ = _paused_handler(monkeypatch, boom)
    on_paused({"requestId": "r1", "request": {"url": "http://" + "a" * 70 + ".example/"}, "resourceType": "Document", "frameId": "MAIN"})
    assert ("Fetch.failRequest", {"requestId": "r1", "errorReason": "BlockedByClient"}) in sent


def test_guard_marks_only_main_frame_document_as_blocked_navigation(monkeypatch):
    on_paused, _, state = _paused_handler(monkeypatch, _fake_validator)
    on_paused({"requestId": "r1", "request": {"url": "http://localhost/x"}, "resourceType": "Document", "frameId": "CHILD"})
    assert state["blocked_document"] is False
    on_paused({"requestId": "r2", "request": {"url": "http://localhost/y"}, "resourceType": "Document", "frameId": "MAIN"})
    assert state["blocked_document"] is True


def _guard_harness(monkeypatch):
    """Guard terpasang di CDP palsu; mengembalikan (emit event, pesan per rute sessionId)."""
    import json

    import services.scrapers.stealth_base as sb

    sent = []
    handlers = {}
    cdp = MagicMock()
    cdp.send.side_effect = lambda method, params=None: sent.append((method, params))
    cdp.on.side_effect = lambda name, fn: handlers.__setitem__(name, fn)
    context = MagicMock()
    context.new_cdp_session.return_value = cdp
    monkeypatch.setattr(sb, "validate_external_url", _fake_validator)
    state = sb._install_ssrf_guard(context, MagicMock())

    def child_messages():
        """Bongkar Target.sendMessageToTarget berlapis -> [(rute, pesan dalam)]."""
        out = []
        for method, params in sent:
            if method != "Target.sendMessageToTarget":
                continue
            route, msg = (params["sessionId"],), json.loads(params["message"])
            while msg["method"] == "Target.sendMessageToTarget":
                route, msg = route + (msg["params"]["sessionId"],), json.loads(msg["params"]["message"])
            out.append((route, msg))
        return out

    def from_child(route, msg):
        """Pesan dari target anak, dibungkus receivedMessageFromTarget sesuai rute."""
        for session_id in reversed(route[1:]):
            msg = {"method": "Target.receivedMessageFromTarget", "params": {"sessionId": session_id, "message": json.dumps(msg)}}
        handlers["Target.receivedMessageFromTarget"]({"sessionId": route[0], "message": json.dumps(msg)})

    def reply(route, method, error=False):
        msg_id = next(m["id"] for r, m in child_messages() if r == route and m["method"] == method)
        from_child(route, {"id": msg_id, **({"error": {"message": "boom"}} if error else {"result": {}})})

    def methods(route):
        return [m["method"] for r, m in child_messages() if r == route]

    attach = {"targetInfo": {"type": "iframe", "url": ""}, "waitingForDebugger": True}
    return types.SimpleNamespace(
        state=state, sent=sent, handlers=handlers, child_messages=child_messages, from_child=from_child,
        reply=reply, methods=methods, attach=attach,
    )


def test_guard_holds_cross_site_iframes_at_start(monkeypatch):
    h = _guard_harness(monkeypatch)
    assert ("Target.setAutoAttach", {
        "autoAttach": True, "waitForDebuggerOnStart": True, "flatten": False, "filter": [{"type": "iframe"}],
    }) in h.sent
    methods = [m for m, _ in h.sent]
    assert methods.index("Fetch.enable") < methods.index("Target.setAutoAttach")


def test_guard_resumes_child_iframe_only_after_its_interception_is_active(monkeypatch):
    h = _guard_harness(monkeypatch)
    h.handlers["Target.attachedToTarget"]({"sessionId": "C1", **h.attach})
    assert h.methods(("C1",)) == ["Fetch.enable"]

    h.reply(("C1",), "Fetch.enable")
    assert h.methods(("C1",)) == ["Fetch.enable", "Target.setAutoAttach"]

    h.reply(("C1",), "Target.setAutoAttach")
    assert h.methods(("C1",))[-1] == "Runtime.runIfWaitingForDebugger"


@pytest.mark.parametrize("failing", ["Fetch.enable", "Target.setAutoAttach"])
def test_guard_keeps_child_iframe_paused_when_it_cannot_be_guarded(monkeypatch, failing):
    h = _guard_harness(monkeypatch)
    h.handlers["Target.attachedToTarget"]({"sessionId": "C1", **h.attach})
    if failing == "Target.setAutoAttach":
        h.reply(("C1",), "Fetch.enable")
    h.reply(("C1",), failing, error=True)
    assert "Runtime.runIfWaitingForDebugger" not in h.methods(("C1",))


def test_guard_filters_requests_inside_nested_child_iframes(monkeypatch):
    h = _guard_harness(monkeypatch)
    h.handlers["Target.attachedToTarget"]({"sessionId": "C1", **h.attach})
    h.from_child(("C1",), {"method": "Target.attachedToTarget", "params": {"sessionId": "G1", **h.attach}})
    assert h.methods(("C1", "G1")) == ["Fetch.enable"]

    for request_id, url in (("r1", "http://localhost/leak"), ("r2", "http://public.example/ok")):
        h.from_child(("C1", "G1"), {"method": "Fetch.requestPaused", "params": {
            "requestId": request_id, "request": {"url": url}, "resourceType": "Image", "frameId": "G-FRAME",
        }})
    grandchild = [m for r, m in h.child_messages() if r == ("C1", "G1")]
    assert {"method": "Fetch.failRequest", "params": {"requestId": "r1", "errorReason": "BlockedByClient"}} in [
        {k: m[k] for k in ("method", "params")} for m in grandchild
    ]
    assert ("Fetch.continueRequest", {"requestId": "r2"}) in [(m["method"], m["params"]) for m in grandchild]


def test_child_iframe_document_block_is_not_a_blocked_navigation(monkeypatch):
    h = _guard_harness(monkeypatch)
    h.handlers["Target.attachedToTarget"]({"sessionId": "C1", **h.attach})
    h.from_child(("C1",), {"method": "Fetch.requestPaused", "params": {
        "requestId": "r1", "request": {"url": "http://localhost/x"}, "resourceType": "Document", "frameId": "C-FRAME",
    }})
    assert "Fetch.failRequest" in h.methods(("C1",))
    assert h.state["blocked_document"] is False


def test_validate_external_url_turns_idna_errors_into_400(monkeypatch):
    from services.security import validate_external_url

    def idna_fail(host, *a, **k):
        # Perilaku getaddrinfo asli untuk label > 63 karakter.
        raise UnicodeError("encoding with 'idna' codec failed (label too long)")

    monkeypatch.setattr(socket, "getaddrinfo", idna_fail)
    with pytest.raises(HTTPException) as exc:
        validate_external_url("http://" + "a" * 70 + ".example/")
    assert exc.value.status_code == 400


# --- Egress proxy yang memvalidasi (lapisan utama Tier 3) ---------------------------

class _Echo:
    """Server TCP lokal kecil: mencatat request mentah dan membalas HTTP 200."""

    def __init__(self):
        self.requests = []
        outer = self

        class H(socketserver.BaseRequestHandler):
            def handle(self):
                data = b""
                self.request.settimeout(3)
                try:
                    while b"\r\n\r\n" not in data:
                        chunk = self.request.recv(4096)
                        if not chunk:
                            break
                        data += chunk
                except OSError:
                    pass
                outer.requests.append(data)
                self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")

        self.srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
        self.srv.daemon_threads = True
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


def _fake_resolver(host, port):
    # "localhost" = internal (ditolak); nama lain dianggap publik dan diarahkan ke server tes.
    if host == "localhost":
        raise HTTPException(status_code=400, detail="Access to private or local network resources is forbidden")
    return "127.0.0.1"


@pytest.fixture
def egress_proxy(monkeypatch):
    import services.egress_proxy as ep

    monkeypatch.setattr(ep, "resolve_public_ip", _fake_resolver)
    return ep.get_egress_proxy()


def _raw(proxy, payload: bytes) -> bytes:
    with socket.create_connection(("127.0.0.1", proxy.port), timeout=5) as s:
        s.sendall(payload)
        out = b""
        try:
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                out += chunk
        except OSError:
            pass
    return out


def test_proxy_rejects_connect_to_private_host(egress_proxy):
    echo = _Echo()
    try:
        out = _raw(egress_proxy, f"CONNECT localhost:{echo.port} HTTP/1.1\r\nHost: localhost:{echo.port}\r\n\r\n".encode())
        assert out.startswith(b"HTTP/1.1 403")
        assert echo.requests == []
    finally:
        echo.close()


def test_proxy_tunnels_connect_to_the_ip_it_validated(egress_proxy):
    echo = _Echo()
    try:
        # "rebind.test" tidak ada di DNS sungguhan: proxy harus menyambung ke IP hasil
        # validasinya sendiri, bukan me-resolve ulang nama host (anti DNS rebinding).
        with socket.create_connection(("127.0.0.1", egress_proxy.port), timeout=5) as s:
            s.sendall(f"CONNECT rebind.test:{echo.port} HTTP/1.1\r\nHost: rebind.test\r\n\r\n".encode())
            assert s.recv(4096).startswith(b"HTTP/1.1 200")
            s.sendall(b"GET /tunnel HTTP/1.1\r\nHost: rebind.test\r\n\r\n")
            assert b"200 OK" in s.recv(4096)
        assert echo.requests and echo.requests[0].startswith(b"GET /tunnel ")
    finally:
        echo.close()


def test_proxy_forwards_plain_http_in_origin_form_and_closes(egress_proxy):
    echo = _Echo()
    try:
        out = _raw(
            egress_proxy,
            f"GET http://public.test:{echo.port}/p?q=1 HTTP/1.1\r\nHost: public.test:{echo.port}\r\n"
            f"Proxy-Connection: keep-alive\r\nConnection: keep-alive\r\n\r\n".encode(),
        )
        assert out.startswith(b"HTTP/1.1 200")
        req = echo.requests[0]
        assert req.startswith(b"GET /p?q=1 HTTP/1.1\r\n")
        assert b"Proxy-Connection" not in req
        assert b"Connection: close" in req
    finally:
        echo.close()


def test_proxy_rejects_plain_http_to_private_host(egress_proxy):
    echo = _Echo()
    try:
        out = _raw(egress_proxy, f"GET http://localhost:{echo.port}/x HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
        assert out.startswith(b"HTTP/1.1 403")
        assert echo.requests == []
    finally:
        echo.close()


# --- Tier 3: browser sungguhan (dilewati bila Chromium tidak tersedia) ----------------

class _Server:
    """Server lokal: /start -> 302 /hop -> 302 http://localhost/internal; /v/<vektor> = halaman penyerang."""

    def __init__(self):
        self.hits = []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _any(self):
                outer.hits.append((self.headers.get("Host") or "").split(":")[0] + self.path)
                port = outer.port
                if self.path == "/start":
                    self._redirect(f"http://127.0.0.1:{port}/hop")
                elif self.path == "/hop":
                    self._redirect(f"http://localhost:{port}/internal")
                elif self.path == "/ok-start":
                    self._redirect(f"http://127.0.0.1:{port}/page")
                elif self.path.startswith("/v/"):
                    self._html(_attack_page(self.path[3:], port))
                elif self.path == "/set-cookie":
                    self._html("<html><body><p>challenge lolos</p></body></html>", ["cf_clearance=solved; Path=/"])
                elif self.path == "/echo-cookie":
                    self._html(f"<html><body><p>cookie=[{self.headers.get('Cookie') or ''}]</p></body></html>")
                elif self.path == "/frame-nest":
                    self._html(f'<html><body><iframe src="http://other-site.test:{port}/frame"></iframe></body></html>')
                elif self.path == "/frame":
                    self._html(
                        f'<html><body><img src="http://localhost:{port}/leak-frame.png">'
                        f'<script>fetch("http://localhost:{port}/leak-frame-fetch").catch(() => {{}});</script></body></html>'
                    )
                else:
                    self._html(
                        f'<html><body><p>halaman publik</p><script src="http://localhost:{port}/leak.js"></script>'
                        f'<img src="http://localhost:{port}/leak.png"></body></html>'
                    )

            do_GET = do_POST = _any

            def _html(self, body, set_cookies=()):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                for cookie in set_cookies:
                    self.send_header("Set-Cookie", cookie)
                self.end_headers()
                self.wfile.write(body.encode())

            def _redirect(self, loc):
                self.send_response(302)
                self.send_header("Location", loc)
                self.end_headers()

        self.httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


_VECTORS = [
    "fetch", "worker_fetch", "worker_ws", "plain_ws", "wsstream", "sharedworker",
    "popup", "form_blank", "spec_prefetch", "link_prefetch", "beacon", "cross_site_iframe",
    "nested_cross_site_iframe",
]


def _attack_page(vector: str, port: int) -> str:
    leak = f"http://localhost:{port}/leak-{vector}"
    ws = f"ws://localhost:{port}/leak-{vector}"
    js = {
        "fetch": f'fetch("{leak}").catch(() => {{}});',
        "worker_fetch": f'new Worker(URL.createObjectURL(new Blob([`fetch("{leak}").catch(() => {{}})`])));',
        "worker_ws": f'new Worker(URL.createObjectURL(new Blob([`try {{ new WebSocket("{ws}") }} catch (e) {{}}`])));',
        "plain_ws": f'try {{ new WebSocket("{ws}"); }} catch (e) {{}}',
        "wsstream": f'if (typeof WebSocketStream !== "undefined") {{ try {{ new WebSocketStream("{ws}"); }} catch (e) {{}} }}',
        "sharedworker": f'try {{ new SharedWorker(URL.createObjectURL(new Blob([`fetch("{leak}").catch(() => {{}})`]))); }} catch (e) {{}}',
        "popup": f'window.open("{leak}");',
        "form_blank": (
            f'const f = document.createElement("form"); f.method = "POST"; f.action = "{leak}"; '
            f'f.target = "_blank"; document.body.appendChild(f); f.submit();'
        ),
        "beacon": f'navigator.sendBeacon("{leak}", "x");',
    }.get(vector, "")
    extra = {
        "spec_prefetch": f'<script type="speculationrules">{{"prefetch":[{{"source":"list","urls":["{leak}"]}}]}}</script>',
        "link_prefetch": f'<link rel="prefetch" href="{leak}">',
        "cross_site_iframe": f'<iframe src="http://cross-site.test:{port}/frame"></iframe>',
        "nested_cross_site_iframe": f'<iframe src="http://cross-site.test:{port}/frame-nest"></iframe>',
    }.get(vector, "")
    return f"<html><body><p>halaman penyerang</p>{extra}<script>{js}</script></body></html>"


def _fake_validator(url: str) -> None:
    # 127.0.0.1 = "publik" di tes ini; localhost = host internal yang harus diblokir.
    if (urlparse(url).hostname or "") == "localhost":
        raise HTTPException(status_code=400, detail="Access to private or local network resources is forbidden")


@pytest.fixture
def real_browser(monkeypatch, egress_proxy):
    try:
        # Mesin yang sama dengan produksi (novalpie._get_thread_browser): Patchright bila ada.
        try:
            from patchright.sync_api import sync_playwright
        except ImportError:
            from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
    except Exception as exc:  # pragma: no cover - lingkungan tanpa Playwright
        pytest.skip(f"Playwright tidak tersedia: {exc}")
    from services.scrapers.browser_stealth import build_launch_args, launch_stealth_browser

    try:
        # PW_CHROMIUM_EXECUTABLE: opsional, untuk lingkungan yang versi Chromium-nya tidak
        # cocok dengan paket playwright terpasang.
        exe = os.environ.get("PW_CHROMIUM_EXECUTABLE")
        if exe:
            browser = pw.chromium.launch(headless=True, executable_path=exe, args=build_launch_args())
        else:
            # Sama dengan browser thread-local produksi: Chromium penuh, site isolation aktif.
            browser = launch_stealth_browser(pw)
    except Exception as exc:  # pragma: no cover - Chromium belum terpasang
        pw.stop()
        pytest.skip(f"Chromium tidak bisa dijalankan: {exc}")
    import services.scrapers.stealth_base as sb

    monkeypatch.setattr(sb, "_get_thread_browser", lambda: browser)
    monkeypatch.setattr(sb, "validate_external_url", _fake_validator)
    yield sb
    sb.close_thread_contexts()
    browser.close()
    pw.stop()


def _no_internal_hits(server):
    return not any(h.startswith("localhost") for h in server.hits)


def test_real_browser_blocks_private_redirect_hop_before_it_is_requested(real_browser):
    server = _Server()
    try:
        with pytest.raises(HTTPException) as exc:
            real_browser.StealthyNovelAdapter()._fetch_playwright_sync(
                f"http://127.0.0.1:{server.port}/start", solve_cloudflare=False, timeout_ms=15000
            )
        assert exc.value.status_code == 400
        assert "127.0.0.1/hop" in server.hits  # hop publik tetap diikuti
        assert _no_internal_hits(server), server.hits
    finally:
        server.close()


def test_real_browser_blocks_private_subresources_but_returns_page(real_browser):
    server = _Server()
    try:
        page = real_browser.StealthyNovelAdapter()._fetch_playwright_sync(
            f"http://127.0.0.1:{server.port}/ok-start", solve_cloudflare=False, disable_resources=False, timeout_ms=15000
        )
        assert "halaman publik" in page.html
        assert page.url == f"http://127.0.0.1:{server.port}/page"
        assert _no_internal_hits(server), server.hits
    finally:
        server.close()


def test_real_browser_keeps_cookies_per_workspace_domain_but_never_across_workspaces(real_browser):
    server = _Server()
    base = f"http://127.0.0.1:{server.port}"

    def fetch(workspace, path):
        return real_browser.StealthyNovelAdapter(workspace=workspace)._fetch_playwright_sync(
            base + path, solve_cloudflare=False, timeout_ms=15000
        )

    try:
        assert "challenge lolos" in fetch("main", "/set-cookie").html
        assert "cookie=[cf_clearance=solved]" in fetch("main", "/echo-cookie").html
        assert "cookie=[]" in fetch("ghost", "/echo-cookie").html
    finally:
        server.close()


@pytest.mark.parametrize("path", ["/plain-private", "/redirect-private"])
def test_real_browser_proxy_blocks_private_navigation_even_if_cdp_layer_allows_it(monkeypatch, real_browser, path):
    """Lapisan proxy berdiri sendiri: guard CDP dimatikan, navigasi ke host internal tetap 400."""
    monkeypatch.setattr(real_browser, "validate_external_url", lambda url: None)
    server = _Server()
    try:
        start = (
            f"http://localhost:{server.port}/internal"
            if path == "/plain-private"
            else f"http://127.0.0.1:{server.port}/hop"
        )
        with pytest.raises(HTTPException) as exc:
            real_browser.StealthyNovelAdapter()._fetch_playwright_sync(start, solve_cloudflare=False, timeout_ms=15000)
        assert exc.value.status_code == 400
        assert _no_internal_hits(server), server.hits
    finally:
        server.close()


@pytest.mark.parametrize("vector", _VECTORS)
def test_real_browser_attack_page_cannot_reach_private_host(real_browser, vector):
    server = _Server()
    try:
        page = real_browser.StealthyNovelAdapter()._fetch_playwright_sync(
            f"http://127.0.0.1:{server.port}/v/{vector}",
            solve_cloudflare=False,
            disable_resources=True,
            page_action=lambda p: p.wait_for_timeout(1500),
            timeout_ms=15000,
        )
        assert "halaman penyerang" in page.html
        if vector == "cross_site_iframe":
            assert "cross-site.test/frame" in server.hits  # iframe publik lintas situs tetap dimuat
        if vector == "nested_cross_site_iframe":
            assert "other-site.test/frame" in server.hits
        assert _no_internal_hits(server), server.hits
    finally:
        server.close()


@pytest.mark.parametrize("vector, frame_hit", [
    ("cross_site_iframe", "cross-site.test/frame"),
    ("nested_cross_site_iframe", "other-site.test/frame"),
])
def test_real_browser_cdp_guard_covers_cross_site_iframes_without_proxy(monkeypatch, real_browser, vector, frame_hit):
    """
    Lapisan CDP berdiri sendiri: proxy dibuat meloloskan semua host. Di Chromium penuh iframe
    lintas-situs adalah target OOPIF terpisah; guard harus tetap menjeda request-nya.
    """
    import services.egress_proxy as ep

    monkeypatch.setattr(ep, "resolve_public_ip", lambda host, port: "127.0.0.1")
    server = _Server()
    try:
        page = real_browser.StealthyNovelAdapter()._fetch_playwright_sync(
            f"http://127.0.0.1:{server.port}/v/{vector}",
            solve_cloudflare=False,
            disable_resources=True,
            page_action=lambda p: p.wait_for_timeout(1500),
            timeout_ms=15000,
        )
        assert "halaman penyerang" in page.html
        assert frame_hit in server.hits  # iframe tetap dimuat, bukan sekadar macet
        assert _no_internal_hits(server), server.hits
    finally:
        server.close()


_NAVIGATING = "Page.content: Unable to retrieve content because the page is navigating and changing the content."


def test_native_fetch_retries_content_while_page_navigates_after_challenge(monkeypatch):
    proxy = _FakeProxy()

    def goto(*a, **k):
        proxy.handled += 1
        return MagicMock(status=200)

    sb, _, _, page, _, _ = _mock_browser(monkeypatch, goto=goto, proxy=proxy)
    # Redirect pasca-challenge: content() gagal sesaat, lalu halaman tujuan siap.
    page.content.side_effect = [RuntimeError(_NAVIGATING), "<html><body>bab</body></html>", "<html><body>bab</body></html>"]

    result = sb.StealthyNovelAdapter()._fetch_playwright_sync("https://public.example/x", disable_resources=False)
    assert "bab" in result.html


def test_native_fetch_does_not_retry_unrelated_content_errors(monkeypatch):
    proxy = _FakeProxy()

    def goto(*a, **k):
        proxy.handled += 1
        return MagicMock(status=200)

    sb, _, _, page, _, _ = _mock_browser(monkeypatch, goto=goto, proxy=proxy)
    page.content.side_effect = RuntimeError("Target page, context or browser has been closed")

    with pytest.raises(RuntimeError, match="closed"):
        sb.StealthyNovelAdapter()._fetch_playwright_sync("https://public.example/x", disable_resources=False)
    assert page.content.call_count == 1


def test_native_fetch_gives_up_when_page_keeps_navigating(monkeypatch):
    proxy = _FakeProxy()

    def goto(*a, **k):
        proxy.handled += 1
        return MagicMock(status=200)

    sb, _, _, page, _, _ = _mock_browser(monkeypatch, goto=goto, proxy=proxy)
    page.content.side_effect = RuntimeError(_NAVIGATING)

    with pytest.raises(RuntimeError, match="navigating"):
        sb.StealthyNovelAdapter()._fetch_playwright_sync("https://public.example/x", disable_resources=False)
    assert page.content.call_count == sb.CONTENT_NAVIGATION_RETRIES
