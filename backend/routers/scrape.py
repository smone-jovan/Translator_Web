"""
POST /api/scrape — Fetch URL, clean HTML, return Markdown.
Uses httpx + BeautifulSoup (lightweight, no browser needed).
Also contains URL imports and NovelUpdates/SFACG metadata scrapers.
"""

import asyncio
import codecs
import json
import random
import re
import urllib.parse
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from database import get_db, SessionLocal, Thread, Chapter, GlobalSetting, resolve_workspace, get_db_workspace
from services.security import validate_external_url, create_safe_async_client
from services.scrapers.engine import MetadataScraperEngine
from services.scrapers.adaptive_dom import AdaptiveDOM, extract_universal_metadata, extract_hydration_prose
from services.scrapers.novalpie import _is_cloudflare_challenge

_DEFAULT_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,ko;q=0.6,ja;q=0.5",
}

_SPA_SHELL_RE = re.compile(
    r'(<div[^>]+id=["\'](?:app|__nuxt|__next|root)["\'][^>]*>\s*</div>|window\.__NUXT__|__NEXT_DATA__)',
    re.IGNORECASE,
)


router = APIRouter(prefix="/api", tags=["Scraping"])
scraper_engine = MetadataScraperEngine()

TOC_ROOT_URL_PATTERN = re.compile(
    r"^https?://(?:(?:www\.)?novalpie\.cc/(?:book|novel)/\d+|(?:[a-zA-Z0-9-]+\.)?sfacg\.com/(?:Novel|b)/\d+(?:/MainIndex)?)/?$",
    re.IGNORECASE,
)


class ScrapeRequest(BaseModel):
    url: str


class ScrapeResponse(BaseModel):
    title: str
    markdown: str
    word_count: int


class ImportURLRequest(BaseModel):
    url: str
    thread_id: Optional[int] = None  # If provided, add chapter to existing thread


class ScrapeMetadataRequest(BaseModel):
    original_title: Optional[str] = None
    include_cover: bool = True
    search_by: Optional[str] = "original"  # "original" or "translated"
    source: Optional[str] = "novelupdates"   # "novelupdates" or "sfacg"


# Tags to strip completely (note: <img> is preserved and converted to Markdown ![alt](url))
STRIP_TAGS = [
    "script", "style", "nav", "footer", "header", "aside",
    "iframe", "noscript", "form", "button", "svg",
    "figcaption", "video", "audio", "canvas",
]

# Common ad/nav class patterns (uses negative lookbehind to avoid matching words ending in 'ad' like 'read-content')
AD_PATTERNS = re.compile(
    r"(?<![a-zA-Z0-9])(ads?[_-]|banner|sidebar|menu|nav|footer|bottem|page[_-]?nav|chap[_-]?nav|turn[_-]?page|comment|social|share|popup|modal|cookie| watermark|anti[_-]?scrape)",
    re.IGNORECASE,
)

# Inline CSS patterns used by novel sites to inject invisible anti-scraper honeypot text
_HIDDEN_STYLE_RE = re.compile(
    r"(?:display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(?:px|em|rem|pt|%)?(?:\s*;|\s*$)|opacity\s*:\s*0(?:\s*;|\s*$)|height\s*:\s*0(?:px)?(?:\s*;|\s*$))",
    re.IGNORECASE,
)

# Page-level containers whose class merely mentions a layout feature (e.g. WordPress
# `has-sidebar`, `comments-open`) must survive the ad filter, or the chapter goes with them.
_ALWAYS_KEEP_TAGS = {"html", "body"}
_WRAPPER_TEXT_SHARE = 0.5
_WRAPPER_MAX_LINK_SHARE = 0.5


def _is_page_wrapper(el, page_text_len: int) -> bool:
    """True when `el` holds most of the page's prose, so it is layout, not an ad/nav widget."""
    if el.name in _ALWAYS_KEEP_TAGS:
        return True
    text_len = len(el.get_text(strip=True))
    if text_len < page_text_len * _WRAPPER_TEXT_SHARE:
        return False
    link_text_len = sum(len(a.get_text(strip=True)) for a in el.find_all("a"))
    return link_text_len < text_len * _WRAPPER_MAX_LINK_SHARE


def html_to_markdown(html: str, url: str = "") -> tuple[str, str]:
    domain = urllib.parse.urlparse(url).hostname or "default" if url else "default"
    """Convert HTML to clean markdown-ish text. Returns (title, content)."""
    soup = BeautifulSoup(html, "html.parser")

    # Extract title adaptively
    adaptive_title = AdaptiveDOM.select_one(
        soup,
        ["h1", "h2", ".chapter-title", ".ep-title", ".reader-title", "title"],
        domain=domain,
        key="title",
        role="title",
        adaptive=True,
        auto_save=bool(url),
    )
    title = adaptive_title.get_text(strip=True) if adaptive_title else (soup.find("title").get_text(strip=True) if soup.find("title") else "Untitled")

    # Remove unwanted tags
    for tag_name in STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove hidden anti-scraper honeypots and elements with ad-like classes/ids
    page_text_len = len(soup.get_text(strip=True))
    for el in list(soup.find_all(True)):
        if getattr(el, "attrs", None) is None:
            continue

        if el.name not in _ALWAYS_KEEP_TAGS:
            is_hidden = (
                el.has_attr("hidden")
                or str(el.get("aria-hidden", "")).strip().lower() == "true"
                or bool(_HIDDEN_STYLE_RE.search(str(el.get("style", "") or "")))
            )
            if is_hidden and not _is_page_wrapper(el, page_text_len):
                el.decompose()
                continue

        classes_raw = el.get("class", [])
        if isinstance(classes_raw, list):
            classes = " ".join(str(c) for c in classes_raw)
        elif isinstance(classes_raw, str):
            classes = classes_raw
        else:
            classes = ""
            
        el_id = el.get("id", "")
        if not isinstance(el_id, str):
            el_id = str(el_id)
            
        if (AD_PATTERNS.search(classes) or AD_PATTERNS.search(el_id)) and not _is_page_wrapper(el, page_text_len):
            el.decompose()

    # Try to find main content area adaptively
    adaptive_content = AdaptiveDOM.select_one(
        soup,
        [
            "article.reader-content",
            "article",
            ".chapter-content",
            ".novel-content",
            "#chapter-content",
            "#content",
            ".entry-content",
            ".post-content",
            "main",
        ],
        domain=domain,
        key="content",
        role="content",
        adaptive=True,
        auto_save=bool(url),
        min_text_len=60,
    )

    content_el = adaptive_content or (
        soup.find("article")
        or soup.find("div", class_=re.compile(r"(chapter|content|entry|post|text|body)", re.I))
        or soup.find("main")
        or soup.body
        or soup
    )

    # Convert inline chapter illustrations (<img>, including lazy-loaded data-src) to Markdown
    for img in list(content_el.find_all("img")):
        raw_src = (
            img.get("data-src")
            or img.get("data-original")
            or img.get("data-lazy-src")
            or img.get("data-actualsrc")
            or img.get("src")
            or ""
        ).strip()
        if not raw_src or raw_src.startswith("data:") or raw_src.lower().endswith(".svg"):
            img.decompose()
            continue
        width = str(img.get("width") or "").strip()
        height = str(img.get("height") or "").strip()
        if width == "1" or height == "1":
            img.decompose()
            continue
        abs_src = urllib.parse.urljoin(url, raw_src) if url else raw_src
        if not abs_src.startswith(("http://", "https://", "/")):
            img.decompose()
            continue
        alt = re.sub(r"[\[\]\r\n]+", " ", str(img.get("alt") or "").strip())
        img.replace_with(f"\n\n![{alt}]({abs_src})\n\n")

    # Pre-process some tags to maintain structure
    for tag in content_el.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        level = int(tag.name[1])
        tag.insert_before(f"\n\n{'#' * level} ")
        tag.insert_after("\n\n")

    for tag in content_el.find_all("li"):
        tag.insert_before("\n- ")

    for tag in content_el.find_all("blockquote"):
        tag.insert_before("\n> ")
        tag.insert_after("\n")

    for br in content_el.find_all("br"):
        br.replace_with("\n\n")
    
    for p in content_el.find_all(["p", "div"]):
        p.insert_before("\n")
        p.insert_after("\n")

    markdown = content_el.get_text(strip=False)
    
    # Clean up whitespace
    markdown = re.sub(r'[ \t]+', ' ', markdown)
    
    # Remove ugly Novalpie Vue placeholders for failed images
    markdown = markdown.replace("图片加载中...", "")
    markdown = markdown.replace("图片加载失败", "")
    markdown = markdown.replace("⚠️", "")
    
    # Collapse excessive newlines
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = markdown.strip()

    # Fallback: if static DOM had < 50 chars of prose, inspect SPA JSON hydration scripts (__NEXT_DATA__, etc.)
    if len(markdown) < 50:
        hydrated = extract_hydration_prose(html)
        if hydrated:
            hyd_title, hyd_md = hydrated
            if hyd_title and hyd_title != "Untitled":
                title = hyd_title
            markdown = hyd_md

    return title, markdown


_HEADER_CHARSET_RE = re.compile(r"charset\s*=\s*[\"']?([^\s;\"']+)", re.IGNORECASE)
_META_CHARSET_RE = re.compile(rb"<meta[^>]+charset\s*=\s*[\"']?\s*([a-zA-Z0-9_\-]+)", re.IGNORECASE)
_CHARSET_SNIFF_BYTES = 4096
# Map common CJK/JP/KR aliases to their strict superset codecs in Python's stdlib.
_CHARSET_ALIASES = {
    "gb2312": "gb18030",
    "gbk": "gb18030",
    "x-gbk": "gb18030",
    "gb_2312-80": "gb18030",
    "big5": "big5hkscs",
    "big5-hkscs": "big5hkscs",
    "x-x-big5": "big5hkscs",
    "shift_jis": "cp932",
    "shift-jis": "cp932",
    "sjis": "cp932",
    "x-sjis": "cp932",
    "ms932": "cp932",
    "windows-31j": "cp932",
    "euc-kr": "cp949",
    "euckr": "cp949",
    "ks_c_5601-1987": "cp949",
    "ksc5601": "cp949",
}
_ASCII_BYTES = bytes(range(128))
# Legacy CJK bytes (GBK, Big5, Shift-JIS, EUC-KR) read as UTF-8 yield ~0.65-0.9 replacement
# chars per non-ASCII byte; genuine UTF-8 with a few corrupt bytes stays far below this.
_MAX_UTF8_ERROR_RATIO = 0.1
_UTF8_REPLACEMENT_CHAR = "\ufffd"


def _normalize_charset(label: Optional[str]) -> Optional[str]:
    if not label:
        return None
    name = label.strip().lower()
    try:
        return codecs.lookup(_CHARSET_ALIASES.get(name, name)).name
    except LookupError:
        return None


def _decode_lenient_utf8(content: bytes) -> Optional[str]:
    """UTF-8 with a few corrupt bytes replaced, or None when the bytes are not UTF-8 at all."""
    text = content.decode("utf-8", errors="replace")
    non_ascii_len = len(content.translate(None, _ASCII_BYTES))
    if text.count(_UTF8_REPLACEMENT_CHAR) <= non_ascii_len * _MAX_UTF8_ERROR_RATIO:
        return text
    return None


def decode_response_html(resp) -> str:
    """
    Decode an HTML response (httpx or curl_cffi) using the HTTP charset, then the <meta>
    charset, then UTF-8 / GB18030 sniffing. httpx alone falls back to UTF-8 when the header
    omits the charset, which garbles GBK pages that declare it only in <meta>.
    """
    content = getattr(resp, "content", None)
    if not isinstance(content, (bytes, bytearray)):
        return getattr(resp, "text", "") or ""
    content = bytes(content)

    headers = getattr(resp, "headers", None)
    content_type = (headers.get("content-type") or "") if headers is not None else ""
    header_match = _HEADER_CHARSET_RE.search(content_type)
    meta_match = _META_CHARSET_RE.search(content[:_CHARSET_SNIFF_BYTES])
    declared = [
        encoding
        for encoding in (
            _normalize_charset(header_match.group(1) if header_match else None),
            _normalize_charset(meta_match.group(1).decode("ascii", "ignore") if meta_match else None),
        )
        if encoding
    ]
    for encoding in declared:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue

    # No usable declaration, or the bytes contradict it: sniff across UTF-8 and CJK/JP/KR codecs.
    lenient_utf8 = _decode_lenient_utf8(content)
    if lenient_utf8 is not None:
        return lenient_utf8
    if not declared:
        for fallback_enc in ("gb18030", "big5hkscs", "cp932", "cp949"):
            try:
                return content.decode(fallback_enc)
            except UnicodeDecodeError:
                continue
    return content.decode(declared[0] if declared else "gb18030", errors="replace")


def is_domain(url: str, domain: str) -> bool:
    """Check if URL host matches domain or subdomain exactly."""
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        return host == domain or host.endswith(f".{domain}")
    except Exception:
        return False


_NEXT_LINK_EXACT_LABELS = frozenset({
    "下一章", "下一页", "下一頁", "下一节", "下一節", "下一话", "下一話", "下页", "下章",
    "next", "next chapter", "next page", "next episode",
    "次へ", "次の話", "次話", "次のページ", "次ページ",
    "다음화", "다음 화", "다음장", "다음 장", "다음편", "다음 편",
    "bab selanjutnya", "chapter selanjutnya", "lanjut",
})
_NEXT_CHAPTER_STRICT_LABELS = frozenset({
    "下一章", "下一节", "下一節", "下一话", "下一話", "下章",
    "next chapter", "next episode",
    "次の話", "次話",
    "다음화", "다음 화", "다음장", "다음 장", "다음편", "다음 편",
    "bab selanjutnya", "chapter selanjutnya",
})
_SUBPAGE_LABELS = frozenset({
    "下一页", "下一頁", "下页", "next page", "次のページ", "次ページ",
})
_NEXT_LINK_EXCLUDED = ("下一卷", "next volume", "다음권", "次巻")
_NEXT_LINK_DECORATION_RE = re.compile(r"[\s<>«»‹›→⇒➜>\[\]【】()（）|:：.…·»]+")
_JS_NEXT_PAGE_RE = re.compile(
    r"(?:var|let|const)?\s*(?:next_page|nextpage|nextUrl|next_url|nextChapterUrl)\s*=\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)


def _site_host(url: str) -> str:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _same_site(candidate_url: str, base_url: str) -> bool:
    """Same host, or one is a subdomain of the other (www./m. mirrors of one novel site)."""
    a, b = _site_host(candidate_url), _site_host(base_url)
    if not a or not b:
        return False
    return a == b or a.endswith(f".{b}") or b.endswith(f".{a}")


def _normalize_next_label(text: str) -> str:
    return _NEXT_LINK_DECORATION_RE.sub(" ", text).strip().lower()


def _chapter_base_stem(url: str) -> tuple[str, int]:
    """
    Return (canonical_chapter_stem, subpage_num) for URLs like:
    - /book/123/456.html -> ('/book/123/456', 1)
    - /book/123/456_2.html -> ('/book/123/456', 2)
    - /book/123/456-3.html -> ('/book/123/456', 3)
    """
    parsed = urllib.parse.urlparse(url)
    path = re.sub(r"\.(?:html?|shtml|php|aspx)$", "", parsed.path.rstrip("/"), flags=re.I)
    q_match = re.search(r"(?:^|&)(?:page|p)=(\d+)(?:&|$)", parsed.query, flags=re.I)
    if q_match:
        return path, int(q_match.group(1))
    m = re.match(r"^(.+?\d+)[_-](\d{1,2})$", path)
    if m and int(m.group(2)) <= 20:
        return m.group(1), int(m.group(2))
    return path, 1


def _is_subpage_url_of(candidate_url: str, base_url: str) -> bool:
    """True when `candidate_url` is sub-page N+1 (e.g. 101_2.html or ?page=2) of `base_url`."""
    if not _same_site(candidate_url, base_url):
        return False
    base_stem, base_sub = _chapter_base_stem(base_url)
    cand_stem, cand_sub = _chapter_base_stem(candidate_url)
    return bool(base_stem and base_stem == cand_stem and cand_sub == base_sub + 1)


def find_next_subpage_link(html: str, base_url: str) -> Optional[str]:
    """
    Detect intra-chapter pagination links (e.g. `101_2.html`, `101-2.html`, `?page=2`, or
    `下一页` when paired with a separate `下一章` link) so split chapters can be stitched.
    Returns None for single-page chapters.
    """
    if not html or not base_url:
        return None
    soup = BeautifulSoup(html, "html.parser")
    current = urllib.parse.urldefrag(base_url)[0]

    def resolve(href) -> Optional[str]:
        href = (href or "").strip()
        if not href or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:")):
            return None
        candidate = urllib.parse.urldefrag(urllib.parse.urljoin(base_url, href))[0]
        if candidate == current or not candidate.startswith(("http://", "https://")):
            return None
        return candidate if _same_site(candidate, base_url) else None

    anchors = []
    has_distinct_next_chapter_label = False
    for a in soup.find_all("a"):
        text = a.get_text(strip=True)
        norm = _normalize_next_label(text)
        url = resolve(a.get("href"))
        if not url:
            continue
        anchors.append((norm, url, text))
        if norm in _NEXT_CHAPTER_STRICT_LABELS and not _is_subpage_url_of(url, base_url):
            has_distinct_next_chapter_label = True

    # 1. Explicit URL sub-page pattern (e.g. 101.html -> 101_2.html or ?page=2)
    for norm, url, _ in anchors:
        if _is_subpage_url_of(url, base_url):
            return url

    # 2. Label is "下一页 / next page" AND the page also has a distinct "下一章 / next chapter" link
    if has_distinct_next_chapter_label:
        for norm, url, _ in anchors:
            if norm in _SUBPAGE_LABELS:
                return url

    return None


async def stitch_subpages_markdown(
    first_html: str,
    first_url: str,
    first_md: str,
    *,
    workspace: Optional[str] = None,
    max_subpages: int = 5,
) -> tuple[str, str, str]:
    """
    If `first_html` is page 1 of a split chapter (e.g. 101.html -> 101_2.html -> 101_3.html),
    fetch and stitch subsequent sub-pages into a single Markdown string.
    Returns (stitched_markdown, last_html, last_final_url).
    For single-page chapters, returns immediately with zero extra network or parser calls.
    """
    next_sub_url = find_next_subpage_link(first_html, first_url)
    if not next_sub_url:
        return first_md, first_html, first_url

    parts = [first_md.strip()] if first_md else []
    visited = {urllib.parse.urldefrag(first_url)[0]}
    last_html = first_html
    last_url = first_url

    for _ in range(max_subpages):
        if not next_sub_url or next_sub_url in visited:
            break
        visited.add(next_sub_url)
        try:
            validate_external_url(next_sub_url)
            sub_html, sub_final_url = await fetch_html_adaptive(next_sub_url, workspace=workspace)
            _, sub_md = html_to_markdown(sub_html, url=sub_final_url)
            if sub_md:
                # Strip duplicate leading # Title header on continuation sub-pages
                cleaned_sub = re.sub(r"^#{1,3}\s+[^\n]+\n+", "", sub_md.strip()).strip()
                if cleaned_sub:
                    parts.append(cleaned_sub)
            last_html = sub_html
            last_url = sub_final_url
            next_sub_url = find_next_subpage_link(sub_html, sub_final_url)
        except Exception:
            break

    return "\n\n".join(p for p in parts if p), last_html, last_url


def find_next_chapter_link(html: str, base_url: str) -> Optional[tuple[str, str]]:
    """
    Find the next-chapter link of a generic chapter page as (absolute_url, link_text).
    Priority:
    1. <link rel=next> / <a rel=next> (unless pointing to an intra-chapter sub-page 1_2.html)
    2. Explicit next-chapter labels (下一章, Next Chapter, 다음화, 次の話, Bab Selanjutnya)
       that do NOT point to an intra-chapter sub-page (1_2.html).
    3. Any exact label in _NEXT_LINK_EXACT_LABELS (including 下一页 / Next Page)
    4. Partial label matches (下一, 下页, next, 다음, 次へ)
    5. Inline JS variables (var next_page = "...")
    Next-volume links (下一卷, 다음권, 次巻), off-site links, self links and javascript:/# anchors
    are never returned.
    """
    soup = BeautifulSoup(html, "html.parser")
    current = urllib.parse.urldefrag(base_url)[0]

    def resolve(href) -> Optional[str]:
        href = (href or "").strip()
        if not href or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:")):
            return None
        candidate = urllib.parse.urldefrag(urllib.parse.urljoin(base_url, href))[0]
        if candidate == current or not candidate.startswith(("http://", "https://")):
            return None
        return candidate if _same_site(candidate, base_url) else None

    anchors = []
    for a in soup.find_all("a"):
        text = a.get_text(strip=True)
        if any(excluded in text.lower() for excluded in _NEXT_LINK_EXCLUDED):
            continue
        url = resolve(a.get("href"))
        if url:
            anchors.append((a, url, text))

    # 1. <link rel="next"> / <a rel="next"> (skip if it points to an intra-chapter sub-page 1_2.html)
    for tag in soup.find_all("link"):
        if "next" in [r.lower() for r in (tag.get("rel") or [])]:
            url = resolve(tag.get("href"))
            if url and not _is_subpage_url_of(url, base_url):
                return url, ""
    for a, url, text in anchors:
        if "next" in [r.lower() for r in (a.get("rel") or [])] and not _is_subpage_url_of(url, base_url):
            return url, text

    # 2. Prefer strict "next chapter" labels that are NOT intra-chapter sub-pages (1_2.html)
    for _, url, text in anchors:
        if _normalize_next_label(text) in _NEXT_CHAPTER_STRICT_LABELS and not _is_subpage_url_of(url, base_url):
            return url, text

    # 3. Any exact label in _NEXT_LINK_EXACT_LABELS (preferring non-subpage URLs first)
    for _, url, text in anchors:
        if _normalize_next_label(text) in _NEXT_LINK_EXACT_LABELS and not _is_subpage_url_of(url, base_url):
            return url, text
    for _, url, text in anchors:
        if _normalize_next_label(text) in _NEXT_LINK_EXACT_LABELS:
            return url, text

    # 4. Partial label matches
    for _, url, text in anchors:
        tl = text.lower()
        if (
            "下一" in text
            or "下页" in text
            or "下章" in text
            or "다음" in text
            or "次の" in text
            or "次へ" in text
            or "next" in tl
            or "selanjutnya" in tl
        ):
            return url, text

    # 5. Inline JS variable fallback (e.g. var next_page = "102.html";)
    for script in soup.find_all("script"):
        s_txt = script.string or script.get_text() or ""
        m = _JS_NEXT_PAGE_RE.search(s_txt)
        if m:
            url = resolve(m.group(1))
            if url:
                return url, ""

    return None


async def fetch_html_adaptive(
    url: str,
    *,
    workspace: Optional[str] = None,
    allow_playwright_fallback: bool = True,
) -> tuple[str, str]:
    validate_external_url(url)
    primary_exc: Optional[Exception] = None
    html_text = ""
    final_url = url

    try:
        async with create_safe_async_client(
            follow_redirects=True,
            timeout=30.0,
            headers=_DEFAULT_BROWSER_HEADERS,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html_text = decode_response_html(resp)
            final_url = str(resp.url) if getattr(resp, "url", None) else url
    except httpx.HTTPStatusError as exc:
        primary_exc = exc
        if exc.response is None or exc.response.status_code not in (403, 429, 503):
            raise
    except httpx.HTTPError as exc:
        primary_exc = exc
        raise

    needs_escalation = primary_exc is not None or not html_text or _is_cloudflare_challenge(html_text)

    if needs_escalation:
        try:
            from curl_cffi.requests import AsyncSession
            from services.security import follow_redirects_safely
            # Redirect diikuti manual: setiap hop divalidasi SEBELUM diminta (ADR-126).
            async with AsyncSession(
                impersonate="chrome120",
                headers=_DEFAULT_BROWSER_HEADERS,
                timeout=25.0,
                allow_redirects=False,
            ) as cf_session:
                cf_resp, cf_final_url = await follow_redirects_safely(
                    lambda u: cf_session.get(u, allow_redirects=False), url
                )
                cf_text = decode_response_html(cf_resp) if cf_resp.status_code == 200 else ""
                if cf_text and not _is_cloudflare_challenge(cf_text):
                    html_text = cf_text
                    final_url = cf_final_url
                    needs_escalation = False
        except HTTPException:
            raise
        except Exception:
            pass

    if not needs_escalation and html_text and _SPA_SHELL_RE.search(html_text):
        _, probe_md = html_to_markdown(html_text, url=final_url)
        if len(probe_md.strip()) < 50:
            needs_escalation = True

    if needs_escalation and allow_playwright_fallback:
        try:
            from services.scrapers.stealth_base import StealthyNovelAdapter
            stealth = StealthyNovelAdapter(workspace=workspace, adaptive_domain=url)
            # strict_ssrf: URL berasal dari pengguna, jadi pakai jalur Playwright native yang
            # memvalidasi setiap request browser (hop redirect + subresource), bukan Scrapling.
            page = await stealth.fetch_stealth_page(
                url, solve_cloudflare=True, disable_resources=True, timeout_ms=45000, strict_ssrf=True
            )
            page_html = getattr(page, "html", "") or (page.get_all_text() if hasattr(page, "get_all_text") else "")
            if page_html and not _is_cloudflare_challenge(page_html):
                html_text = page_html
                final_url = getattr(page, "url", None) or final_url
                needs_escalation = False
        except HTTPException:
            raise
        except Exception:
            pass

    if not html_text and primary_exc is not None:
        raise primary_exc

    return html_text, final_url


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape_url(req: ScrapeRequest, request: Request = None, workspace: Optional[str] = None):
    """Fetch URL, strip ads/nav, return clean markdown."""
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    # SSRF guard: block requests to internal/private IPs
    from services.security import validate_external_url
    validate_external_url(req.url)

    if TOC_ROOT_URL_PATTERN.match(req.url.strip()):
        raise HTTPException(
            400,
            "This is a Novel TOC URL. Please use the 'Extract TOC' button (list icon) instead to import all chapters.",
        )

    ws = workspace or resolve_workspace(request)

    # 1. Dedicated Adapter: Novalpie
    if is_domain(req.url, "novalpie.cc"):
        try:
            from services.scrapers.novalpie import NovalpieAdapter
            novalpie = NovalpieAdapter(workspace=ws)
            title, markdown = await novalpie.scrape_chapter_content(req.url)
            if not markdown:
                raise HTTPException(422, "No content extracted from novalpie URL.")
            return ScrapeResponse(
                title=title,
                markdown=markdown,
                word_count=len(markdown.split()),
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Failed to scrape novalpie chapter: {e}")

    # 2. Dedicated Adapter: SFACG (book.sfacg.com)
    if is_domain(req.url, "sfacg.com"):
        try:
            from services.scrapers.sfacg import SFACGAdapter
            sfacg = SFACGAdapter()
            title, markdown = await sfacg.scrape_chapter_content(req.url)
            if not markdown:
                raise HTTPException(422, "No content extracted from SFACG URL.")
            return ScrapeResponse(
                title=title,
                markdown=markdown,
                word_count=len(markdown.split()),
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Failed to scrape SFACG chapter: {e}")

    if re.match(r'^https?://(?:www\.)?novalpie\.cc/(?:book|novel)/\d+/?$', req.url):
        raise HTTPException(400, "This is a Novel TOC URL. Please use the 'Extract TOC' button (list icon) instead to import all chapters.")

    try:
        html_text, final_url = await fetch_html_adaptive(req.url, workspace=ws)
        title, markdown = html_to_markdown(html_text, url=final_url)
        markdown, _, _ = await stitch_subpages_markdown(html_text, final_url, markdown, workspace=ws)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch URL: {e}")

    if not markdown:
        raise HTTPException(422, "No content extracted from URL.")

    return ScrapeResponse(
        title=title,
        markdown=markdown,
        word_count=len(markdown.split()),
    )


@router.post("/threads/import-url")
async def import_from_url(req: ImportURLRequest, db: Session = Depends(get_db)):
    """Scrape a URL and create a new Thread/Chapter, or add a chapter to an existing thread."""
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    validate_external_url(req.url)

    if TOC_ROOT_URL_PATTERN.match(req.url.strip()):
        raise HTTPException(
            400,
            "This is a Novel TOC URL. Please use the 'Extract TOC' button (list icon) instead to import all chapters.",
        )

    ws = get_db_workspace(db)
    source_url = req.url

    if is_domain(req.url, "novalpie.cc"):
        try:
            from services.scrapers.novalpie import NovalpieAdapter
            novalpie = NovalpieAdapter(workspace=ws)
            title, markdown = await novalpie.scrape_chapter_content(req.url)
            if not markdown:
                raise HTTPException(422, "No content extracted from novalpie URL.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Failed to scrape novalpie chapter: {e}")
    elif is_domain(req.url, "sfacg.com"):
        try:
            from services.scrapers.sfacg import SFACGAdapter
            sfacg = SFACGAdapter()
            title, markdown = await sfacg.scrape_chapter_content(req.url)
            if not markdown:
                raise HTTPException(422, "No content extracted from sfacg URL.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Failed to scrape sfacg chapter: {e}")
    else:
        try:
            html_text, final_url = await fetch_html_adaptive(req.url, workspace=ws)
            title, markdown = html_to_markdown(html_text, url=final_url)
            markdown, _, _ = await stitch_subpages_markdown(html_text, final_url, markdown, workspace=ws)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Failed to fetch URL: {e}")

    is_vip = False
    if "/vip/" in req.url.lower():
        is_vip = True
    elif title and "VIP章节" in title:
        is_vip = True
    elif not markdown or len(markdown) < 50:
        if not (is_domain(req.url, "novalpie.cc") or is_domain(req.url, "sfacg.com")):
            is_vip = True

    if is_vip:
        markdown = "[VIP CHAPTER] Bab ini terkunci atau tidak dapat diakses (VIP)."

    if req.thread_id:
        # Add chapter to existing thread
        thread = db.execute(select(Thread).where(Thread.id == req.thread_id)).scalar_one_or_none()
        if not thread:
            raise HTTPException(404, "Thread not found")

        # Get the next order number (0 if thread currently has no chapters)
        max_order_val = db.execute(
            select(func.max(Chapter.order)).where(Chapter.thread_id == thread.id)
        ).scalar()
        max_order = -1 if max_order_val is None else max_order_val

        chapter = Chapter(
            thread_id=thread.id,
            order=max_order + 1,
            title_original=title,
            content_original=markdown,
            source_url=req.url,
            translation_status="vip" if is_vip else "idle"
        )
        db.add(chapter)
        db.commit()

        return {"thread_id": thread.id, "chapter_id": chapter.id}
    else:
        # Create new Thread
        # Check if URL belongs to a TOC-capable adapter (e.g. Novalpie)
        novel_title = title
        author = None
        cover_image = None
        synopsis = None
        remaining_chapters = []

        if is_domain(req.url, "novalpie.cc"):
            try:
                from services.scrapers.novalpie import NovalpieAdapter
                novalpie = NovalpieAdapter(workspace=ws)
                meta, remaining_chapters = await novalpie.get_remaining_chapters(req.url)
                if meta and meta.success:
                    if meta.original_title:
                        novel_title = meta.original_title
                    elif meta.title:
                        novel_title = meta.title
                    author = meta.author
                    cover_image = meta.cover_image
                    synopsis = meta.synopsis
            except Exception as e:
                print(f"⚠️ [Novalpie] Error auto-discovering novel metadata on single chapter import: {e}")
        elif not is_domain(req.url, "sfacg.com") and locals().get("html_text"):
            try:
                uni_meta = extract_universal_metadata(html_text, url=final_url)
                if uni_meta.get("title") and uni_meta["title"] != title:
                    novel_title = uni_meta["title"]
                author = uni_meta.get("author") or author
                cover_image = uni_meta.get("cover_image") or cover_image
                synopsis = uni_meta.get("synopsis") or synopsis
            except Exception as e:
                print(f"⚠️ [Universal] Error extracting metadata on chapter import: {e}")

        thread = Thread(
            title=novel_title,
            original_title=novel_title,
            author=author,
            cover_image=cover_image,
            synopsis=synopsis,
            source_type="url",
            source_url=req.url
        )
        db.add(thread)
        db.flush()  # Get ID

        # Create first chapter (the requested chapter)
        first_chapter = Chapter(
            thread_id=thread.id,
            order=0,
            title_original=title,
            content_original=markdown,
            source_url=req.url,
            translation_status="vip" if is_vip else "idle"
        )
        db.add(first_chapter)

        # Auto-populate remaining chapters from TOC (if discovered)
        for i, rem_ch in enumerate(remaining_chapters, start=1):
            db.add(Chapter(
                thread_id=thread.id,
                order=i,
                title_original=rem_ch.get("title") or f"Chapter {i + 1}",
                source_url=rem_ch.get("url"),
                content_original=None,
                translation_status="idle"
            ))

        db.commit()
        return {"thread_id": thread.id, "chapter_id": first_chapter.id}


@router.post("/threads/{thread_id}/scrape_metadata")
async def scrape_metadata(
    thread_id: int,
    req: ScrapeMetadataRequest,
    db: Session = Depends(get_db)
):
    """Scrape metadata from Novel Updates or SFACG directly."""
    # 1. Fetch thread
    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")
        
    query = req.original_title or thread.source_url or thread.title or ""
    if not query:
        raise HTTPException(400, "No query title or URL available to scrape metadata")

    # Call swappable scraper coordinator
    result = await scraper_engine.scrape(
        query=query,
        source=req.source,
        search_by=req.search_by,
        include_cover=req.include_cover,
        db_session=db,
        workspace=get_db_workspace(db),
    )

    if not result.success:
        raise HTTPException(500, result.synopsis or "Failed to scrape metadata")

    # Persist scraped fields to DB Thread
    thread.original_title = result.original_title
    if result.title:
        thread.title = result.title
    if result.genres:
        thread.genres = result.genres
    if result.tags:
        thread.tags = result.tags
    if result.synopsis:
        thread.synopsis = result.synopsis
    if result.status_coo:
        thread.status_coo = result.status_coo
    if result.status:
        thread.status = result.status
    if result.cover_image:
        thread.cover_image = result.cover_image
    if result.author:
        thread.author = result.author
        
    db.commit()
    
    return {
        "success": True,
        "original_title": result.original_title,
        "title": result.title,
        "author": result.author,
        "genres": result.genres,
        "tags": result.tags,
        "status": result.status,
        "status_coo": result.status_coo,
        "synopsis": result.synopsis,
        "cover_image": result.cover_image,
        "detail_url": result.detail_url
    }


@router.post("/threads/{thread_id}/scrape_candidates")
async def scrape_candidates_route(
    thread_id: int,
    req: ScrapeMetadataRequest,
    db: Session = Depends(get_db)
):
    """Scrape metadata candidates from Novel Updates or SFACG."""
    # 1. Fetch thread
    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")
        
    query = req.original_title or thread.source_url or thread.title or ""
    if not query:
        raise HTTPException(400, "No query title or URL available to scrape metadata")

    # Call swappable scraper coordinator
    results = await scraper_engine.scrape_candidates(
        query=query,
        source=req.source,
        search_by=req.search_by,
        include_cover=req.include_cover,
        db_session=db,
        workspace=get_db_workspace(db),
    )

    if not results:
        raise HTTPException(404, f"No candidates found on {req.source} for '{query}'")

    return {
        "success": True,
        "candidates": [
            {
                "title": r.title,
                "original_title": r.original_title,
                "author": r.author,
                "genres": r.genres,
                "tags": r.tags,
                "synopsis": r.synopsis,
                "status": r.status,
                "status_coo": r.status_coo,
                "cover_image": r.cover_image,
                "detail_url": r.detail_url
            }
            for r in results
        ]
    }


class SaveMetadataRequest(BaseModel):
    title: str
    original_title: str
    author: Optional[str] = None
    genres: Optional[str] = None
    tags: Optional[str] = None
    synopsis: Optional[str] = None
    status: Optional[str] = None
    status_coo: Optional[str] = None
    cover_image: Optional[str] = None
    detail_url: Optional[str] = None


@router.post("/threads/{thread_id}/save_metadata")
def save_metadata_route(
    thread_id: int,
    req: SaveMetadataRequest,
    db: Session = Depends(get_db)
):
    """Save chosen metadata to DB."""
    thread_stmt = select(Thread).where(Thread.id == thread_id)
    thread = db.execute(thread_stmt).scalar_one_or_none()
    if not thread:
        raise HTTPException(404, "Thread not found")

    thread.title = req.title
    thread.original_title = req.original_title
    if req.author:
        thread.author = req.author
    if req.genres:
        thread.genres = req.genres
    if req.tags:
        thread.tags = req.tags
    if req.synopsis:
        thread.synopsis = req.synopsis
    if req.status:
        thread.status = req.status
    if req.status_coo:
        thread.status_coo = req.status_coo
    if req.cover_image is not None:
        thread.cover_image = req.cover_image
    
    db.commit()
    return {"success": True}

@router.post("/threads/{thread_id}/chapters/{chapter_id}/fetch-next")
async def fetch_next_chapter(
    thread_id: int,
    chapter_id: int,
    db: Session = Depends(get_db)
):
    """Auto-fetch the next chapter from the web if a 'Next' link exists in the current chapter's HTML."""
    chapter = db.execute(select(Chapter).where(Chapter.id == chapter_id, Chapter.thread_id == thread_id)).scalar_one_or_none()
    if not chapter:
        raise HTTPException(404, "Chapter not found")
        
    if not chapter.source_url:
        raise HTTPException(400, "Current chapter has no source_url to fetch from.")

    # SSRF guard: block requests to internal/private IPs
    from services.security import validate_external_url
    validate_external_url(chapter.source_url)

    next_url = None
    next_title = None

    ws = get_db_workspace(db)

    if is_domain(chapter.source_url, "novalpie.cc"):
        try:
            from services.scrapers.novalpie import NovalpieAdapter
            novalpie = NovalpieAdapter(workspace=ws)
            next_info = await novalpie.get_next_chapter(chapter.source_url)
            if next_info:
                next_url, next_title = next_info
        except Exception as e:
            print(f"⚠️ [Novalpie] Error resolving next chapter: {e}")
    elif is_domain(chapter.source_url, "sfacg.com"):
        try:
            from services.scrapers.sfacg import SFACGAdapter
            sfacg = SFACGAdapter()
            next_info = await sfacg.get_next_chapter(chapter.source_url)
            if next_info:
                next_url, next_title = next_info
        except Exception as e:
            print(f"⚠️ [SFACG] Error resolving next chapter: {e}")
    else:
        try:
            current_html, current_final_url = await fetch_html_adaptive(chapter.source_url, workspace=ws)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Failed to fetch chapter HTML: {e}")

        next_info = find_next_chapter_link(current_html, current_final_url)
        # If current page only links to an intra-chapter sub-page (e.g. 101_2.html), walk sub-pages
        # to find the true next-chapter link at the end of the split chapter.
        if (not next_info or _is_subpage_url_of(next_info[0], current_final_url)) and find_next_subpage_link(current_html, current_final_url):
            _, last_sub_html, last_sub_url = await stitch_subpages_markdown(
                current_html, current_final_url, "", workspace=ws
            )
            next_info = find_next_chapter_link(last_sub_html, last_sub_url)
        if next_info:
            next_url, next_title = next_info

    if not next_url:
        raise HTTPException(404, "Could not find a 'Next Chapter' link on the page.")

    validate_external_url(next_url)

    # Check if next_url is already in the thread
    existing = db.execute(select(Chapter).where(Chapter.thread_id == thread_id, Chapter.source_url == next_url)).scalar_one_or_none()
    if existing:
        return {"success": True, "chapter_id": existing.id, "message": "Chapter already exists."}

    # Fetch and parse the new chapter content
    if is_domain(next_url, "novalpie.cc"):
        from services.scrapers.novalpie import NovalpieAdapter
        novalpie = NovalpieAdapter(workspace=ws)
        parsed_title, markdown = await novalpie.scrape_chapter_content(next_url)
    elif is_domain(next_url, "sfacg.com"):
        from services.scrapers.sfacg import SFACGAdapter
        sfacg = SFACGAdapter()
        parsed_title, markdown = await sfacg.scrape_chapter_content(next_url)
    else:
        try:
            next_html, next_final_url = await fetch_html_adaptive(next_url, workspace=ws)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Failed to fetch next chapter URL ({next_url}): {e}")

        parsed_title, markdown = html_to_markdown(next_html, url=next_final_url)
        markdown, _, _ = await stitch_subpages_markdown(next_html, next_final_url, markdown, workspace=ws)

    is_vip = False
    if "/vip/" in next_url.lower():
        is_vip = True
    elif parsed_title and "VIP章节" in parsed_title:
        is_vip = True
    elif not markdown or len(markdown) < 50:
        if not (is_domain(next_url, "novalpie.cc") or is_domain(next_url, "sfacg.com")):
            is_vip = True

    if is_vip:
        markdown = "[VIP CHAPTER] Bab ini terkunci atau tidak dapat diakses (VIP)."

    # Get max order
    max_order = db.execute(
        select(func.max(Chapter.order)).where(Chapter.thread_id == thread_id)
    ).scalar() or chapter.order

    new_chapter = Chapter(
        thread_id=thread_id,
        order=max_order + 1,
        title_original=parsed_title or next_title or "Untitled Next Chapter",
        content_original=markdown,
        source_url=next_url,
        translation_status="vip" if is_vip else "idle"
    )
    db.add(new_chapter)
    db.commit()

    return {"success": True, "chapter_id": new_chapter.id}


class CrawlNextChaptersRequest(BaseModel):
    start_chapter_id: Optional[int] = None
    custom_start_url: Optional[str] = None
    count: int = 10


@router.post("/threads/{thread_id}/crawl-next")
async def crawl_next_chapters(
    thread_id: int,
    req: CrawlNextChaptersRequest,
    request: Request,
):
    """Crawl N upcoming chapters sequentially from the web using Next links with real-time SSE progress."""
    ws = resolve_workspace(request)

    async def crawl_stream_generator():
        db = SessionLocal(workspace=ws)
        try:
            # 1. Verify thread
            thread = db.execute(select(Thread).where(Thread.id == thread_id)).scalar_one_or_none()
            if not thread:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Thread not found'})}\n\n"
                return

            # Get current max order
            current_max_order = db.execute(
                select(func.max(Chapter.order)).where(Chapter.thread_id == thread_id)
            ).scalar() or 0

            # 2. Determine starting chapter / URL
            start_chapter = None
            current_url = None
            start_title = "Web Source"
            start_order = current_max_order

            if req.custom_start_url and req.custom_start_url.strip().startswith(("http://", "https://")):
                current_url = req.custom_start_url.strip()
                start_title = "Custom URL"
            elif req.start_chapter_id:
                start_chapter = db.execute(
                    select(Chapter).where(Chapter.id == req.start_chapter_id, Chapter.thread_id == thread_id)
                ).scalar_one_or_none()
                if start_chapter and start_chapter.source_url:
                    current_url = start_chapter.source_url
                    start_title = start_chapter.title_original or f"Chapter {start_chapter.order}"
                    start_order = start_chapter.order
            else:
                # 1st try: chapter with highest order that has source_url
                start_chapter = db.execute(
                    select(Chapter)
                    .where(Chapter.thread_id == thread_id, Chapter.source_url.isnot(None), Chapter.source_url != "")
                    .order_by(Chapter.order.desc())
                ).scalars().first()
                if start_chapter and start_chapter.source_url:
                    current_url = start_chapter.source_url
                    start_title = start_chapter.title_original or f"Chapter {start_chapter.order}"
                    start_order = start_chapter.order
                elif thread.source_url and thread.source_url.strip().startswith(("http://", "https://")):
                    current_url = thread.source_url.strip()
                    start_title = thread.title

            if not current_url:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No valid web source URL found to start crawling. Please provide a starting URL or import from web.'})}\n\n"
                return

            target_count = max(1, min(req.count, 50))
            created_chapters = []
            visited_urls = {current_url}

            yield f"data: {json.dumps({'type': 'start', 'start_order': start_order, 'start_title': start_title, 'target_count': target_count})}\n\n"

            for step in range(1, target_count + 1):
                # A. Fetch next link
                next_url = None
                next_title = None

                if is_domain(current_url, "novalpie.cc"):
                    try:
                        from services.scrapers.novalpie import NovalpieAdapter
                        novalpie = NovalpieAdapter(workspace=ws)
                        next_info = await novalpie.get_next_chapter(current_url)
                        if next_info:
                            next_url, next_title = next_info
                    except Exception as e:
                        print(f"⚠️ [Novalpie] Error resolving next chapter in crawl stream: {e}")
                elif is_domain(current_url, "sfacg.com"):
                    try:
                        from services.scrapers.sfacg import SFACGAdapter
                        sfacg = SFACGAdapter()
                        next_info = await sfacg.get_next_chapter(current_url)
                        if next_info:
                            next_url, next_title = next_info
                    except Exception as e:
                        print(f"⚠️ [SFACG] Error resolving next chapter in crawl stream: {e}")
                else:
                    try:
                        current_html, current_final_url = await fetch_html_adaptive(current_url, workspace=ws)
                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to fetch URL ({current_url}): {e}'})}\n\n"
                        break

                    next_info = find_next_chapter_link(current_html, current_final_url)
                    if (not next_info or _is_subpage_url_of(next_info[0], current_final_url)) and find_next_subpage_link(current_html, current_final_url):
                        _, last_sub_html, last_sub_url = await stitch_subpages_markdown(
                            current_html, current_final_url, "", workspace=ws
                        )
                        next_info = find_next_chapter_link(last_sub_html, last_sub_url)
                    if next_info and next_info[0] != current_url:
                        next_url, next_title = next_info

                if not next_url:
                    yield f"data: {json.dumps({'type': 'complete', 'fetched_count': len(created_chapters), 'reason': 'no_next_link', 'message': f'End of web chapters reached. Scraped {len(created_chapters)} new chapters.'})}\n\n"
                    break

                if next_url in visited_urls:
                    yield f"data: {json.dumps({'type': 'complete', 'fetched_count': len(created_chapters), 'reason': 'loop_detected', 'message': f'Loop detected. Scraped {len(created_chapters)} new chapters.'})}\n\n"
                    break
                visited_urls.add(next_url)

                # B. Check if next_url is already in database
                existing = db.execute(
                    select(Chapter).where(Chapter.thread_id == thread_id, Chapter.source_url == next_url)
                ).scalar_one_or_none()

                if existing:
                    current_url = next_url
                    yield f"data: {json.dumps({'type': 'progress', 'current': step, 'total': target_count, 'status': 'skipped_existing', 'chapter': {'id': existing.id, 'order': existing.order, 'title': existing.title_original}})}\n\n"
                    continue

                # C. Fetch and parse next chapter content (Retry up to 3 times on failure)
                max_fetch_attempts = 3
                parsed_title, markdown = None, None
                for fetch_attempt in range(1, max_fetch_attempts + 1):
                    try:
                        if is_domain(next_url, "novalpie.cc"):
                            from services.scrapers.novalpie import NovalpieAdapter
                            novalpie = NovalpieAdapter(workspace=ws)
                            parsed_title, markdown = await novalpie.scrape_chapter_content(next_url)
                        elif is_domain(next_url, "sfacg.com"):
                            from services.scrapers.sfacg import SFACGAdapter
                            sfacg = SFACGAdapter()
                            parsed_title, markdown = await sfacg.scrape_chapter_content(next_url)
                        else:
                            next_html, next_final_url = await fetch_html_adaptive(next_url, workspace=ws)
                            parsed_title, markdown = html_to_markdown(next_html, url=next_final_url)
                            markdown, _, _ = await stitch_subpages_markdown(
                                next_html, next_final_url, markdown, workspace=ws
                            )

                        # Check if successful content extracted
                        if markdown and len(markdown.strip()) >= 50:
                            err_keywords = ["加载章节内容失败", "请求过于频繁", "请稍后再试", "Ray ID:", "Cloudflare Turnstile blocked"]
                            if not any(k in markdown for k in err_keywords):
                                break
                    except Exception as e:
                        print(f"⚠️ [Crawl Attempt {fetch_attempt}/{max_fetch_attempts}] Error scraping {next_url}: {e}")

                    if fetch_attempt < max_fetch_attempts:
                        retry_label = "Playwright/Browser" if is_domain(next_url, "novalpie.cc") else "Network/HTTP"
                        yield f"data: {json.dumps({'type': 'log', 'message': f'Gagal memuat bab, mencoba ulang {retry_label} (Percobaan {fetch_attempt + 1}/{max_fetch_attempts})...'})}\n\n"
                        await asyncio.sleep(fetch_attempt * 2)
                is_vip = False
                if "/vip/" in next_url.lower():
                    is_vip = True
                elif parsed_title and "VIP章节" in parsed_title:
                    is_vip = True
                elif not markdown or len(markdown) < 50:
                    if not (is_domain(next_url, "novalpie.cc") or is_domain(next_url, "sfacg.com")):
                        is_vip = True


                if is_vip:
                    markdown = "[VIP CHAPTER] Bab ini terkunci atau tidak dapat diakses (VIP)."

                current_max_order += 1
                new_chapter = Chapter(
                    thread_id=thread_id,
                    order=current_max_order,
                    title_original=parsed_title or next_title or f"Chapter {current_max_order}",
                    content_original=markdown,
                    source_url=next_url,
                    translation_status="vip" if is_vip else "idle"
                )
                db.add(new_chapter)
                db.commit()
                db.refresh(new_chapter)

                created_chapters.append({
                    "id": new_chapter.id,
                    "order": new_chapter.order,
                    "title": new_chapter.title_original,
                    "is_vip": is_vip
                })

                yield f"data: {json.dumps({'type': 'progress', 'current': len(created_chapters), 'total': target_count, 'status': 'created', 'chapter': {'id': new_chapter.id, 'order': new_chapter.order, 'title': new_chapter.title_original, 'is_vip': is_vip}})}\n\n"

                if is_vip:
                    yield f"data: {json.dumps({'type': 'complete', 'fetched_count': len(created_chapters), 'reason': 'vip_reached', 'message': f'Stopped at VIP chapter ({new_chapter.title_original}). Scraped {len(created_chapters)} chapters.'})}\n\n"
                    break

                current_url = next_url

                # Anti-bot delay between scrapes
                if step < target_count:
                    await asyncio.sleep(random.uniform(1.2, 2.2))

            else:
                # Loop completed target count
                yield f"data: {json.dumps({'type': 'complete', 'fetched_count': len(created_chapters), 'reason': 'target_reached', 'message': f'Successfully crawled {len(created_chapters)} chapters.'})}\n\n"

        except Exception as general_err:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Unexpected crawl error: {general_err}'})}\n\n"
        finally:
            db.close()

        yield "data: [DONE]\n\n"

    return StreamingResponse(crawl_stream_generator(), media_type="text/event-stream")
