import re
import urllib.parse
from typing import Optional, List
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

from services.scrapers.base import BaseScraperAdapter, ScrapedNovelMetadata

class NovelUpdatesAdapter(BaseScraperAdapter):
    """
    Concrete adapter for scraping novel metadata from Novel Updates.
    Supports searching by original/translated titles and direct URL loading.
    """
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/"
        }

    def _clean_for_match(self, s: str) -> str:
        if not s:
            return ""
        return "".join(c for c in s.lower() if c.isalnum() or '\u4e00' <= c <= '\u9fff')

    def _is_match(self, query_title: str, orig_title: str, official: str, assoc_names: List[str]) -> bool:
        q_clean = self._clean_for_match(query_title)
        o_clean = self._clean_for_match(orig_title)
        off_clean = self._clean_for_match(official)
        
        def overlap_match(s1: str, s2: str) -> bool:
            if not s1 or not s2:
                return False
            if s1 in s2 or s2 in s1:
                return True
            # Character overlap for Chinese characters
            cn1 = [c for c in s1 if '\u4e00' <= c <= '\u9fff']
            if cn1:
                cn2 = [c for c in s2 if '\u4e00' <= c <= '\u9fff']
                intersect = set(cn1).intersection(set(cn2))
                if len(cn1) > 0 and len(intersect) / len(cn1) >= 0.5:
                    return True
            return False

        # Check official title
        if overlap_match(q_clean, off_clean) or (o_clean and overlap_match(o_clean, off_clean)):
            return True
        
        # Check associated names
        for assoc in assoc_names:
            assoc_clean = self._clean_for_match(assoc)
            if overlap_match(q_clean, assoc_clean) or (o_clean and overlap_match(o_clean, assoc_clean)):
                return True
                
        return False

    async def scrape_metadata(self, query: str, search_by: str = "original", include_cover: bool = True) -> ScrapedNovelMetadata:
        query_strip = query.strip()
        
        # Direct URL check
        if "novelupdates.com/series/" in query_strip:
            return await self._scrape_detail_page(query_strip, query_strip, include_cover)
            
        candidates = []
        
        # Try Yahoo Search first
        try:
            async with AsyncSession() as client:
                search_query = f"{query_strip} site:novelupdates.com"
                encoded_query = urllib.parse.quote(search_query)
                yahoo_url = f"https://search.yahoo.com/search?p={encoded_query}"
                
                print(f"🔍 [NovelUpdates] Searching Yahoo Search: {yahoo_url}")
                resp = await client.get(yahoo_url, headers=self.headers, impersonate="chrome110", timeout=12.0, verify=False)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    links = soup.find_all('a')
                    for link in links:
                        href = link.get('href', '')
                        target_url = None
                        if "novelupdates.com/series/" in href:
                            target_url = href
                        elif "r.search.yahoo.com" in href and "RU=" in href:
                            try:
                                decoded = urllib.parse.unquote(href.split("RU=", 1)[1].split("/RK=", 1)[0])
                                if "novelupdates.com/series/" in decoded:
                                    target_url = decoded
                            except Exception:
                                pass
                        
                        if target_url and "/series/" in target_url:
                            clean_url = target_url.split("?")[0].split("&")[0].split("/RS=")[0]
                            if clean_url not in candidates:
                                candidates.append(clean_url)
        except Exception as e:
            print(f"⚠️ [NovelUpdates] Yahoo Search failed or timed out: {e}")

        # Fallback to direct Novel Updates search
        if not candidates:
            try:
                encoded_title = urllib.parse.quote(query_strip)
                search_url = f"https://www.novelupdates.com/?s={encoded_title}"
                print(f"🔍 [NovelUpdates] Falling back to direct Novel Updates Search: {search_url}")
                async with AsyncSession() as client:
                    resp = await client.get(search_url, headers=self.headers, impersonate="chrome110", timeout=12.0)
                    if resp.status_code == 200:
                        final_url = str(resp.url)
                        if "/series/" in final_url:
                            candidates.append(final_url.split("?")[0])
                        else:
                            soup = BeautifulSoup(resp.text, 'html.parser')
                            search_results = soup.select(".search_title a")
                            if not search_results:
                                search_results = soup.select(".w-blog-entry-title a")
                            if not search_results:
                                search_results = [a for a in soup.find_all('a') if a.get('href') and "/series/" in a.get('href')]
                            
                            for sr in search_results:
                                href = sr.get('href', '').split("?")[0]
                                if href and href not in candidates:
                                    candidates.append(href)
            except Exception as e:
                print(f"⚠️ [NovelUpdates] Direct search failed: {e}")

        if not candidates:
            return ScrapedNovelMetadata(
                success=False,
                title="",
                original_title=query_strip,
                synopsis=f"No candidates found on Novel Updates for '{query_strip}'"
            )

        print(f"📋 [NovelUpdates] Found {len(candidates)} candidates. Cross-checking...")
        matched_detail_url = None
        detail_html = None
        first_candidate_html = None
        first_candidate_url = candidates[0]
        
        async with AsyncSession() as client:
            for cand_url in candidates[:5]:
                print(f"🕵️ Checking candidate: {cand_url}")
                try:
                    resp = await client.get(cand_url, headers=self.headers, impersonate="chrome110", timeout=10.0)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        
                        # Official Title
                        official_title = ""
                        title_el = soup.select_one(".seriestitlenu") or soup.select_one(".seriestitle span") or soup.select_one(".seriestitle")
                        if title_el:
                            official_title = title_el.text.strip()
                            
                        # Associated Names
                        associated_names = []
                        assoc_el = soup.select_one("#editassociated")
                        if assoc_el:
                            html_content = str(assoc_el)
                            html_content = html_content.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
                            clean_soup = BeautifulSoup(html_content, 'html.parser')
                            associated_names = [line.strip() for line in clean_soup.text.split("\n") if line.strip()]
                            
                        if not first_candidate_html:
                            first_candidate_html = resp.text
                            first_candidate_url = cand_url
                            
                        if self._is_match(query_strip, query_strip, official_title, associated_names):
                            print(f"🎯 Verified Match found: {cand_url}!")
                            matched_detail_url = cand_url
                            detail_html = resp.text
                            break
                except Exception as ex:
                    print(f"   ⚠️ Error checking candidate {cand_url}: {ex}")
                    continue

        if not matched_detail_url:
            if first_candidate_html:
                print(f"⚠️ No exact match verified. Falling back to first candidate: {first_candidate_url}")
                matched_detail_url = first_candidate_url
                detail_html = first_candidate_html
            else:
                return ScrapedNovelMetadata(
                    success=False,
                    title="",
                    original_title=query_strip,
                    synopsis="Failed to retrieve detail pages for matched candidates."
                )

        return await self._parse_html(detail_html, matched_detail_url, query_strip, include_cover)

    async def _scrape_detail_page(self, url: str, query: str, include_cover: bool) -> ScrapedNovelMetadata:
        try:
            async with AsyncSession() as client:
                resp = await client.get(url, headers=self.headers, impersonate="chrome110", timeout=15.0)
                if resp.status_code != 200:
                    return ScrapedNovelMetadata(
                        success=False,
                        title="",
                        original_title=query,
                        synopsis=f"Failed to load Novel Updates direct URL (status {resp.status_code})"
                    )
                return await self._parse_html(resp.text, url, query, include_cover)
        except Exception as e:
            return ScrapedNovelMetadata(
                success=False,
                title="",
                original_title=query,
                synopsis=f"Error direct loading Novel Updates series URL: {e}"
            )

    async def _parse_html(self, html: str, url: str, query: str, include_cover: bool) -> ScrapedNovelMetadata:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Official Title
        official_title = "Untitled Series"
        title_el = soup.select_one(".seriestitlenu") or soup.select_one(".seriestitle span") or soup.select_one(".seriestitle")
        if title_el:
            official_title = title_el.text.strip()
            
        # Genres
        genres_list = [a.text.strip() for a in soup.select("#seriesgenre a")]
        genres_str = ", ".join(genres_list) if genres_list else None
        
        # Tags
        tags_list = [a.text.strip() for a in soup.select("#showtags a") or soup.select("#seriestags a")]
        tags_str = ", ".join(tags_list) if tags_list else None
        
        # Synopsis
        synopsis_str = None
        synopsis_el = soup.select_one("#editdescription")
        if synopsis_el:
            synopsis_str = synopsis_el.text.strip()
            
        # Author
        author_str = None
        author_el = soup.select_one("#showauthors") or soup.select_one(".author") or soup.select_one("a[href*='/author/']")
        if author_el:
            author_str = author_el.text.strip()
            
        # COO & Status
        status_coo_str = None
        coo_el = soup.select_one("#editstatus")
        if coo_el:
            lines = [line.replace("\r", "").strip() for line in coo_el.text.split("\n")]
            status_coo_str = ", ".join([l for l in lines if l])
            
        status_str = None
        translated_el = soup.select_one("#showtranslated") or soup.select_one("#edittranslated")
        if translated_el:
            status_str = f"Completely Translated: {translated_el.text.strip()}"
                        
        # Cover Image
        cover_img_url = None
        if include_cover:
            img_el = soup.select_one(".seriesimg img")
            if img_el and img_el.get('src'):
                cover_img_url = img_el['src']
                if not cover_img_url.startswith("http"):
                    cover_img_url = "https:" + cover_img_url if cover_img_url.startswith("//") else cover_img_url

        return ScrapedNovelMetadata(
            success=True,
            title=official_title,
            original_title=query,
            author=author_str,
            genres=genres_str,
            tags=tags_str,
            synopsis=synopsis_str,
            status=status_str,
            status_coo=status_coo_str,
            cover_image=cover_img_url,
            detail_url=url
        )
