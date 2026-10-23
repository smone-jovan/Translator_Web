import re
import urllib.parse
from typing import Optional, List, Tuple
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

from services.scrapers.base import BaseScraperAdapter, ScrapedNovelMetadata
from services.security import validate_external_url, create_safe_async_client, egress_proxies

class SFACGAdapter(BaseScraperAdapter):
    """
    Concrete adapter for scraping novel metadata and TOC from SFACG (book.sfacg.com) directly.
    """

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://book.sfacg.com/"
        }

    def extract_novel_id(self, query: str) -> Optional[int]:
        """
        Extract novel ID integer from an SFACG URL or raw string ID.
        """
        if not query:
            return None
        query_strip = query.strip()
        if query_strip.isdigit():
            return int(query_strip)
        id_match = re.search(r'/Novel/(\d+)', query_strip, re.IGNORECASE)
        if not id_match:
            id_match = re.search(r'/b/(\d+)', query_strip, re.IGNORECASE)
        if id_match:
            return int(id_match.group(1))
        return None

    async def scrape_toc(self, query: str) -> Tuple[str, List[dict]]:
        """
        Scrapes Table of Contents (TOC) / chapter list from SFACG.
        Returns (novel_title, list of {'title': str, 'url': str}).
        """
        novel_id = self.extract_novel_id(query)
        if not novel_id:
            raise ValueError(f"Could not extract a valid SFACG novel ID from: '{query}'")

        target_url = f"https://book.sfacg.com/Novel/{novel_id}/MainIndex/"
        validate_external_url(target_url)

        async with create_safe_async_client(
            headers=self.headers,
            follow_redirects=True,
            timeout=25.0
        ) as client:
            resp = await client.get(target_url)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to fetch SFACG TOC page (status {resp.status_code})")

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract clean novel title
            title_el = (
                soup.select_one(".story-title")
                or soup.select_one(".crumbs a:last-child")
                or soup.select_one("h1")
            )
            if title_el:
                for tag in title_el.select(".tag, .badge, .status"):
                    tag.decompose()
                novel_title = " ".join(title_el.text.split()).strip()
            else:
                title_tag = soup.find("title")
                raw_title = title_tag.get_text(strip=True) if title_tag else "Untitled SFACG Novel"
                novel_title = re.sub(r"目录列表.*", "", raw_title).strip() or raw_title

            chapters: List[dict] = []
            seen_urls = set()

            for a in soup.select(".catalog-list li a, .story-catalog a"):
                href = a.get("href")
                if not href or href.startswith(("#", "javascript:")):
                    continue

                if not ("/Novel/" in href or "/vip/c/" in href):
                    continue

                parsed_href = urllib.parse.urlparse(href)
                path_parts = [p for p in parsed_href.path.strip("/").split("/") if p]

                # Filter out novel homepage, TOC index, or shallow links
                if "/Novel/" in href:
                    if len(path_parts) <= 3 or "MainIndex" in path_parts:
                        continue
                elif "/vip/c/" in href:
                    if len(path_parts) < 3:
                        continue

                abs_url = urllib.parse.urljoin("https://book.sfacg.com", href)
                if abs_url in seen_urls:
                    continue
                seen_urls.add(abs_url)

                ch_title = (a.get("title") or "").strip()
                if not ch_title:
                    ch_title = a.get_text(strip=True)
                if ch_title.startswith("VIP"):
                    ch_title = ch_title[3:].strip()

                chapters.append({"title": ch_title, "url": abs_url})

            return novel_title, chapters

    async def scrape_chapter_content(self, url: str) -> Tuple[str, str]:
        """
        Scrapes chapter content from SFACG directly without Playwright.
        Returns (chapter_title, chapter_markdown).
        """
        validate_external_url(url)
        async with create_safe_async_client(
            headers=self.headers,
            follow_redirects=True,
            timeout=25.0
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to fetch SFACG chapter (status {resp.status_code})")

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract clean chapter title
            title_el = soup.select_one(".article-title") or soup.select_one("h1")
            if title_el:
                title = title_el.get_text(strip=True)
            else:
                title_tag = soup.find("title")
                raw_title = title_tag.get_text(strip=True) if title_tag else "Untitled Chapter"
                title = raw_title.split(" - ")[1] if " - " in raw_title else raw_title

            # Extract content from #ChapterBody or .article-content
            content_el = soup.select_one("#ChapterBody") or soup.select_one(".article-content")
            if not content_el:
                return title, ""

            # Check if this is a VIP chapter with preview only
            is_vip = "/vip/" in url.lower() or "VIP" in title
            raw_text = content_el.get_text(strip=True)
            if is_vip and len(raw_text) < 200:
                return title, "[VIP CHAPTER] Bab ini terkunci atau tidak dapat diakses (VIP)."

            # Extract paragraphs cleanly
            paragraphs = []
            for p in content_el.select("p"):
                p_text = p.get_text(strip=True)
                if p_text:
                    paragraphs.append(p_text)

            if not paragraphs:
                paragraphs = [line.strip() for line in content_el.get_text().split("\n") if line.strip()]

            markdown = "\n\n".join(paragraphs)
            return title, markdown

    async def get_next_chapter(self, current_url: str) -> Optional[Tuple[str, str]]:
        """
        Finds the 'Next Chapter' URL and title from the current SFACG chapter page.
        Returns (next_url, next_title) or None.
        """
        validate_external_url(current_url)
        async with create_safe_async_client(
            headers=self.headers,
            follow_redirects=True,
            timeout=25.0
        ) as client:
            resp = await client.get(current_url)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("a"):
                text = a.get_text(strip=True)
                if any(keyword in text for keyword in ["下一章", "下一页", "下一节"]):
                    href = a.get("href")
                    if href and not href.startswith(("#", "javascript:")):
                        abs_url = urllib.parse.urljoin(current_url, href)
                        if abs_url != current_url:
                            return abs_url, text
            return None

    async def scrape_metadata(self, query: str, search_by: str = "original", include_cover: bool = True) -> ScrapedNovelMetadata:
        query_strip = query.strip()
        novel_id = self.extract_novel_id(query_strip)
        if not novel_id:
            return ScrapedNovelMetadata(
                success=False,
                title="",
                original_title=query_strip,
                synopsis=f"Invalid SFACG URL or novel ID: {query_strip}"
            )

        target_url = f"https://book.sfacg.com/Novel/{novel_id}/"
        validate_external_url(target_url)

        print(f"[SFACG] Direct scraping target URL: {target_url}")

        try:
            async with AsyncSession(proxies=egress_proxies()) as client:
                resp = await client.get(target_url, headers=self.headers, impersonate="chrome110", timeout=15.0)
                if resp.status_code != 200:
                    return ScrapedNovelMetadata(
                        success=False,
                        title="",
                        original_title=query_strip,
                        synopsis=f"Failed to retrieve SFACG page (status {resp.status_code})."
                    )

                soup = BeautifulSoup(resp.text, 'html.parser')

                # 1. Title (Mandarin Hanzi, clean of tag badges)
                title_el = soup.select_one(".d-summary .title") or soup.select_one(".d-normal-banner .title") or soup.select_one(".novel-info .title") or soup.select_one("h1")
                if title_el:
                    for tag in title_el.select(".tag, .badge, .status"):
                        tag.decompose()
                    title = " ".join(title_el.text.split()).strip()
                else:
                    title = "Untitled SFACG Novel"

                # 2. Synopsis
                introduce_el = soup.select_one(".d-summary .introduce") or soup.select_one(".introduce") or soup.select_one(".novel-intro")
                synopsis = introduce_el.text.strip() if introduce_el else ""

                # 3. Genres
                genre_links = soup.select(".tag-list .tag a") or soup.select(".previous-chapter .tag-list .tag a") or soup.select(".novel-tags a")
                genres_list = [a.text.strip() for a in genre_links if a.text.strip()]
                genres_str = ", ".join(genres_list) if genres_list else ""

                # 4. Cover Image
                cover_url = None
                if include_cover:
                    cover_el = soup.select_one(".d-normal-banner .summary-pic img") or soup.select_one(".summary-pic img") or soup.select_one(".novel-cover img")
                    if cover_el:
                        cover_url = cover_el.get("src", "")
                        if cover_url and cover_url.startswith("//"):
                            cover_url = "https:" + cover_url

                # 5. Author
                author_el = soup.select_one(".author-name") or soup.select_one(".author-info") or soup.select_one("a[href*='/author/']") or soup.select_one(".novel-author") or soup.select_one("#showauthors")
                author = author_el.text.replace("作者：", "").replace("作者:", "").strip() if author_el else ""

                return ScrapedNovelMetadata(
                    success=True,
                    title=title,
                    original_title=title,
                    author=author,
                    genres=genres_str,
                    tags="",
                    synopsis=synopsis,
                    status="Ongoing",
                    status_coo="Ongoing",
                    cover_image=cover_url,
                    detail_url=target_url
                )
        except Exception as e:
            print(f"[SFACG] Scraping error: {e}")
            return ScrapedNovelMetadata(
                success=False,
                title="",
                original_title=query_strip,
                synopsis=f"Error scraping SFACG metadata: {str(e)}"
            )

