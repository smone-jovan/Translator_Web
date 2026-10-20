"""
Base adapter untuk situs web novel dengan proteksi Cloudflare Turnstile / WAF berat
menggunakan Scrapling (StealthyFetcher / AsyncStealthySession) jika tersedia,
atau Native Adaptive Playwright Fallback + Adaptive DOM Parsing.
"""

import asyncio
import json
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, List, Tuple, Callable, Any
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from fastapi import HTTPException

from database import normalize_workspace
from services.scrapers.base import BaseScraperAdapter, ScrapedNovelMetadata
from services.scrapers.adaptive_dom import AdaptiveDOM, AdaptivePage
from services.scrapers.novalpie import (
    get_scraper_concurrency,
    _get_thread_browser,
    _inject_scrapling_stealth_scripts,
    _install_resource_shield,
)
from services.scrapers.browser_stealth import (
    apply_client_hints,
    build_context_options,
    cloudflare_poll_step,
    is_patchright_object,
    new_cloudflare_state,
)
from services.security import validate_external_url
from services.egress_proxy import get_egress_proxy

try:
    from scrapling.fetchers import StealthyFetcher, AsyncStealthySession
    HAS_SCRAPLING = True
except ImportError:
    HAS_SCRAPLING = False


_SSRF_FORBIDDEN_DETAIL = "Access to private or local network resources is forbidden"
_GOOGLE_REFERER = "https://www.google.com/"
_NON_NETWORK_SCHEMES = {"data", "blob", "about"}
# Redirect pasca-challenge Cloudflare membuat page.content() gagal sesaat ("page is navigating").
CONTENT_NAVIGATION_RETRIES = 5
_CONTENT_RETRY_DELAY_MS = 250
_FETCH_ALL_REQUESTS = {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]}
# Non-flatten: Playwright Python tidak bisa mengirim ke sessionId anak, jadi pesan ke OOPIF
# lewat Target.sendMessageToTarget. Worker/popup sengaja tidak di-attach (ditangani proxy).
_HOLD_CHILD_IFRAMES = {
    "autoAttach": True, "waitForDebuggerOnStart": True, "flatten": False, "filter": [{"type": "iframe"}],
}
# Cache context per (workspace, domain) agar cookie cf_clearance bertahan antar bab.
# Idle TTL sama dengan recycle browser thread-local (novalpie._get_thread_browser, 5 menit).
CONTEXT_IDLE_TTL_S = 300.0
CONTEXT_MAX_AGE_S = 1800.0
MAX_CACHED_CONTEXTS = 4
_now = time.monotonic
# Browser thread-local, jadi cache context juga thread-local: tanpa lock, tak pernah lintas thread.
_context_local = threading.local()


@dataclass
class _CachedContext:
    context: Any
    browser: Any
    proxy_url: str
    created: float
    last_used: float
    # Konfigurasi proxy per-context tidak berubah: cukup dibuktikan sekali. Fetch berikutnya
    # bisa memakai ulang tunnel CONNECT lama sehingga tidak menambah hitungan koneksi proxy.
    proxy_verified: bool = False


def _context_cache_key(workspace: Optional[str], url: str) -> Tuple[str, str]:
    """Key bergaya make_workspace_key: context tidak pernah dibagi antar workspace main/ghost."""
    return (normalize_workspace(workspace), (urlparse(url).hostname or "").lower())


def _thread_contexts() -> "OrderedDict[Tuple[str, str], _CachedContext]":
    entries = getattr(_context_local, "entries", None)
    if entries is None:
        entries = _context_local.entries = OrderedDict()
    return entries


def _close_quietly(target: Any) -> None:
    try:
        target.close()
    except Exception:
        pass


def _evict_context(key: Tuple[str, str]) -> None:
    entry = _thread_contexts().pop(key, None)
    if entry is not None:
        _close_quietly(entry.context)


def close_thread_contexts() -> None:
    """Tutup semua context ter-cache milik thread ini."""
    for key in list(_thread_contexts()):
        _evict_context(key)


def _acquire_context(browser: Any, key: Tuple[str, str], proxy_url: str) -> _CachedContext:
    now = _now()
    entries = _thread_contexts()
    for cached_key, cached in list(entries.items()):
        # Browser di-recycle (idle/putus) = context lamanya ikut mati bersama browser itu.
        if (
            cached.browser is not browser
            or now - cached.last_used > CONTEXT_IDLE_TTL_S
            or now - cached.created > CONTEXT_MAX_AGE_S
            or (cached_key == key and cached.proxy_url != proxy_url)
        ):
            _evict_context(cached_key)

    entry = entries.get(key)
    if entry is None:
        # Lapisan utama SSRF: semua koneksi browser context ini lewat egress proxy yang
        # me-resolve sendiri, menolak IP non-publik, dan menyambung ke IP yang sudah dicek.
        # "<-loopback>": tanpa ini Chromium mem-bypass proxy untuk localhost/127.0.0.1.
        context = browser.new_context(
            **build_context_options(browser),
            proxy={"server": proxy_url, "bypass": "<-loopback>"},
            # Service worker bisa membuat request di luar jangkauan guard SSRF per halaman.
            service_workers="block",
        )
        try:
            _inject_scrapling_stealth_scripts(context)
        except Exception:
            _close_quietly(context)
            raise
        entry = entries[key] = _CachedContext(context, browser, proxy_url, created=now, last_used=now)
        while len(entries) > MAX_CACHED_CONTEXTS:
            _evict_context(next(iter(entries)))
    entries.move_to_end(key)
    entry.last_used = now
    return entry


def _release_context(key: Tuple[str, str], entry: _CachedContext, keep: bool) -> None:
    # Halaman (termasuk popup sisa) selalu ditutup; context hanya disimpan bila fetch sukses.
    try:
        pages = list(entry.context.pages)
    except Exception:
        pages = []
    for page in pages:
        _close_quietly(page)
    if not keep and _thread_contexts().get(key) is entry:
        _evict_context(key)


class _ChildFrameGuard:
    """
    Chromium penuh menjalankan iframe lintas-situs sebagai target OOPIF sendiri, di luar
    jangkauan `Fetch` milik halaman. Auto-attach di sesi guard menahan tiap OOPIF (dan
    turunannya) sebelum jalan; target baru dilanjutkan setelah Fetch.enable dan auto-attach
    untuk turunannya sukses. Gagal di langkah mana pun = target tetap tertahan (fail closed).
    """

    def __init__(self, cdp: Any, on_paused: Callable[[Callable[[str, dict], None], dict], None]):
        self._cdp = cdp
        self._on_paused = on_paused
        self._last_id = 0
        self._on_success: dict = {}

    def install(self) -> None:
        self._cdp.on("Target.attachedToTarget", lambda ev: self._hold((ev.get("sessionId"),)))
        self._cdp.on(
            "Target.receivedMessageFromTarget",
            lambda ev: self._receive((ev.get("sessionId"),), ev.get("message")),
        )
        self._cdp.send("Target.setAutoAttach", _HOLD_CHILD_IFRAMES)

    def _send(self, route: tuple, method: str, params: Optional[dict] = None, on_success=None) -> None:
        """Kirim ke target anak di ujung `route` (sessionId berlapis, dari yang terluar)."""
        self._last_id += 1
        msg_id = self._last_id
        if on_success is not None:
            self._on_success[msg_id] = on_success
        message = {"id": msg_id, "method": method, "params": params or {}}
        for session_id in reversed(route[1:]):
            self._last_id += 1
            message = {
                "id": self._last_id,
                "method": "Target.sendMessageToTarget",
                "params": {"sessionId": session_id, "message": json.dumps(message)},
            }
        try:
            self._cdp.send("Target.sendMessageToTarget", {"sessionId": route[0], "message": json.dumps(message)})
        except Exception:
            self._on_success.pop(msg_id, None)  # target sudah hilang; tetap tertahan

    def _hold(self, route: tuple) -> None:
        def resume() -> None:
            self._send(route, "Runtime.runIfWaitingForDebugger")

        self._send(
            route, "Fetch.enable", _FETCH_ALL_REQUESTS,
            on_success=lambda: self._send(route, "Target.setAutoAttach", _HOLD_CHILD_IFRAMES, on_success=resume),
        )

    def _receive(self, route: tuple, raw: Optional[str]) -> None:
        try:
            msg = json.loads(raw or "")
        except ValueError:
            return
        if "id" in msg:
            on_success = self._on_success.pop(msg["id"], None)
            if on_success is not None and "error" not in msg:
                on_success()
            return
        method, params = msg.get("method"), msg.get("params") or {}
        if method == "Target.receivedMessageFromTarget":
            self._receive(route + (params.get("sessionId"),), params.get("message"))
        elif method == "Target.attachedToTarget":
            self._hold(route + (params.get("sessionId"),))
        elif method == "Fetch.requestPaused":
            self._on_paused(lambda m, p: self._send(route, m, p), params)


def _install_ssrf_guard(context: Any, page: Any) -> dict:
    """
    Lapisan kedua SSRF untuk browser (ADR-126); lapisan utamanya egress proxy yang memvalidasi.

    CDP `Fetch` (requestStage=Request) menjeda dokumen awal, tiap hop redirect (yang tidak
    terlihat oleh `page.route`), subresource, fetch/XHR, dan request Web Worker di target
    halaman ini serta di setiap iframe OOPIF (`_ChildFrameGuard`), lalu menggagalkan request
    ke host yang gagal `validate_external_url` sebelum koneksi dibuat. Gunanya: kegagalan
    cepat dan pesan 400 yang jelas untuk navigasi utama. Popup, form `target=_blank`, WebSocket, dan target lain tidak dijeda di sini;
    jalur itu ditangani proxy. Gagal dipasang = exception (fail closed).
    """
    state = {"blocked": [], "blocked_document": False}
    host_ok: dict = {}
    cdp = context.new_cdp_session(page)
    main_frame_id = None
    try:
        tree = cdp.send("Page.getFrameTree") or {}
        main_frame_id = ((tree.get("frameTree") or {}).get("frame") or {}).get("id")
    except Exception:
        main_frame_id = None

    def _allowed(url: str) -> bool:
        scheme = url.split(":", 1)[0].lower()
        if scheme in _NON_NETWORK_SCHEMES:
            return True
        if scheme in ("ws", "wss"):
            url = ("https" if scheme == "wss" else "http") + url[len(scheme):]
        elif scheme not in ("http", "https"):
            return False
        try:
            host = (urlparse(url).hostname or "").lower()
        except ValueError:
            return False
        if host not in host_ok:
            try:
                validate_external_url(url)
                host_ok[host] = True
            except Exception:
                # HTTPException maupun error tak terduga (mis. UnicodeError IDNA) = tolak.
                host_ok[host] = False
        return host_ok[host]

    def _on_paused(event: dict, send: Callable[[str, dict], Any] = cdp.send, main_target: bool = True) -> None:
        request_id = event.get("requestId")
        url = (event.get("request") or {}).get("url", "")
        allowed = False
        try:
            allowed = _allowed(url)
        except Exception:
            allowed = False
        try:
            if allowed:
                send("Fetch.continueRequest", {"requestId": request_id})
                return
            state["blocked"].append(url)
            is_main = main_target and (main_frame_id is None or event.get("frameId") == main_frame_id)
            if event.get("resourceType") == "Document" and is_main:
                state["blocked_document"] = True
            send("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"})
        except Exception:
            # Target sudah ditutup / request sudah dibatalkan.
            pass

    cdp.on("Fetch.requestPaused", _on_paused)
    cdp.send("Fetch.enable", _FETCH_ALL_REQUESTS)
    _ChildFrameGuard(cdp, lambda send, event: _on_paused(event, send, main_target=False)).install()
    return state


def _page_content(page: Any) -> str:
    for _ in range(CONTENT_NAVIGATION_RETRIES - 1):
        try:
            return page.content()
        except Exception as exc:
            if "is navigating" not in str(exc):
                raise
        page.wait_for_timeout(_CONTENT_RETRY_DELAY_MS)
    return page.content()


class StealthyNovelAdapter(BaseScraperAdapter):
    """
    Template / Base class untuk adapter situs novel baru yang memerlukan:
    1. Bypass Cloudflare Turnstile/Interstitial otomatis (`solve_cloudflare=True`)
    2. Pemblokiran resource berat seperti font/tracker (`disable_resources=True`)
    3. Pencarian elemen adaptif yang tahan perubahan desain web (`adaptive=True`)
    """

    def __init__(self, workspace: Optional[str] = None, adaptive_domain: Optional[str] = None):
        self.workspace = workspace
        self.adaptive_domain = adaptive_domain
        if HAS_SCRAPLING and adaptive_domain:
            StealthyFetcher.adaptive = True

    def _fetch_playwright_sync(
        self,
        url: str,
        *,
        solve_cloudflare: bool = True,
        disable_resources: bool = True,
        wait_selector: Optional[str] = None,
        wait_selector_state: str = "attached",
        page_action: Optional[Callable[[Any], Any]] = None,
        cookies: Optional[List[dict]] = None,
        timeout_ms: int = 60000,
    ) -> AdaptivePage:
        try:
            from playwright_stealth import sync_stealth
            has_stealth = True
        except ImportError:
            has_stealth = False

        browser = _get_thread_browser()
        egress_proxy = get_egress_proxy()
        cache_key = _context_cache_key(self.workspace, url)
        entry = _acquire_context(browser, cache_key, egress_proxy.server_url)
        context = entry.context
        if cookies:
            try:
                context.add_cookies(cookies)
            except Exception:
                pass

        keep_context = False
        try:
            page = context.new_page()
            ssrf_guard = _install_ssrf_guard(context, page)
            apply_client_hints(context, page, browser)
            if disable_resources:
                _install_resource_shield(page, disable_resources=True)
            if has_stealth and not is_patchright_object(page):
                try:
                    sync_stealth(page, pure_js=True)
                except Exception:
                    pass

            proxied_before = egress_proxy.handled
            proxy_blocked_before = egress_proxy.blocked
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms, referer=_GOOGLE_REFERER)
            except Exception:
                # CONNECT (https) yang ditolak proxy muncul sebagai error jaringan biasa.
                if ssrf_guard["blocked_document"] or egress_proxy.blocked > proxy_blocked_before:
                    raise HTTPException(status_code=400, detail=_SSRF_FORBIDDEN_DETAIL)
                raise
            # http biasa yang ditolak proxy muncul sebagai respons 403 bertanda dari proxy.
            resp_headers = getattr(resp, "headers", None) if resp is not None else None
            proxy_refused = isinstance(resp_headers, dict) and bool(resp_headers.get("x-ssrf-blocked"))
            if proxy_refused:
                raise HTTPException(status_code=400, detail=_SSRF_FORBIDDEN_DETAIL)
            if egress_proxy.handled == proxied_before and not entry.proxy_verified:
                # Fail closed: halaman termuat tanpa satu pun koneksi lewat proxy, berarti
                # konfigurasi proxy per-context diabaikan dan browser menyambung langsung.
                raise RuntimeError("SSRF egress proxy was bypassed; refusing to return the page")
            entry.proxy_verified = True
            status_code = resp.status if resp else 200

            max_poll_s = min(20.0, max(5.0, timeout_ms / 3000.0))
            poll_interval = 0.5
            elapsed = 0.0
            cf_state = new_cloudflare_state()
            while elapsed < max_poll_s:
                raw_html = _page_content(page)
                if cloudflare_poll_step(page, raw_html, cf_state, solve=solve_cloudflare):
                    page.wait_for_timeout(int(poll_interval * 1000))
                    elapsed += poll_interval
                    continue
                break

            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, state=wait_selector_state, timeout=min(10000, timeout_ms))
                except Exception:
                    pass
            else:
                # Universal SPA prose-ready poll: when no selector is given and initial DOM looks
                # like an unhydrated Vue/React/Next/Nuxt shell, poll briefly (up to 3.0s) until
                # prose paragraphs appear.
                try:
                    probe_html = _page_content(page)
                    if re.search(r"(?:id=[\x27\"](?:app|__nuxt|__next|root)[\x27\"]|window\.__NUXT__|__NEXT_DATA__)", probe_html, re.I):
                        for _ in range(6):
                            probe_soup = BeautifulSoup(probe_html, "html.parser")
                            if AdaptiveDOM.find_best_content_container(probe_soup, min_chars=120) is not None:
                                break
                            page.wait_for_timeout(500)
                            probe_html = _page_content(page)
                except Exception:
                    pass

            if callable(page_action):
                try:
                    page_action(page)
                except Exception:
                    pass

            raw_html = _page_content(page)
            final_url = page.url or url
            if final_url and final_url != url:
                validate_external_url(final_url)

            result = AdaptivePage(
                html=raw_html,
                url=final_url,
                domain=self.adaptive_domain or final_url,
                status=status_code,
            )
            keep_context = True
            return result
        finally:
            _release_context(cache_key, entry, keep_context)

    async def fetch_stealth_page(
        self,
        url: str,
        *,
        solve_cloudflare: bool = True,
        disable_resources: bool = True,
        wait_selector: Optional[str] = None,
        wait_selector_state: str = "attached",
        page_action: Optional[Callable[[Any], Any]] = None,
        cookies: Optional[List[dict]] = None,
        timeout_ms: int = 60000,
        strict_ssrf: bool = False,
    ) -> Any:
        """
        strict_ssrf=True: untuk URL pilihan pengguna. Scrapling tidak punya hook per-request,
        sehingga hanya jalur Playwright native (egress proxy + guard CDP) yang menjamin setiap
        koneksi browser divalidasi (ADR-126).
        """
        validate_external_url(url)
        if HAS_SCRAPLING and not strict_ssrf:
            return await StealthyFetcher.async_fetch(
                url,
                headless=True,
                solve_cloudflare=solve_cloudflare,
                disable_resources=disable_resources,
                block_webrtc=True,
                hide_canvas=True,
                google_search=True,
                wait_selector=wait_selector,
                wait_selector_state=wait_selector_state,
                page_action=page_action,
                cookies=cookies,
                timeout=timeout_ms,
            )

        from services.scrapers.novalpie import NovalpieAdapter
        sem = NovalpieAdapter.get_semaphore(self.workspace)
        async with sem:
            return await asyncio.to_thread(
                self._fetch_playwright_sync,
                url,
                solve_cloudflare=solve_cloudflare,
                disable_resources=disable_resources,
                wait_selector=wait_selector,
                wait_selector_state=wait_selector_state,
                page_action=page_action,
                cookies=cookies,
                timeout_ms=timeout_ms,
            )

    async def fetch_stealth_batch(
        self,
        urls: List[str],
        *,
        solve_cloudflare: bool = True,
        disable_resources: bool = True,
        wait_selector: Optional[str] = None,
        timeout_ms: int = 60000,
    ) -> List[Any]:
        for u in urls:
            validate_external_url(u)
        if HAS_SCRAPLING:
            max_pages = get_scraper_concurrency(workspace=self.workspace)
            results = []
            async with AsyncStealthySession(
                headless=True,
                solve_cloudflare=solve_cloudflare,
                disable_resources=disable_resources,
                block_webrtc=True,
                hide_canvas=True,
                timeout=timeout_ms,
                max_pages=max_pages,
            ) as session:
                for u in urls:
                    results.append(await session.fetch(u, wait_selector=wait_selector))
            return results

        tasks = [
            self.fetch_stealth_page(
                u,
                solve_cloudflare=solve_cloudflare,
                disable_resources=disable_resources,
                wait_selector=wait_selector,
                timeout_ms=timeout_ms,
            )
            for u in urls
        ]
        return list(await asyncio.gather(*tasks))

    @staticmethod
    def extract_clean_chapter(
        page: Any,
        title_selector: str,
        content_selector: str,
        *,
        adaptive: bool = True,
        auto_save: bool = False,
        domain: str = "default",
    ) -> Tuple[str, str]:
        if isinstance(page, str):
            page = AdaptivePage(html=page, domain=domain)
        elif isinstance(page, BeautifulSoup):
            page = AdaptivePage(html=str(page), domain=domain)

        title_nodes = page.css(title_selector, adaptive=adaptive, auto_save=auto_save)
        title = title_nodes[0].text.strip() if title_nodes else "Untitled Chapter"

        content_nodes = page.css(content_selector, adaptive=adaptive, auto_save=auto_save)
        if not content_nodes:
            return title, ""

        paragraphs = [p.text.strip() for p in content_nodes[0].css("p") if p.text and p.text.strip()]
        if not paragraphs:
            raw_text = (
                content_nodes[0].get_all_text(strip=True)
                if hasattr(content_nodes[0], "get_all_text")
                else getattr(content_nodes[0], "text", "")
            )
            paragraphs = [line.strip() for line in raw_text.splitlines() if line.strip()]

        return title, "\n\n".join(paragraphs)

    async def scrape_metadata(
        self, query: str, search_by: str = "original", include_cover: bool = True
    ) -> ScrapedNovelMetadata:
        raise NotImplementedError("Subclass harus mengimplementasikan scrape_metadata")
