"""
Base adapter untuk situs web novel dengan proteksi Cloudflare Turnstile / WAF berat
menggunakan Scrapling (StealthyFetcher / AsyncStealthySession) jika tersedia,
atau Native Adaptive Playwright Fallback + Adaptive DOM Parsing.
"""

import asyncio
from typing import Optional, List, Tuple, Callable, Any
from bs4 import BeautifulSoup

from services.scrapers.base import BaseScraperAdapter, ScrapedNovelMetadata
from services.scrapers.adaptive_dom import AdaptivePage
from services.scrapers.novalpie import (
    get_scraper_concurrency,
    _get_thread_browser,
    _inject_scrapling_stealth_scripts,
    _install_resource_shield,
    _try_solve_cloudflare_turnstile,
    _is_cloudflare_challenge,
)
from services.security import validate_external_url

try:
    from scrapling.fetchers import StealthyFetcher, AsyncStealthySession
    HAS_SCRAPLING = True
except ImportError:
    HAS_SCRAPLING = False


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
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
        )
        _inject_scrapling_stealth_scripts(context, block_webrtc=True, hide_canvas=True)
        if cookies:
            try:
                context.add_cookies(cookies)
            except Exception:
                pass

        try:
            page = context.new_page()
            if disable_resources:
                _install_resource_shield(page, disable_resources=True)
            if has_stealth:
                try:
                    sync_stealth(page, pure_js=True)
                except Exception:
                    pass

            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            status_code = resp.status if resp else 200

            max_poll_s = min(20.0, max(5.0, timeout_ms / 3000.0))
            poll_interval = 0.5
            elapsed = 0.0
            while elapsed < max_poll_s:
                raw_html = page.content()
                if _is_cloudflare_challenge(raw_html):
                    if solve_cloudflare:
                        _try_solve_cloudflare_turnstile(page)
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
    ) -> Any:
        validate_external_url(url)
        if HAS_SCRAPLING:
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
