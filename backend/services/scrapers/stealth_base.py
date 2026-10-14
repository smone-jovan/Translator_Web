"""
Base adapter untuk situs web novel dengan proteksi Cloudflare Turnstile / WAF berat
menggunakan Scrapling (StealthyFetcher / AsyncStealthySession) + Adaptive DOM Parsing.
"""

from typing import Optional, List, Tuple, Callable, Any
from services.scrapers.base import BaseScraperAdapter, ScrapedNovelMetadata
from services.scrapers.novalpie import get_scraper_concurrency
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
    ):
        """
        Mengambil halaman yang dilindungi Cloudflare Turnstile/WAF menggunakan Scrapling StealthyFetcher.
        Selalu menjalankan validasi SSRF (`validate_external_url`) sebelum membuka koneksi.
        """
        validate_external_url(url)

        if not HAS_SCRAPLING:
            raise RuntimeError(
                "Scrapling belum terinstal. Jalankan dengan persetujuan user: "
                "pip install \"scrapling[fetchers]\" && scrapling install"
            )

        page = await StealthyFetcher.async_fetch(
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
        return page

    async def fetch_stealth_batch(
        self,
        urls: List[str],
        *,
        solve_cloudflare: bool = True,
        disable_resources: bool = True,
        wait_selector: Optional[str] = None,
        timeout_ms: int = 60000,
    ) -> List[Any]:
        """
        Mengambil banyak URL bab secara paralel menggunakan tab pool AsyncStealthySession
        yang menghormati batas `scraper_concurrency` (1-5 worker) pada workspace aktif.
        """
        for u in urls:
            validate_external_url(u)

        if not HAS_SCRAPLING:
            raise RuntimeError(
                "Scrapling belum terinstal. Jalankan dengan persetujuan user: "
                "pip install \"scrapling[fetchers]\" && scrapling install"
            )

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
                page = await session.fetch(u, wait_selector=wait_selector)
                results.append(page)

        return results

    @staticmethod
    def extract_clean_chapter(
        page: Any,
        title_selector: str,
        content_selector: str,
        *,
        adaptive: bool = True,
        auto_save: bool = False,
    ) -> Tuple[str, str]:
        """
        Mengekstrak judul dan isi bab bersih menggunakan Adaptive Selector Scrapling.
        Jika struktur CSS situs berubah di masa depan, `adaptive=True` akan merelokasi elemen secara otomatis.
        """
        title_nodes = page.css(title_selector, adaptive=adaptive, auto_save=auto_save)
        title = title_nodes[0].text.strip() if title_nodes else "Untitled Chapter"

        content_nodes = page.css(content_selector, adaptive=adaptive, auto_save=auto_save)
        if not content_nodes:
            return title, ""

        # Ekstrak paragraf menjadi Markdown bersih
        paragraphs = [
            p.text.strip()
            for p in content_nodes[0].css("p")
            if p.text and p.text.strip()
        ]
        if not paragraphs:
            raw_text = content_nodes[0].get_all_text(strip=True) if hasattr(content_nodes[0], "get_all_text") else ""
            paragraphs = [line.strip() for line in raw_text.splitlines() if line.strip()]

        return title, "\n\n".join(paragraphs)

    async def scrape_metadata(
        self, query: str, search_by: str = "original", include_cover: bool = True
    ) -> ScrapedNovelMetadata:
        raise NotImplementedError("Subclass harus mengimplementasikan scrape_metadata")
