"""
Base adapter untuk situs web novel dengan proteksi Cloudflare Turnstile / WAF berat
menggunakan Scrapling (StealthyFetcher / AsyncStealthySession) jika tersedia,
atau Native Adaptive Playwright Fallback + Adaptive DOM Parsing.
"""

import asyncio
from typing import Optional, List, Tuple, Callable, Any
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from fastapi import HTTPException

from services.scrapers.base import BaseScraperAdapter, ScrapedNovelMetadata
from services.scrapers.adaptive_dom import AdaptivePage
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


def _install_ssrf_guard(context: Any, page: Any) -> dict:
    """
    Lapisan kedua SSRF untuk browser (ADR-126); lapisan utamanya egress proxy yang memvalidasi.

    CDP `Fetch` (requestStage=Request) menjeda dokumen awal, tiap hop redirect (yang tidak
    terlihat oleh `page.route`), subresource, fetch/XHR, dan request Web Worker di target
    halaman ini, lalu menggagalkan request ke host yang gagal `validate_external_url`
    sebelum koneksi dibuat. Gunanya: kegagalan cepat dan pesan 400 yang jelas untuk navigasi
    utama. Popup, form `target=_blank`, WebSocket, dan target lain tidak dijeda di sini;
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

    def _on_paused(event: dict) -> None:
        request_id = event.get("requestId")
        url = (event.get("request") or {}).get("url", "")
        allowed = False
        try:
            allowed = _allowed(url)
        except Exception:
            allowed = False
        try:
            if allowed:
                cdp.send("Fetch.continueRequest", {"requestId": request_id})
                return
            state["blocked"].append(url)
            is_main = main_frame_id is None or event.get("frameId") == main_frame_id
            if event.get("resourceType") == "Document" and is_main:
                state["blocked_document"] = True
            cdp.send("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"})
        except Exception:
            # Target sudah ditutup / request sudah dibatalkan.
            pass

    cdp.on("Fetch.requestPaused", _on_paused)
    cdp.send("Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]})
    return state


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
        # Lapisan utama SSRF: semua koneksi browser context ini lewat egress proxy yang
        # me-resolve sendiri, menolak IP non-publik, dan menyambung ke IP yang sudah dicek.
        # "<-loopback>": tanpa ini Chromium mem-bypass proxy untuk localhost/127.0.0.1.
        egress_proxy = get_egress_proxy()
        context = browser.new_context(
            **build_context_options(browser),
            proxy={"server": egress_proxy.server_url, "bypass": "<-loopback>"},
            # Service worker bisa membuat request di luar jangkauan guard SSRF per halaman.
            service_workers="block",
        )
        _inject_scrapling_stealth_scripts(context)
        if cookies:
            try:
                context.add_cookies(cookies)
            except Exception:
                pass

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
            if egress_proxy.handled == proxied_before:
                # Fail closed: halaman termuat tanpa satu pun koneksi lewat proxy, berarti
                # konfigurasi proxy per-context diabaikan dan browser menyambung langsung.
                raise RuntimeError("SSRF egress proxy was bypassed; refusing to return the page")
            status_code = resp.status if resp else 200

            max_poll_s = min(20.0, max(5.0, timeout_ms / 3000.0))
            poll_interval = 0.5
            elapsed = 0.0
            cf_state = new_cloudflare_state()
            while elapsed < max_poll_s:
                raw_html = page.content()
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

            if callable(page_action):
                try:
                    page_action(page)
                except Exception:
                    pass

            raw_html = page.content()
            final_url = page.url or url
            if final_url and final_url != url:
                validate_external_url(final_url)

            return AdaptivePage(
                html=raw_html,
                url=final_url,
                domain=self.adaptive_domain or final_url,
                status=status_code,
            )
        finally:
            try:
                context.close()
            except Exception:
                pass

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
