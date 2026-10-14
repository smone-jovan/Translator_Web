import re
import threading
import time
import atexit
import asyncio
from typing import Optional, List, Tuple, Dict, Any
import httpx
from services.scrapers.base import BaseScraperAdapter, ScrapedNovelMetadata

_pw_thread_local = threading.local()
_all_active_browsers = []
_browsers_lock = threading.Lock()


def _cleanup_all_browsers():
    with _browsers_lock:
        for pw, browser in _all_active_browsers:
            try:
                browser.close()
            except Exception:
                pass
            try:
                pw.stop()
            except Exception:
                # Direct driver transport process termination fallback if cross-thread greenlet exception occurs
                try:
                    proc = getattr(getattr(getattr(pw, "_connection", None), "_transport", None), "_proc", None)
                    if proc and hasattr(proc, "poll") and proc.poll() is None:
                        proc.terminate()
                except Exception:
                    pass
        _all_active_browsers.clear()


atexit.register(_cleanup_all_browsers)


def get_scraper_concurrency(workspace: str = None) -> int:
    try:
        from database import SessionLocal, GlobalSetting
        from sqlalchemy import select
        with SessionLocal(workspace=workspace) as db:
            gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
            if gs and hasattr(gs, 'scraper_concurrency') and gs.scraper_concurrency:
                return max(1, min(5, int(gs.scraper_concurrency)))
    except Exception:
        pass
    return 2


def get_novalpie_auth_config(workspace: str = None) -> Tuple[bool, str, str, List[dict]]:
    """
    Returns (auth_enabled: bool, raw_cookie: str, auth_token: str, playwright_cookies: List[dict]).
    Reads novalpie_auth_enabled and novalpie_cookie from GlobalSetting.
    Intelligently parses:
      1. Chrome DevTools tabular copy-paste (Name \t Value \t Domain ...)
      2. Semicolon-separated cookie headers (name=value; name2=value2)
      3. Raw single token (auth_token or LOGINKEY)
    Automatically maps cookies to both novalpie.cc and novelpia.com.
    """
    try:
        from database import SessionLocal, GlobalSetting
        from sqlalchemy import select
        with SessionLocal(workspace=workspace) as db:
            gs = db.execute(select(GlobalSetting)).scalar_one_or_none()
            if gs and getattr(gs, 'novalpie_auth_enabled', 0):
                from services.ai.secrets import load_secrets
                secrets = load_secrets()
                raw = secrets.get('novalpie_cookie', '') or getattr(gs, 'novalpie_cookie', '') or ''
                raw = raw.strip()
                if raw:
                    auth_token = ""
                    pw_cookies = []
                    cookie_pairs = []

                    # 1. DevTools tab-separated table detection
                    if "\t" in raw:
                        cleaned = re.sub(r'\t(Medium|High|Low|VeryHigh|VeryLow)\t', '\n', raw)
                        for line in cleaned.splitlines():
                            m = re.match(r'([a-zA-Z0-9_\-]+)\t([^\t\r\n]+)\t(\.?[a-zA-Z0-9_\-\.]+)', line.strip())
                            if m:
                                k, v, d = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
                                if k.lower() in ("loginkey", "userkey", "auth_token", "token", "remember_web", "autologin"):
                                    auth_token = v
                                clean_domain = d.lstrip(".")
                                pw_cookies.append({"name": k, "value": v, "domain": f".{clean_domain}", "path": "/"})
                                if "novelpia" in clean_domain:
                                    pw_cookies.append({"name": k, "value": v, "domain": ".novalpie.cc", "path": "/"})
                                    pw_cookies.append({"name": k, "value": v, "domain": "images.novelpia.com", "path": "/"})
                                cookie_pairs.append(f"{k}={v}")

                    # 2. Semicolon format (name=value; ...)
                    elif "=" in raw:
                        parts = [p.strip() for p in raw.split(";") if p.strip()]
                        for part in parts:
                            if "=" in part:
                                k, v = part.split("=", 1)
                                k_s = k.strip()
                                v_s = v.strip()
                                if k_s.lower() in ("auth_token", "token", "remember_web", "loginkey", "userkey", "autologin"):
                                    auth_token = v_s
                                pw_cookies.append({"name": k_s, "value": v_s, "domain": ".novalpie.cc", "path": "/"})
                                pw_cookies.append({"name": k_s, "value": v_s, "domain": ".novelpia.com", "path": "/"})
                                cookie_pairs.append(f"{k_s}={v_s}")

                    # 3. Plain token
                    else:
                        auth_token = raw
                        pw_cookies.append({"name": "auth_token", "value": raw, "domain": ".novalpie.cc", "path": "/"})
                        pw_cookies.append({"name": "LOGINKEY", "value": raw, "domain": ".novelpia.com", "path": "/"})
                        cookie_pairs.append(f"auth_token={raw}")

                    if not auth_token and pw_cookies:
                        auth_token = pw_cookies[0]["value"]

                    final_cookie_str = "; ".join(cookie_pairs) if cookie_pairs else raw
                    return True, final_cookie_str, auth_token, pw_cookies
    except Exception as e:
        print(f"⚠️ [Novalpie Auth] Error parsing auth config: {e}")
    return False, "", "", []


def _get_thread_browser():
    """Returns a reusable thread-local Chromium browser instance to avoid launching/killing Chromium processes repeatedly."""
    now = time.time()
    if hasattr(_pw_thread_local, "browser") and _pw_thread_local.browser is not None:
        try:
            if _pw_thread_local.browser.is_connected():
                # Recycle browser if idle for more than 5 minutes
                if now - getattr(_pw_thread_local, "last_used", now) < 300:
                    _pw_thread_local.last_used = now
                    return _pw_thread_local.browser
        except Exception:
            pass
        # Clean up stale or disconnected browser
        old_browser = getattr(_pw_thread_local, "browser", None)
        old_pw = getattr(_pw_thread_local, "pw", None)
        try:
            if old_browser:
                old_browser.close()
        except Exception:
            pass
        try:
            if old_pw:
                old_pw.stop()
        except Exception:
            pass
        with _browsers_lock:
            if (old_pw, old_browser) in _all_active_browsers:
                _all_active_browsers.remove((old_pw, old_browser))
        _pw_thread_local.browser = None
        _pw_thread_local.pw = None

    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    from playwright.sync_api import sync_playwright
    print("🚀 [Playwright] Launching reusable Chromium browser instance for worker thread...")
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox"
        ]
    )
    _pw_thread_local.pw = pw
    _pw_thread_local.browser = browser
    _pw_thread_local.last_used = now
    with _browsers_lock:
        _all_active_browsers.append((pw, browser))
    return browser


class NovalpieAdapter(BaseScraperAdapter):
    """
    Concrete adapter for scraping novel metadata, Table of Contents (TOC),
    and chapter content from novalpie.cc directly via its REST API and web endpoints.
    """

    BASE_URL = "https://novalpie.cc"
    API_BASE = "https://novalpie.cc/api"

    @classmethod
    def get_semaphore(cls, workspace: str = None):
        """Returns or updates the dynamic concurrency semaphore based on GlobalSetting safely and event-loop aware."""
        concurrency = get_scraper_concurrency(workspace)
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        sem = getattr(cls, "_playwright_sem", None)
        sem_loop = getattr(cls, "_playwright_sem_loop", None)

        if sem is None or sem_loop is not current_loop:
            cls._playwright_sem = asyncio.Semaphore(concurrency)
            cls._playwright_sem_loop = current_loop
            cls._current_concurrency = concurrency
        elif getattr(cls, "_current_concurrency", 2) != concurrency:
            if not cls._playwright_sem.locked():
                cls._playwright_sem = asyncio.Semaphore(concurrency)
                cls._playwright_sem_loop = current_loop
                cls._current_concurrency = concurrency
        return cls._playwright_sem

    def __init__(self, workspace: Optional[str] = None):
        self.workspace = workspace
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ko;q=0.7",
            "Referer": "https://novalpie.cc/",
            "Origin": "https://novalpie.cc",
        }

    def get_request_headers(self) -> Dict[str, str]:
        """Returns request headers, automatically augmented with auth session cookie/token if enabled."""
        headers = dict(self.headers)
        auth_enabled, raw_cookie, auth_token, _ = get_novalpie_auth_config(self.workspace)
        if auth_enabled:
            if raw_cookie:
                headers["Cookie"] = raw_cookie if "=" in raw_cookie else f"auth_token={raw_cookie}"
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
        return headers

    def extract_novel_id(self, query: str) -> Optional[int]:
        """Extract novel ID from URL or raw number."""
        query_strip = query.strip()
        if query_strip.isdigit():
            return int(query_strip)
        
        # Match URL patterns like:
        # https://novalpie.cc/book/12345
        # https://novalpie.cc/novel/12345
        # https://novalpie.cc/read/12345/67890
        # https://novalpie.cc/12345
        patterns = [
            r'novalpie\.cc/(?:book|novel|read)/(\d+)',
            r'novalpie\.cc/(\d+)',
            r'/book/(\d+)',
            r'/novel/(\d+)',
            r'/read/(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, query_strip, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        num_match = re.search(r'(\d+)', query_strip)
        if num_match:
            return int(num_match.group(1))
        
        return None

    def extract_chapter_id(self, url: str) -> Optional[int]:
        """Extract chapter ID from URL if present."""
        match = re.search(r'/(?:read|book|novel)/\d+/(\d+)', url) or re.search(r'/chapter/(\d+)', url)
        if match:
            return int(match.group(1))
        return None

    async def scrape_metadata(self, query: str, search_by: str = "original", include_cover: bool = True) -> ScrapedNovelMetadata:
        """
        Scrapes novel metadata from novalpie.cc API.
        """
        novel_id = self.extract_novel_id(query)
        if not novel_id:
            return ScrapedNovelMetadata(
                success=False,
                title="",
                original_title=query,
                synopsis=f"Invalid novalpie.cc URL or novel ID: '{query}'"
            )

        detail_url = f"{self.API_BASE}/novels/{novel_id}/detail"
        print(f"🥧 [Novalpie] Fetching novel metadata from {detail_url}")

        try:
            async with httpx.AsyncClient(headers=self.get_request_headers(), timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(detail_url)
                if resp.status_code == 200:
                    data = resp.json()
                    item = data.get("data", data) if isinstance(data, dict) else {}

                    title = item.get("title") or item.get("name") or f"Novalpie Novel #{novel_id}"
                    # trueName holds the original Korean/source title from novelpia.com
                    original_title = item.get("trueName") or title
                    author = item.get("authorName") or item.get("author") or item.get("writer") or " SMONE"
                    synopsis = item.get("description") or item.get("intro") or item.get("synopsis") or ""

                    # Tags / Genres
                    genres = ""
                    tags_raw = item.get("tags") or item.get("genres") or item.get("categories") or []
                    if isinstance(tags_raw, list):
                        genres = ", ".join(str(t.get("name", t) if isinstance(t, dict) else t) for t in tags_raw if t)
                    elif isinstance(tags_raw, str):
                        genres = tags_raw

                    # Cover — prefer photoTrueUrl (high-res) over photoUrl (thumbnail)
                    cover_image = None
                    if include_cover:
                        cover_image = (
                            item.get("photoTrueUrl") or item.get("photoUrl")
                            or item.get("cover_image") or item.get("cover")
                            or item.get("thumbnail") or item.get("image_url")
                        )
                        if cover_image and cover_image.startswith("//"):
                            cover_image = "https:" + cover_image
                        elif cover_image and not cover_image.startswith("http"):
                            cover_image = f"{self.BASE_URL}/{cover_image.lstrip('/')}"

                    # Status: API has no dedicated status field; derive from 'spans' badge text
                    # e.g. "PLUS 独家 完结" → Completed, otherwise Ongoing
                    spans = item.get("spans") or ""
                    if "完结" in spans:
                        status = "Completed"
                    elif "连载" in spans or item.get("status"):
                        status = item.get("status") or "Ongoing"
                    else:
                        status = "Ongoing"

                    return ScrapedNovelMetadata(
                        success=True,
                        title=title,
                        original_title=original_title,
                        author=author,
                        genres=genres,
                        tags=genres,
                        synopsis=synopsis,
                        status=status,
                        status_coo=status,
                        cover_image=cover_image,
                        detail_url=f"{self.BASE_URL}/book/{novel_id}"
                    )
                else:
                    return ScrapedNovelMetadata(
                        success=False,
                        title="",
                        original_title=query,
                        synopsis=f"Failed to fetch novalpie.cc metadata (status code: {resp.status_code})"
                    )
        except Exception as e:
            print(f"⚠️ [Novalpie] Error scraping metadata for ID {novel_id}: {e}")
            return ScrapedNovelMetadata(
                success=False,
                title="",
                original_title=query,
                synopsis=f"Network error accessing novalpie.cc: {str(e)}"
            )

    async def scrape_candidates(self, query: str, search_by: str = "original", include_cover: bool = True) -> List[ScrapedNovelMetadata]:
        res = await self.scrape_metadata(query, search_by=search_by, include_cover=include_cover)
        return [res] if res.success else []

    async def scrape_toc(self, query: str) -> Tuple[str, List[dict]]:
        """
        Scrapes the Table of Contents (TOC) / list of chapters from novalpie.cc.
        Returns (novel_title, list of {'title': str, 'url': str}).
        """
        novel_id = self.extract_novel_id(query)
        if not novel_id:
            raise ValueError(f"Could not extract a valid novel ID from: '{query}'")

        # 1. Fetch metadata for title
        meta = await self.scrape_metadata(str(novel_id))
        novel_title = meta.title if meta.success and meta.title else f"Novalpie Novel #{novel_id}"

        # 2. Fetch chapter list
        toc_url = f"{self.API_BASE}/novels/{novel_id}/chapters"
        print(f"🥧 [Novalpie] Fetching TOC from {toc_url}")

        chapters: List[dict] = []
        try:
            async with httpx.AsyncClient(headers=self.get_request_headers(), timeout=25.0, follow_redirects=True) as client:
                resp = await client.get(toc_url)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_chapters = []
                    if isinstance(data, list):
                        raw_chapters = data
                    elif isinstance(data, dict):
                        raw_chapters = data.get("chapters") or data.get("data") or data.get("items") or []

                    for idx, ch in enumerate(raw_chapters):
                        ch_id = ch.get("id") or ch.get("chapter_id") or (idx + 1)
                        ch_num = ch.get("chapter_number") or ch.get("chapterNumber") or (idx + 1)
                        ch_title = ch.get("title") or ch.get("name") or f"Chapter {ch_num}"
                        
                        clean_title = str(ch_title).strip()
                        if not clean_title.startswith(("第", "EP", "Chapter", "Ch.", "Prologue", "Epilogue", "Side")):
                            clean_title = f"第 {ch_num} 章 {clean_title}"

                        read_url = f"{self.BASE_URL}/book/{novel_id}/{ch_id}"
                        chapters.append({
                            "title": clean_title,
                            "url": read_url,
                            "order": idx,
                            "chapter_id": ch_id,
                            "is_vip": bool(ch.get("is_vip", False)),
                            "update_time": ch.get("updateTime") or ch.get("updatedAt") or ch.get("createdAt") or ""
                        })
        except Exception as e:
            print(f"⚠️ [Novalpie] Error fetching TOC for novel {novel_id}: {e}")

        return novel_title, chapters

    async def get_next_chapter(self, current_chapter_url: str) -> Optional[Tuple[str, str]]:
        """
        Given a Novalpie chapter URL, returns (next_chapter_url, next_chapter_title)
        by consulting the novel TOC. Returns None if at the last chapter or if novel not found.
        """
        novel_id = self.extract_novel_id(current_chapter_url)
        curr_ch_id = self.extract_chapter_id(current_chapter_url)
        if not novel_id or not curr_ch_id:
            return None

        _, chapters = await self.scrape_toc(f"https://novalpie.cc/book/{novel_id}")
        if not chapters:
            return None

        for idx, ch in enumerate(chapters):
            ch_url = ch.get("url", "")
            ch_id = self.extract_chapter_id(ch_url)
            if ch_id == curr_ch_id:
                if idx + 1 < len(chapters):
                    next_ch = chapters[idx + 1]
                    return next_ch.get("url", ""), next_ch.get("title", f"Chapter {idx + 2}")
                break
        return None

    async def get_remaining_chapters(self, current_chapter_url: str) -> Tuple[Optional[ScrapedNovelMetadata], List[Dict[str, Any]]]:
        """
        Given a Novalpie chapter URL, fetches novel metadata and all chapters following the current chapter.
        Returns (metadata, remaining_chapters_list).
        """
        novel_id = self.extract_novel_id(current_chapter_url)
        curr_ch_id = self.extract_chapter_id(current_chapter_url)
        if not novel_id:
            return None, []

        book_url = f"https://novalpie.cc/book/{novel_id}"
        meta = await self.scrape_metadata(book_url)
        _, chapters = await self.scrape_toc(book_url)
        if not chapters:
            return meta, []

        if not curr_ch_id:
            return meta, chapters

        for idx, ch in enumerate(chapters):
            ch_url = ch.get("url", "")
            ch_id = self.extract_chapter_id(ch_url)
            if ch_id == curr_ch_id:
                return meta, chapters[idx + 1:]

        return meta, chapters

    async def scrape_chapter_content(self, url: str) -> Tuple[str, str]:
        """
        Scrapes original chapter content given a novalpie chapter URL.
        Returns (chapter_title, content_markdown).
        """
        novel_id = self.extract_novel_id(url)
        chapter_id = self.extract_chapter_id(url)
        
        if not novel_id or not chapter_id:
            novel_id = novel_id or 0
            chapter_id = chapter_id or self.extract_novel_id(url) or 0

        direct_url = url if url.startswith("http") else f"{self.BASE_URL}/book/{novel_id}/{chapter_id}"
        print(f"🥧 [Novalpie] Fetching chapter content directly via Playwright for {direct_url}")

        title = f"Chapter {chapter_id}"
        content = ""

        try:
            def _run_playwright_sync(target_url: str) -> str:
                try:
                    from playwright_stealth import sync_stealth
                    has_stealth = True
                except ImportError:
                    has_stealth = False
                    
                max_retries = 3
                last_err = None
                for attempt in range(1, max_retries + 1):
                    browser = _get_thread_browser()
                    context = browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    )
                    auth_enabled, raw_cookie, auth_token, pw_cookies = get_novalpie_auth_config(self.workspace)
                    if auth_enabled and pw_cookies:
                        try:
                            context.add_cookies(pw_cookies)
                            print(f"🍪 [Novalpie Auth] Injected {len(pw_cookies)} cookies into Playwright context.")
                        except Exception as ce:
                            print(f"⚠️ [Novalpie Auth] Cookie injection failed: {ce}")
                    if auth_enabled and auth_token:
                        try:
                            escaped_token = auth_token.replace('"', '\\"').replace("'", "\\'")
                            context.add_init_script(f"""
                                try {{
                                    localStorage.setItem("auth_token", "{escaped_token}");
                                    // Force reader settings to always request and render full chapter images
                                    const currentSettings = JSON.parse(localStorage.getItem("readerSettings") || "{{}}");
                                    currentSettings.showImages = true;
                                    localStorage.setItem("readerSettings", JSON.stringify(currentSettings));
                                }} catch(e) {{}}
                            """)
                        except Exception as se:
                            print(f"⚠️ [Novalpie Auth] Init script injection failed: {se}")
                    try:
                        page = context.new_page()
                        if auth_enabled:
                            def _spoof_user_profile(route):
                                try:
                                    resp = route.fetch()
                                    data = resp.json()
                                    if isinstance(data, dict):
                                        user_obj = data.get("data") if isinstance(data.get("data"), dict) else data
                                        if isinstance(user_obj, dict):
                                            user_obj["role"] = "admin"
                                            user_obj["is_adult"] = True
                                            user_obj["created_at"] = "2020-01-01T00:00:00.000000Z"
                                        route.fulfill(response=resp, body=json.dumps(data))
                                        return
                                except Exception:
                                    pass
                                route.continue_()

                            try:
                                page.route("**/api/**/users/me*", _spoof_user_profile)
                            except Exception:
                                pass

                        if has_stealth:
                            sync_stealth(page, pure_js=True)
                        
                        print(f"🚀 [Playwright Context] Opening tab for {target_url} (Percobaan {attempt}/{max_retries}, Stealth: {has_stealth})...")
                        page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
                        
                        # Adaptive State Polling: Finish immediately when content is decrypted (~4-5s),
                        # but retain up to 20s ceiling for slower Cloudflare Turnstile challenges.
                        max_poll_seconds = 20.0
                        poll_interval = 0.4
                        elapsed = 0.0
                        raw_html = ""

                        while elapsed < max_poll_seconds:
                            raw_html = page.content()

                            # If actively in Cloudflare Turnstile challenge, keep polling
                            if "Just a moment..." in raw_html or "cf-browser-verification" in raw_html:
                                page.wait_for_timeout(int(poll_interval * 1000))
                                elapsed += poll_interval
                                continue

                            # Early abort if fatal rate limit or error is rendered in DOM
                            if "请求过于频繁" in raw_html or "加载章节内容失败" in raw_html:
                                if "获取密钥失败: 403" in raw_html or "403" in raw_html:
                                    raise Exception("Novalpie 403: Gagal memperoleh kunci bab atau membutuhkan akun.")
                                raise Exception("Novalpie rate limit atau gagal memuat konten bab.")

                            # Check if real chapter content has finished decrypting
                            p_title, p_content = self._parse_chapter_html(raw_html, chapter_id=chapter_id)
                            if len(p_content) > 100 and "正在准备内容" not in p_content and "加载中" not in p_content:
                                print(f"⚡ [Playwright Context] Bab terdekripsi siap dalam {elapsed:.2f}s!")
                                try:
                                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                    page.wait_for_timeout(400)
                                    raw_html = page.content()
                                except Exception:
                                    pass
                                break

                            page.wait_for_timeout(int(poll_interval * 1000))
                            elapsed += poll_interval

                        if "Just a moment..." in raw_html or "cf-browser-verification" in raw_html or "Enable JavaScript and cookies to continue" in raw_html or "cloudflare" in raw_html.lower():
                            if "Ray ID:" in raw_html:
                                raise Exception("Cloudflare Turnstile blocked the request.")

                        if "请求过于频繁" in raw_html or "加载章节内容失败" in raw_html:
                            raise Exception("Novalpie rate limit detected in page (请求过于频繁).")
                        
                        print(f"✅ [Playwright Context] Finished extracting {target_url} on attempt {attempt}")
                        return raw_html
                    except Exception as err:
                        last_err = err
                        print(f"⚠️ [Playwright Percobaan {attempt}/{max_retries}] Gagal untuk {target_url}: {err}")
                        if attempt < max_retries:
                            time.sleep(attempt * 2)
                    finally:
                        try:
                            context.close()
                        except Exception:
                            pass
                
                print(f"❌ [Playwright Context] Seluruh {max_retries} percobaan gagal untuk {target_url}: {last_err}")
                return ""

            sem = self.get_semaphore(self.workspace)
            async with sem:
                raw_html = await asyncio.to_thread(_run_playwright_sync, direct_url)
            if raw_html:
                parsed_title, parsed_content = self._parse_chapter_html(raw_html, chapter_id=chapter_id)
                if parsed_title:
                    title = parsed_title
                if parsed_content:
                    content = parsed_content
        except Exception as e:
            print(f"⚠️ [Novalpie] Error scraping chapter {chapter_id} via Playwright: {e}")

        return title, content

    def _parse_chapter_html(self, raw_html: str, chapter_id: Optional[int] = None) -> Tuple[str, str]:
        """
        Extracts clean chapter markdown and title from Novalpie reader DOM.
        Targets the specific chapter container (#chapter-{chapter_id}) to prevent cross-chapter bleeding,
        converts illustrations into markdown images, and strips Vue boilerplate.
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw_html, "html.parser")

        target = None
        if chapter_id:
            target = soup.find("div", id=f"chapter-{chapter_id}") or soup.find("div", attrs={"data-chapter-id": str(chapter_id)})

        if not target:
            target = soup.find("article", class_="reader-content") or soup.find("article") or soup

        # Extract title from h2 or title tag
        title = "Untitled"
        h2 = target.find("h2")
        if h2 and h2.get_text(strip=True):
            title = h2.get_text(strip=True)
        else:
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

        # Process illustrations into markdown images BEFORE decomposing wrappers
        for img in target.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            alt = img.get("alt") or "插图"
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/") and not src.startswith("//"):
                src = f"https://novalpie.cc{src}"

            # Normalize Novalpie / Cloudflare R2 / Novelkit / Freenovel CDN aliases (from Nuxt reader po() function)
            if "photo.1695ffc38d5faf9827f7fbd055757d56.r2.cloudflarestorage.com" in src:
                src = src.replace("https://photo.1695ffc38d5faf9827f7fbd055757d56.r2.cloudflarestorage.com/", "https://jpg.freenovel.sbs/")
            if "novelkit.top/images" in src:
                src = src.replace("https://novelkit.top/images/", "https://jpg.freenovel.sbs/")
            if "jpg.freenovel.sbs" in src:
                m_hash = re.search(r'jpg\.freenovel\.sbs/([^"\'\)\s]+)', src)
                if m_hash:
                    f_name = m_hash.group(1)
                    prefix = f_name[:2]
                    src = f"https://images.novelpia.com/imagebox/{prefix}/{f_name}"

            allowed_domains = ("novelpia.com", "novalpie.cc", "freenovel.sbs", "cloudflarestorage.com", "novelkit.top")
            is_valid_img = any(d in src for d in allowed_domains) or bool(re.search(r'\.(?:jpg|jpeg|png|webp|gif|file)(?:\?|$)', src, re.I))

            if src and is_valid_img:
                wrapper = img.find_parent(class_="image-wrapper")
                if wrapper:
                    wrapper.replace_with(f"\n\n![{alt}]({src})\n\n")
                else:
                    img.replace_with(f"\n\n![{alt}]({src})\n\n")

        # Decompose comments, navigation, placeholders, separators
        for el in target.find_all(class_=re.compile(r"(chapter-comments|comment-section|chapter-separator|loading-placeholder|error-placeholder|spinner)", re.I)):
            el.decompose()

        for tag in target.find_all(["button", "script", "style", "nav", "footer", "svg"]):
            tag.decompose()

        # Handle linebreaks
        for br in target.find_all("br"):
            br.replace_with("\n")

        raw_text = target.get_text()

        # Resolve [[img:hash]] placeholders (Novalpie illustration placeholder pattern)
        def _replace_img_placeholder(match):
            h = match.group(1).strip()
            prefix = h[:2]
            return f"\n\n![插图](https://images.novelpia.com/imagebox/{prefix}/{h})\n\n"

        raw_text = re.sub(r'\[\[(?:img|image):([a-zA-Z0-9_\-\.]+)\]\]', _replace_img_placeholder, raw_text, flags=re.I)

        # Resolve [图片: URL] or [图片 URL] placeholders (Novalpie export pattern from e4j1Urtp.js)
        def _replace_tupian_placeholder(match):
            u = match.group(1).strip()
            if u.startswith("//"):
                u = "https:" + u
            elif u.startswith("/") and not u.startswith("//"):
                u = f"https://novalpie.cc{u}"
            if "jpg.freenovel.sbs" in u:
                m_h = re.search(r'jpg\.freenovel\.sbs/([^"\'\)\s]+)', u)
                if m_h:
                    fn = m_h.group(1)
                    u = f"https://images.novelpia.com/imagebox/{fn[:2]}/{fn}"
            return f"\n\n![插图]({u})\n\n"

        raw_text = re.sub(r'\[图片(?:[:：]|\s)*?(https?://[^\s\]]+|//[^\s\]]+|/[^\s\]]+)\]', _replace_tupian_placeholder, raw_text, flags=re.I)

        # Resolve raw image URLs pasted in quotes or plaintext (e.g. “https://images.novelpia.com/...”)
        def _replace_raw_image_url(match):
            m_full = match.group(0)
            if m_full.startswith("]("):
                return m_full
            u = (match.group(1) or match.group(2) or "").strip()
            if not u:
                return m_full
            if "jpg.freenovel.sbs" in u:
                m_h = re.search(r'jpg\.freenovel\.sbs/([^"\'\)\s]+)', u)
                if m_h:
                    fn = m_h.group(1)
                    u = f"https://images.novelpia.com/imagebox/{fn[:2]}/{fn}"
            return f"\n\n![插图]({u})\n\n"

        raw_text = re.sub(
            r'(?:\]\([^)]+\)|["\'“”‘’]\s*(https?://[^\s"\'“”‘’<>\)]+\.(?:jpg|jpeg|png|webp|gif|file)[^\s"\'“”‘’<>\)]*)\s*["\'“”‘’]|(?<!\]\()(https?://[^\s"\'“”‘’<>\)]+\.(?:jpg|jpeg|png|webp|gif|file)[^\s"\'“”‘’<>\)]*))',
            _replace_raw_image_url,
            raw_text,
            flags=re.I
        )

        lines = []
        for line in raw_text.splitlines():
            l_strip = line.strip()
            # Strip Vue UI artifacts
            if l_strip in ("封面折叠", "图片加载中...", "图片加载失败", "⚠️"):
                continue
            lines.append(line)

        content = "\n".join(lines)
        content = re.sub(r'\n{3,}', '\n\n', content).strip()

        if "请求过于频繁" in content or "加载章节内容失败" in content:
            print(f"⚠️ [Novalpie] Rate limit text detected in parsed chapter content: {content[:60]}")
            return title, ""

        return title, content

    def _clean_content(self, raw_text: str) -> str:
        """Normalize linebreaks, strip ads/watermarks, preserve images, and format clean markdown."""
        from bs4 import BeautifulSoup
        if "<" in raw_text and ">" in raw_text:
            soup = BeautifulSoup(raw_text, "html.parser")
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                alt = img.get("alt") or "插图"
                if src:
                    img.replace_with(f"\n\n![{alt}]({src})\n\n")
            for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            for br in soup.find_all("br"):
                br.replace_with("\n")
            text = soup.get_text()
        else:
            text = raw_text

        lines = []
        for line in text.splitlines():
            l_strip = line.strip()
            if l_strip in ("封面折叠", "图片加载中...", "图片加载失败", "⚠️"):
                continue
            lines.append(line)

        text = "\n".join(lines)
        text = re.sub(r'\r\n|\r', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
