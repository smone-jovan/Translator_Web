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

            def _html(self, body):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
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
    }.get(vector, "")
    return f"<html><body><p>halaman penyerang</p>{extra}<script>{js}</script></body></html>"


def _fake_validator(url: str) -> None:
    # 127.0.0.1 = "publik" di tes ini; localhost = host internal yang harus diblokir.
    if (urlparse(url).hostname or "") == "localhost":
        raise HTTPException(status_code=400, detail="Access to private or local network resources is forbidden")


@pytest.fixture
def real_browser(monkeypatch, egress_proxy):
    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
    except Exception as exc:  # pragma: no cover - lingkungan tanpa Playwright
        pytest.skip(f"Playwright tidak tersedia: {exc}")
    try:
        # PW_CHROMIUM_EXECUTABLE: opsional, untuk lingkungan yang versi Chromium-nya tidak
        # cocok dengan paket playwright terpasang.
        exe = os.environ.get("PW_CHROMIUM_EXECUTABLE") or None
        browser = pw.chromium.launch(
            headless=True,
            executable_path=exe,
            # Sama dengan browser thread-local produksi (novalpie._get_thread_browser).
            args=["--disable-features=IsolateOrigins,site-per-process"],
        )
    except Exception as exc:  # pragma: no cover - Chromium belum terpasang
        pw.stop()
        pytest.skip(f"Chromium tidak bisa dijalankan: {exc}")
    import services.scrapers.stealth_base as sb

    monkeypatch.setattr(sb, "_get_thread_browser", lambda: browser)
    monkeypatch.setattr(sb, "validate_external_url", _fake_validator)
    yield sb
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
        assert _no_internal_hits(server), server.hits
    finally:
        server.close()
