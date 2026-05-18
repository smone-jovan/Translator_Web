import re
from typing import Optional
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

from services.scrapers.base import BaseScraperAdapter, ScrapedNovelMetadata

class SFACGAdapter(BaseScraperAdapter):
    """
    Concrete adapter for scraping novel metadata from SFACG (book.sfacg.com) directly.
    """
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://book.sfacg.com/"
        }

    async def scrape_metadata(self, query: str, search_by: str = "original", include_cover: bool = True) -> ScrapedNovelMetadata:
        query_strip = query.strip()
        sfacg_url = query_strip
        
        # Check if query is just an ID
        if sfacg_url.isdigit():
            sfacg_url = f"https://book.sfacg.com/Novel/{sfacg_url}/"
        elif not sfacg_url.startswith(("http://", "https://")):
            # Fallback if messy input
            num_match = re.search(r'(\d+)', sfacg_url)
            if num_match:
                sfacg_url = f"https://book.sfacg.com/Novel/{num_match.group(1)}/"
            else:
                return ScrapedNovelMetadata(
                    success=False,
                    title="",
                    original_title=query_strip,
                    synopsis=f"Invalid SFACG URL or novel ID: {query_strip}"
                )
                
        # Parse novel ID for normalization
        novel_id = None
        id_match = re.search(r'/Novel/(\d+)', sfacg_url, re.IGNORECASE)
        if not id_match:
            id_match = re.search(r'/b/(\d+)', sfacg_url, re.IGNORECASE)
        if id_match:
            novel_id = id_match.group(1)
            
        target_url = f"https://book.sfacg.com/Novel/{novel_id}/" if novel_id else sfacg_url
        print(f"🍍 [SFACG] Direct scraping target URL: {target_url}")
        
        try:
            async with AsyncSession() as client:
                resp = await client.get(target_url, headers=self.headers, impersonate="chrome110", timeout=15.0, verify=False)
                if resp.status_code != 200:
                    return ScrapedNovelMetadata(
                        success=False,
                        title="",
                        original_title=query_strip,
                        synopsis=f"Failed to retrieve SFACG page (status {resp.status_code})."
                    )
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # 1. Title (Mandarin Hanzi)
                title_el = soup.select_one(".d-summary .title") or soup.select_one(".d-normal-banner .title") or soup.select_one(".novel-info .title") or soup.select_one("h1")
                title = title_el.text.strip() if title_el else "Untitled SFACG Novel"
                
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
            print(f"❌ [SFACG] Scraping error: {e}")
            return ScrapedNovelMetadata(
                success=False,
                title="",
                original_title=query_strip,
                synopsis=f"Error scraping SFACG metadata: {str(e)}"
            )
