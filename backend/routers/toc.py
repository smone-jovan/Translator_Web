import re
import urllib.parse
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from database import get_db, Thread, Chapter, resolve_workspace, get_db_workspace
from services.scrapers.adaptive_dom import extract_universal_metadata

router = APIRouter(prefix="/api", tags=["Scraping", "TOC"])

class TOCScrapeRequest(BaseModel):
    url: str

class TOCChapterInfo(BaseModel):
    title: str
    url: str

class TOCScrapeResponse(BaseModel):
    title: str
    chapters: List[TOCChapterInfo]

class TOCBulkImportRequest(BaseModel):
    thread_id: Optional[int] = None
    title: Optional[str] = None
    base_url: Optional[str] = None
    genres: Optional[str] = None
    chapters: List[TOCChapterInfo]


_CHAPTER_TEXT_RE = re.compile(
    r"(?:"
    r"第\s*[0-9零一二三四五六七八九十百千万〇两]+\s*[章节回话話集卷篇幕]|"
    r"^(?:chapter|ch\.?|episode|ep\.?)\s*\d+|"
    r"^\d+\s*(?:화|장|편|話|章|节|節)|"
    r"^\d{1,4}\s*[.、:：\-—]\s*\S+|"
    r"^(?:序章|楔子|引子|尾声|尾聲|番外|番外編|后记|後記|幕間|프롤로그|에필로그|외전|プロローグ|エピローグ|prologue|epilogue|interlude|side\s*story)"
    r")",
    re.IGNORECASE,
)

_CHAPTER_PATH_RE = re.compile(
    r"(?:/(?:read|chapter|chapters|ep|episode|episodes|txt|viewer|view|archive)/|\d+[_/-]\d+\.html?$)",
    re.IGNORECASE,
)

_TOC_NAV_EXACT_LABELS = frozenset({
    "上一章", "下一章", "上一页", "下一页", "上一頁", "下一頁", "目录", "目錄",
    "返回目录", "章节目录", "加入书架", "投推荐票", "推荐票", "书架", "首页",
    "登录", "注册", "报错", "トップ", "目次", "次へ", "前へ", "이전화", "다음화",
    "prev", "next", "previous", "next chapter", "previous chapter", "home",
})

_TOC_FOLLOW_KEYWORDS = (
    "/MainIndex/",
    "/catalog",
    "/chapters",
    "目录",
    "目錄",
    "全部章节",
    "章节目录",
    "完整目录",
    "查看目录",
    "点击阅读",
    "开始阅读",
    "전체회차",
    "目次",
    "table of contents",
)


def _same_site_host(netloc_a: str, netloc_b: str) -> bool:
    a = (netloc_a or "").split(":")[0].lower()
    b = (netloc_b or "").split(":")[0].lower()
    if a.startswith("www."):
        a = a[4:]
    if b.startswith("www."):
        b = b[4:]
    if not a or not b:
        return False
    return a == b or a.endswith(f".{b}") or b.endswith(f".{a}")


_CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}
_TITLE_NUM_ARABIC_RE = re.compile(r"第\s*(\d+)\s*[章节話话回]|(?:chapter|ch\.?|bab)\s*(\d+)", re.IGNORECASE)
_TITLE_NUM_CN_RE = re.compile(r"第\s*([零〇一二两三四五六七八九十百千]+)\s*[章节話话回]")
_TITLE_NUM_AFTER_VOLUME_RE = re.compile(r"[卷部]\s*(\d+)")
_TITLE_NUM_LEADING_RE = re.compile(r"^\s*(\d+)")
_MIN_ORDER_PAIRS = 3
_DESCENDING_RATIO = 0.8


def _cn_numeral_to_int(text: str) -> Optional[int]:
    total, current = 0, 0
    for ch in text:
        if ch in _CN_DIGITS:
            current = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            total += (current or 1) * _CN_UNITS[ch]
            current = 0
        else:
            return None
    return total + current


def _chapter_number_from_title(title: str) -> Optional[int]:
    match = _TITLE_NUM_ARABIC_RE.search(title or "")
    if match:
        return int(match.group(1) or match.group(2))
    match = _TITLE_NUM_CN_RE.search(title or "")
    if match:
        return _cn_numeral_to_int(match.group(1))
    match = _TITLE_NUM_AFTER_VOLUME_RE.search(title or "") or _TITLE_NUM_LEADING_RE.search(title or "")
    return int(match.group(1)) if match else None


def _chapter_number_from_url(url: str) -> Optional[int]:
    digits = re.findall(r"\d+", urllib.parse.urlparse(url or "").path)
    return int(digits[-1]) if digits else None


def _is_descending(numbers: List[Optional[int]]) -> bool:
    """True only when the numbered items clearly run high -> low (>= 80% of adjacent pairs)."""
    known = [n for n in numbers if n is not None]
    if len(known) < _MIN_ORDER_PAIRS + 1 or len(known) < 0.6 * len(numbers):
        return False
    pairs = list(zip(known, known[1:]))
    descending = sum(1 for a, b in pairs if b < a)
    return descending >= _DESCENDING_RATIO * len(pairs)


def ensure_chronological_order(chapters: list) -> list:
    """Return chapters oldest-first. Some sites list newest-first; importing that as-is makes
    'Chapter 1' the story's last chapter. Detect from title numbers, else from URL ids, and only
    reverse when the evidence is clear. Never mutates the input."""
    if len(chapters) < _MIN_ORDER_PAIRS + 1:
        return chapters
    title_numbers = [_chapter_number_from_title(c["title"]) for c in chapters]
    if sum(n is not None for n in title_numbers) >= 0.6 * len(chapters):
        descending = _is_descending(title_numbers)
    else:
        descending = _is_descending([_chapter_number_from_url(c["url"]) for c in chapters])
    return list(reversed(chapters)) if descending else chapters


def extract_links_from_html(html_text: str, base_url: str):
    soup = BeautifulSoup(html_text, "html.parser")
    meta = extract_universal_metadata(html_text, url=base_url)
    title_tag = soup.find("title")
    novel_title = (
        meta.get("title")
        or (title_tag.get_text(strip=True) if title_tag else "")
        or "Untitled Novel"
    )

    parsed_base = urllib.parse.urlparse(base_url)
    base_clean = urllib.parse.urldefrag(base_url)[0]
    base_digits = [seg for seg in parsed_base.path.split("/") if seg.isdigit() and len(seg) >= 2]

    links = []
    url_to_index = {}
    raw_links = []

    junk_paths = (
        "/stag/", "/cmts/", "/lcmt/", "/fans", "/vip/c/",
        "/author/", "/user/", "/login", "/register", "/search",
        "/category/", "/tag/", "/rank/", "/top/", "/comment",
    )

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:", "tel:")):
            continue
        text = a.get_text(strip=True)
        if not text or len(text) < 2:
            continue
        if text.lower() in _TOC_NAV_EXACT_LABELS:
            continue

        abs_url = urllib.parse.urldefrag(urllib.parse.urljoin(base_url, href))[0]
        parsed = urllib.parse.urlparse(abs_url)

        if not _same_site_host(parsed.netloc, parsed_base.netloc):
            continue

        if abs_url == base_clean:
            continue

        raw_links.append((text, abs_url, parsed))

        if any(junk in parsed.path.lower() for junk in junk_paths):
            continue

        is_chapter = False
        base_path_clean = parsed_base.path.rstrip("/")
        cand_path_clean = parsed.path.rstrip("/")

        # 1. Path is deeper than base (e.g. /Novel/123/456/ or /book/123.html -> /book/123/1.html)
        base_stem = re.sub(r"\.(?:html?|shtml|php|aspx)$", "", base_path_clean, flags=re.I)
        if base_stem and cand_path_clean.startswith(base_stem) and len(cand_path_clean) > len(base_stem):
            is_chapter = True
        # 2. Chinese websites often use specific path structures with digits
        elif any(char.isdigit() for char in parsed.path) and len(cand_path_clean.split("/")) > 3:
            is_chapter = True
        # 3. Path matches common chapter routes (/read/123/456, /chapter/456, /txt/123/456)
        elif _CHAPTER_PATH_RE.search(parsed.path) and any(c.isdigit() for c in parsed.path):
            is_chapter = True
        # 4. Shares novel numeric ID and ends with a chapter numeric ID or matches chapter text pattern
        elif base_digits and any(f"/{nid}/" in parsed.path for nid in base_digits) and any(c.isdigit() for c in cand_path_clean.split("/")[-1]):
            is_chapter = True
        elif _CHAPTER_TEXT_RE.search(text) and any(char.isdigit() for char in parsed.path):
            is_chapter = True

        # Extra safety: Ensure the link is not just the novel homepage
        if "/Novel/" in parsed.path and len(cand_path_clean.split("/")) <= 3:
            is_chapter = False

        if is_chapter:
            # Tail deduplication: many Chinese/Asian novel TOC pages place a "最新章节 (Latest Chapters)"
            # widget at the top before the main chronological "正文 (Chapter List)" below.
            # If the same chapter URL appears again later in the main TOC, move it to the later
            # position so chapters stay in chronological order starting from Chapter 1.
            if abs_url in url_to_index:
                old_idx = url_to_index[abs_url]
                links[old_idx] = None
            url_to_index[abs_url] = len(links)
            links.append({"title": text, "url": abs_url})

    links = [item for item in links if item is not None]
    return novel_title, links, raw_links


async def fetch_and_extract_links(url: str, client: Optional[httpx.AsyncClient] = None, workspace: Optional[str] = None):
    from routers.scrape import fetch_html_adaptive
    html_text, final_url = await fetch_html_adaptive(url, workspace=workspace)
    return extract_links_from_html(html_text, final_url)

def is_domain(url: str, domain: str) -> bool:
    """Check if URL host matches domain or subdomain exactly."""
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        return host == domain or host.endswith(f".{domain}")
    except Exception:
        return False


@router.post("/threads/scrape-toc", response_model=TOCScrapeResponse)
async def scrape_toc(req: TOCScrapeRequest, request: Request = None):
    """Scrape a novel index/TOC page and detect chapter links heuristically or via dedicated adapters."""
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    ws = resolve_workspace(request)

    # SSRF guard: block requests to internal/private IPs
    from services.security import validate_external_url, create_safe_async_client
    validate_external_url(req.url)

    # 1. Dedicated Adapter: Novalpie.cc
    if is_domain(req.url, "novalpie.cc"):
        try:
            from services.scrapers.novalpie import NovalpieAdapter
            novalpie = NovalpieAdapter(workspace=ws)
            novel_title, chapters_list = await novalpie.scrape_toc(req.url)
            toc_chapters = [TOCChapterInfo(title=c["title"], url=c["url"]) for c in chapters_list]
            return TOCScrapeResponse(title=novel_title, chapters=toc_chapters)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Failed to scrape novalpie.cc TOC: {e}")

    # 2. Dedicated Adapter: SFACG (book.sfacg.com)
    if is_domain(req.url, "sfacg.com"):
        try:
            from services.scrapers.sfacg import SFACGAdapter
            sfacg = SFACGAdapter()
            novel_title, chapters_list = await sfacg.scrape_toc(req.url)
            toc_chapters = [TOCChapterInfo(title=c["title"], url=c["url"]) for c in chapters_list]
            return TOCScrapeResponse(title=novel_title, chapters=toc_chapters)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Failed to scrape sfacg.com TOC: {e}")

    try:
        novel_title, links, raw_links = await fetch_and_extract_links(req.url, workspace=ws)

        # If we found too few links, we might be on the summary page.
        # Look for a dedicated TOC link (like /MainIndex/, "目录", "全部章节", "点击阅读", etc.)
        if len(links) < 50:
            toc_url = None
            for text, url, parsed in raw_links:
                if any(kw in url or kw in text.lower() or kw in text for kw in _TOC_FOLLOW_KEYWORDS):
                    toc_url = url
                    break

            if toc_url:
                validate_external_url(toc_url)
                print(f"[TOC Scraper] Found <50 links. Automatically following TOC link: {toc_url}")
                novel_title2, links2, _ = await fetch_and_extract_links(toc_url, workspace=ws)
                if len(links2) > len(links):
                    novel_title = novel_title2
                    links = links2

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch URL: {e}")

    return TOCScrapeResponse(title=novel_title, chapters=ensure_chronological_order(links))


@router.post("/threads/bulk-import-toc")
async def bulk_import_toc(req: TOCBulkImportRequest, db: Session = Depends(get_db)):
    """Bulk import chapters from TOC. Only saves the source_url, content is scraped on-demand."""
    if not req.chapters:
        raise HTTPException(400, "No chapters provided")

    if req.thread_id:
        thread = db.execute(select(Thread).where(Thread.id == req.thread_id)).scalar_one_or_none()
        if not thread:
            raise HTTPException(404, "Thread not found")

        max_order_val = db.execute(
            select(func.max(Chapter.order)).where(Chapter.thread_id == thread.id)
        ).scalar()
        max_order = -1 if max_order_val is None else max_order_val
    else:
        title = req.title or "Imported Novel"
        author = ""
        synopsis = ""
        cover_image = ""

        # Auto-fetch metadata if base_url is provided
        if req.base_url:
            from services.security import validate_external_url
            try:
                validate_external_url(req.base_url)
                ws = get_db_workspace(db)
                if is_domain(req.base_url, "sfacg.com"):
                    from services.scrapers.sfacg import SFACGAdapter
                    sfacg = SFACGAdapter()
                    meta = await sfacg.scrape_metadata(req.base_url)
                    if meta.success:
                        title = meta.title or title
                        author = meta.author or ""
                        synopsis = meta.synopsis or ""
                        cover_image = meta.cover_image or ""
                elif is_domain(req.base_url, "novalpie.cc"):
                    from services.scrapers.novalpie import NovalpieAdapter
                    novalpie = NovalpieAdapter(workspace=ws)
                    meta = await novalpie.scrape_metadata(req.base_url)
                    if meta.success:
                        title = meta.title or title
                        author = meta.author or ""
                        synopsis = meta.synopsis or ""
                        cover_image = meta.cover_image or ""
                        if not req.genres and meta.genres:
                            req.genres = meta.genres
                else:
                    from routers.scrape import fetch_html_adaptive
                    html_text, final_url = await fetch_html_adaptive(req.base_url, workspace=ws)
                    uni_meta = extract_universal_metadata(html_text, url=final_url)
                    if uni_meta.get("title") and (not req.title or req.title == "Imported Novel"):
                        title = uni_meta["title"]
                    author = uni_meta.get("author") or author
                    synopsis = uni_meta.get("synopsis") or synopsis
                    cover_image = uni_meta.get("cover_image") or cover_image
                    if not req.genres and uni_meta.get("genres"):
                        req.genres = uni_meta["genres"]
            except Exception as e:
                print(f"[TOC Import] Auto-metadata failed: {e}")


        # Create new Thread
        thread = Thread(
            title=title,
            original_title=title,
            author=author,
            synopsis=synopsis,
            cover_image=cover_image,
            genres=req.genres,
            source_type="url",
            source_url=req.base_url or (req.chapters[0].url if req.chapters else "")
        )
        db.add(thread)
        db.flush()
        max_order = -1

    new_chapters = []
    for idx, chap_info in enumerate(req.chapters):
        chapter = Chapter(
            thread_id=thread.id,
            order=max_order + 1 + idx,
            title_original=chap_info.title,
            source_url=chap_info.url,
            content_original=None,  # explicitly null so it triggers on-demand scraping
            translation_status="idle"
        )
        new_chapters.append(chapter)

    db.add_all(new_chapters)
    db.commit()

    return {
        "success": True, 
        "thread_id": thread.id, 
        "imported_count": len(new_chapters)
    }
