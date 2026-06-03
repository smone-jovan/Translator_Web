import re
import urllib.parse
from typing import Optional, List
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

from services.scrapers.base import BaseScraperAdapter, ScrapedNovelMetadata

class NovelUpdatesAdapter(BaseScraperAdapter):
    """
    Concrete adapter for scraping novel metadata from Novel Updates.
    Uses Google Search to find candidates and extracts metadata from search snippets.
    Direct Novel Updates access is avoided due to Cloudflare protection.
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

    def _extract_title_from_url(self, url: str) -> str:
        """Extract a readable title from a Novel Updates URL slug."""
        try:
            # Extract the slug from URL like /series/how-could-the-villainous-young-master-be-a-saintess/
            match = re.search(r'/series/([^/]+)', url)
            if match:
                slug = match.group(1)
                # Convert slug to title case
                title = slug.replace('-', ' ').title()
                return title
        except Exception:
            pass
        return ""

    async def _search_google(self, query: str) -> List[dict]:
        """
        Search Google for Novel Updates results.
        Returns list of dicts with 'url', 'title', 'snippet'.
        """
        results = []
        try:
            search_query = f"{query} site:novelupdates.com"
            encoded_query = urllib.parse.quote(search_query)
            google_url = f"https://www.google.com/search?q={encoded_query}&num=10"
            
            print(f"[NovelUpdates] Searching Google: {google_url}")
            async with AsyncSession() as client:
                resp = await client.get(google_url, headers=self.headers, impersonate="chrome120", timeout=12.0)
                if resp.status_code != 200:
                    print(f"[NovelUpdates] Google search returned status {resp.status_code}")
                    return results
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Find all search result divs
                search_divs = soup.find_all('div', class_='g')
                
                for div in search_divs:
                    link = div.find('a')
                    if not link:
                        continue
                    
                    href = link.get('href', '')
                    if 'novelupdates.com/series/' not in href:
                        continue
                    
                    # Extract title
                    title_el = div.find('h3')
                    title = title_el.text.strip() if title_el else self._extract_title_from_url(href)
                    
                    # Extract snippet
                    snippet_el = div.find('div', class_='VwiC3b') or div.find('span', class_='aCOpRe')
                    snippet = snippet_el.text.strip() if snippet_el else ""
                    
                    results.append({
                        'url': href.split('?')[0],
                        'title': title,
                        'snippet': snippet
                    })
                    
        except Exception as e:
            print(f"[NovelUpdates] Google Search failed: {e}")
        
        return results

    async def _search_yahoo(self, query: str) -> List[ScrapedNovelMetadata]:
        """Fallback search using Yahoo."""
        import urllib.parse
        from bs4 import BeautifulSoup
        import re
        
        search_query = f"{query} site:novelupdates.com"
        url = f"https://search.yahoo.com/search?p={urllib.parse.quote(search_query)}"
        print(f"[NovelUpdates] Searching Yahoo: {url}")
        
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession() as client:
                resp = await client.get(url, headers=self.headers, impersonate="chrome120", timeout=12.0)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    candidates = []
                    for a in soup.select('a'):
                        href = a.get('href', '')
                        unquoted_href = urllib.parse.unquote(href)
                        if 'novelupdates.com/series/' in unquoted_href:
                            # Extract actual NU URL from Yahoo redirect
                            match = re.search(r'RU=(https://www\.novelupdates\.com/series/[^/]+/)', unquoted_href)
                            real_url = match.group(1) if match else None
                            if not real_url:
                                print(f"DEBUG: Could not extract real_url from {unquoted_href}")
                                continue
                                
                            parent = a.find_parent('div', class_='algo') or a.find_parent('div')
                            snippet = None
                            if parent:
                                desc_el = parent.select_one('.compText') or parent.select_one('.compTitle ~ div') or parent.select_one('.fc-falcon') or parent.select_one('.fz-ms')
                                if desc_el:
                                    snippet = desc_el.text.strip()
                                    if '... ' in snippet:
                                        snippet = snippet.split('... ', 1)[-1]
                                    
                            title = self._extract_title_from_url(real_url) or query
                            
                            if not any(c.detail_url == real_url for c in candidates):
                                candidates.append(ScrapedNovelMetadata(
                                    success=True,
                                    title=title,
                                    original_title=query,
                                    synopsis=snippet,
                                    detail_url=real_url
                                ))
                    return candidates
        except Exception as e:
            print(f"[NovelUpdates] Yahoo search error: {e}")
            
        return []

    def _parse_google_snippet_metadata(self, title: str, snippet: str, url: str, query: str) -> Optional[ScrapedNovelMetadata]:
        """
        Extract metadata from Google search snippet.
        Returns ScrapedNovelMetadata if enough info found, None otherwise.
        """
        if not title and not snippet:
            return None
        
        # Clean up title - remove " | Novel Updates" suffix if present
        clean_title = re.sub(r'\s*[\|\-–]\s*Novel\s*Updates?\s*$', '', title, flags=re.IGNORECASE).strip()
        
        # Try to extract genres from snippet
        genres = None
        genre_match = re.search(r'Genres?:\s*([^\.]+)', snippet, re.IGNORECASE)
        if genre_match:
            genres = genre_match.group(1).strip()
        
        # Try to extract status from snippet
        status = None
        if 'completed' in snippet.lower():
            status = 'Completed'
        elif 'ongoing' in snippet.lower():
            status = 'Ongoing'
        
        # Extract English title from snippet if available
        # Novel Updates snippets often show: "English Title - Novel Updates"
        english_title = clean_title
        if ' - Novel Updates' in title:
            english_title = title.split(' - Novel Updates')[0].strip()
        
        return ScrapedNovelMetadata(
            success=True,
            title=english_title,
            original_title=query,
            genres=genres,
            status=status,
            synopsis=snippet[:500] if snippet else None,
            detail_url=url
        )

    async def scrape_candidates(self, query: str, search_by: str = "original", include_cover: bool = True) -> List[ScrapedNovelMetadata]:
        import asyncio
        query_strip = query.strip()
        
        # Direct URL check - extract title and use it as query
        detail_url = ""
        if "novelupdates.com/series/" in query_strip:
            detail_url = query_strip
            url_title = self._extract_title_from_url(query_strip)
            if url_title:
                query_strip = url_title
        
        # Search using Google (primary) and Yahoo (fallback)
        google_results = await self._search_google(query_strip)
        yahoo_candidates = await self._search_yahoo(query_strip)
        
        # Build candidates from Google results
        candidates = []
        seen_urls = set()
        
        for gr in google_results:
            url = gr['url']
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Try to parse metadata from snippet
            meta = self._parse_google_snippet_metadata(gr['title'], gr['snippet'], url, query_strip)
            if meta:
                candidates.append(meta)
            else:
                # Create basic metadata from URL
                url_title = self._extract_title_from_url(url)
                candidates.append(ScrapedNovelMetadata(
                    success=True,
                    title=url_title or "Unknown Title",
                    original_title=query_strip,
                    detail_url=url
                ))
        
        # Add Yahoo results as fallback
        for cand in yahoo_candidates:
            if cand.detail_url in seen_urls:
                continue
            seen_urls.add(cand.detail_url)
            candidates.append(cand)
        
        if not candidates:
            print(f"[NovelUpdates] No candidates found for '{query_strip}'")
            return []
        
        print(f"[NovelUpdates] Found {len(candidates)} candidates")
        
        # Rank by match score
        def get_match_score(r: ScrapedNovelMetadata) -> int:
            q_clean = self._clean_for_match(query_strip)
            t_clean = self._clean_for_match(r.title)
            if q_clean and t_clean and (q_clean in t_clean or t_clean in q_clean):
                return 2
            return 0
        
        candidates.sort(key=get_match_score, reverse=True)
        
        # Enforce detail_url if it was directly provided
        if detail_url:
            for c in candidates:
                c.detail_url = detail_url
        
        # Fallback if no candidates found but direct URL was provided
        if not candidates and detail_url:
            fallback_meta = ScrapedNovelMetadata(
                success=True,
                title=query_strip,
                original_title=query,
                detail_url=detail_url
            )
            candidates.append(fallback_meta)
        
        # MangaUpdates enhancement disabled per user request
        # to strictly avoid Manhwa covers/genres.
            
        return candidates[:10]



    async def scrape_metadata(self, query: str, search_by: str = "original", include_cover: bool = True) -> ScrapedNovelMetadata:
        query_strip = query.strip()
        
        # Direct URL check - extract title and use it as query
        detail_url = ""
        if "novelupdates.com/series/" in query_strip:
            detail_url = query_strip
            url_title = self._extract_title_from_url(query_strip)
            if url_title:
                query_strip = url_title
                
        # Search using Google
        google_results = await self._search_google(query_strip)
        
        if google_results:
            # Use the first (best) result
            best = google_results[0]
            meta = self._parse_google_snippet_metadata(
                best['title'], 
                best['snippet'], 
                best['url'], 
                query_strip
            )
            if meta:
                print(f"[NovelUpdates] Best match from Google: {best['title']}")
                if detail_url:
                    meta.detail_url = detail_url
                await self._enhance_metadata(meta, query_strip)
                return meta
        
        # Fallback to Yahoo Search
        yahoo_candidates = await self._search_yahoo(query_strip)
        if yahoo_candidates:
            meta = yahoo_candidates[0]
            print(f"[NovelUpdates] Fallback to Yahoo result: {meta.detail_url}")
            if detail_url:
                meta.detail_url = detail_url
            # MangaUpdates enhancement disabled per user request
            return meta
        
        # Absolute fallback if search engines fail
        if detail_url:
            meta = ScrapedNovelMetadata(
                success=True,
                title=query_strip,
                original_title=query_strip,
                detail_url=detail_url
            )
            await self._enhance_metadata(meta, query_strip)
            return meta
            
        return ScrapedNovelMetadata(
            success=False,
            title="",
            original_title=query_strip,
            synopsis=f"No results found on Novel Updates for '{query_strip}'"
        )

    async def _scrape_detail_page(self, url: str, query: str, include_cover: bool) -> ScrapedNovelMetadata:
        """Scrape detail page - now returns URL-based metadata since direct access is blocked."""
        url_title = self._extract_title_from_url(url)
        return ScrapedNovelMetadata(
            success=True,
            title=url_title or "Novel Updates Series",
            original_title=query,
            detail_url=url
        )

    async def _parse_html(self, html: str, url: str, query: str, include_cover: bool) -> ScrapedNovelMetadata:
        """Parse HTML - kept for backward compatibility but not used in current flow."""
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
