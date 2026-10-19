"""
Post-extraction helpers for generic (non-dedicated) novel sites: picking the chapter title
instead of the site name, stripping pirate-site watermark lines, and telling a locked (VIP)
chapter apart from a page whose content simply failed to extract.
"""

import re
from typing import Iterator, Optional

from bs4 import BeautifulSoup, Tag

VIP_PLACEHOLDER = "[VIP CHAPTER] Bab ini terkunci atau tidak dapat diakses (VIP)."

# --- chapter title -------------------------------------------------------------------------

_CHAPTER_TITLE_RE = re.compile(
    r"第\s*[0-9零〇一二两三四五六七八九十百千万]+\s*[章节節话話回卷集篇幕]"
    r"|\b(?:chapter|ch\.?|episode|ep\.?)\s*\d+"
    r"|(?:제\s*)?\d+\s*화",
    re.IGNORECASE,
)
_SITE_CHROME_RE = re.compile(r"(?<![a-z0-9])(logo|brand|site-?name|site-?title)", re.IGNORECASE)
_TITLE_HEADING_SELECTORS = ("h1", "h2", "h3", ".chapter-title", ".ep-title", ".reader-title")
_TITLE_MAX_CHARS = 220
# No leading/trailing \s* here: on a long run of spaces that backtracks quadratically.
_TITLE_TAG_SEPARATOR_RE = re.compile(r"_|\||｜|\s[-–—]\s")


def _is_site_chrome(el: Tag) -> bool:
    """Logo / site-name headings (or headings inside <nav>) name the site, not the chapter."""
    for node in (el, *el.parents):
        if not isinstance(node, Tag) or node.name in ("body", "html"):
            break
        if node.name == "nav":
            return True
        classes = node.get("class") or []
        marker = f"{node.get('id') or ''} {' '.join(classes) if isinstance(classes, list) else classes}"
        if _SITE_CHROME_RE.search(marker):
            return True
    return False


def _title_candidates(soup: BeautifulSoup) -> Iterator[Tag]:
    for selector in _TITLE_HEADING_SELECTORS:
        for el in soup.select(selector):
            text = el.get_text(strip=True)
            if text and len(text) <= _TITLE_MAX_CHARS and not _is_site_chrome(el):
                yield el


def find_chapter_heading(soup: BeautifulSoup) -> Optional[Tag]:
    """First heading that reads like a chapter title (第十章 / Chapter 12 / 12화)."""
    return next((el for el in _title_candidates(soup) if _CHAPTER_TITLE_RE.search(el.get_text(strip=True))), None)


def find_plain_heading(soup: BeautifulSoup) -> Optional[Tag]:
    """First non-logo heading, h1 before h2 before h3."""
    return next(_title_candidates(soup), None)


def clean_title_tag_text(text: str) -> str:
    """`第五章 夜雨_某书_某站` -> `第五章 夜雨`: keep the chapter segment, else the first one."""
    text = text.strip()[:_TITLE_MAX_CHARS]
    segments = [s.strip() for s in _TITLE_TAG_SEPARATOR_RE.split(text) if s.strip()]
    if not segments:
        return text
    return next((s for s in segments if _CHAPTER_TITLE_RE.search(s)), segments[0])


# --- watermarks ----------------------------------------------------------------------------

_DOMAIN = r"(?:https?://)?(?:[a-z0-9-]+\.)+(?:com|net|org|cc|cn|la|io|me|co|info|xyz|tw|top|vip|so)\b"
_CJK_SITE_NOTICE = (
    r"(?:请?记住本书首发域名|本书首发|(?:天才)?一秒记住(?:本站地址)?|记住本站(?:地址)?"
    r"|(?:笔趣阁)?手机版阅读网址|最快更新|请?收藏本站)"
)
# Only whole watermark spans are removed, never the sentence around them: each notice must carry
# the site's domain or 【bracketed】 address, or be one of the fixed pagination/report phrases.
_WATERMARK_SPAN_RE = re.compile(
    rf"{_CJK_SITE_NOTICE}[^。\n]{{0,40}}?(?:{_DOMAIN}|【[^】\n]{{1,40}}】)"
    r"(?:[，,]?[^。！!\n]{0,20}?无弹窗[^。！!\n]{0,10})?[。！!]?"
    r"|本章未完[，,]?请?点击下一页继续阅读[》>。！!]*"
    r"|章节错误[，,]?点此举报(?:[(（][^)）\n]{0,10}[)）])?"
    r"|加入书签[，,]?方便(?:下次)?阅读[。！!]?"
    rf"|(?:this chapter (?:is )?)?upload(?:ed)? first at\s+{_DOMAIN}\.?"
    rf"|(?:the )?source of this (?:content|chapter) is\s+{_DOMAIN}\.?"
    rf"|(?:please )?(?:read|find) (?:the )?latest chapters? (?:at|on)\s+{_DOMAIN}\.?"
    r"|find authorized novels in webnovel[^\n]*?(?:for visiting\.?|$)",
    re.IGNORECASE,
)
_LEFTOVER_PUNCT_RE = re.compile(r"[\s，,。.！!：:;；、]*")


def _strip_watermark_line(line: str) -> str:
    stripped = _WATERMARK_SPAN_RE.sub("", line)
    if stripped == line:
        return line
    stripped = re.sub(r"[ \t]{2,}", " ", stripped).strip()
    return "" if _LEFTOVER_PUNCT_RE.fullmatch(stripped) else stripped


def strip_watermarks(text: str) -> str:
    """Remove pirate-site watermark spans (首发域名 + domain, "upload first at <domain>", ...)."""
    return "\n".join(_strip_watermark_line(line) for line in text.split("\n"))


# --- VIP vs. failed extraction -------------------------------------------------------------

# A generic page yielding less than this after extraction was not parsed; it is not locked.
_MIN_GENERIC_CONTENT_CHARS = 50
# The whole body must be the paywall notice, so a chapter that merely mentions 订阅/VIP is not locked.
_VIP_NOTICE_RE = re.compile(
    r"^.{0,40}(?:VIP章节[，,]?请?订阅|订阅后(?:才能)?阅读|购买本章|本章为付费章节).{0,40}$", re.DOTALL
)


def is_vip_chapter(
    url: Optional[str], title: Optional[str], markdown: Optional[str], *, inspect_content: bool = True
) -> bool:
    """
    Only explicit lock signals count: a /vip/ URL, a VIP title, or (for generic sites, where
    `inspect_content` is True) a body that is nothing but a paywall notice.
    """
    if "/vip/" in (url or "").lower():
        return True
    if title and "VIP章节" in title:
        return True
    return inspect_content and bool(_VIP_NOTICE_RE.match((markdown or "").strip()))


def is_extraction_empty(markdown: Optional[str]) -> bool:
    return len((markdown or "").strip()) < _MIN_GENERIC_CONTENT_CHARS


# --- link labels and navigation blocks -----------------------------------------------------

_LABEL_ATTRS = ("aria-label", "title")
_ICON_CHILD_TAGS = ("img", "i", "span", "svg")
_WORD_CHAR_RE = re.compile(r"\w")


def anchor_label(a: Tag) -> str:
    """
    Visible text of a link; for icon-only links (no letters/CJK, e.g. `<i>` or `›`) fall back to
    the anchor's aria-label/title, then an icon child's alt/aria-label/title.
    """
    text = a.get_text(strip=True)
    if _WORD_CHAR_RE.search(text):
        return text
    for attr in _LABEL_ATTRS:
        value = str(a.get(attr) or "").strip()
        if value:
            return value
    for child in a.find_all(_ICON_CHILD_TAGS):
        for attr in ("alt", *_LABEL_ATTRS):
            value = str(child.get(attr) or "").strip()
            if value:
                return value
    return text


# A block whose links make up most of its (short) text is navigation, not prose.
_NAV_BLOCK_TAGS = ("div", "p", "ul", "ol", "li", "section", "table", "tr", "td", "dl", "dd", "center")
_NAV_BLOCK_MAX_CHARS = 80
_NAV_BLOCK_MIN_LINK_SHARE = 0.6


# Link-heavy alone is not enough: short dialogue with linked names (李逍遥？) and linked paywall
# notices look the same, so at least one link must also read like site navigation.
_NAV_LINK_WORD_RE = re.compile(
    r"上一[章页頁节節话話]|下一[章页頁节節话話]|目录|目錄|首页|首頁|书架|書架|书页|返回|章节列表|加入书签"
    r"|\b(?:prev(?:ious)?|next|home|index|contents|toc|library|chapter list)\b",
    re.IGNORECASE,
)


def _is_nav_block(el: Tag) -> bool:
    text = el.get_text(strip=True)
    if not text or len(text) > _NAV_BLOCK_MAX_CHARS or _VIP_NOTICE_RE.match(text):
        return False
    anchors = el.find_all("a")
    link_len = sum(len(a.get_text(strip=True)) for a in anchors)
    if link_len < len(text) * _NAV_BLOCK_MIN_LINK_SHARE:
        return False
    return any(_NAV_LINK_WORD_RE.search(anchor_label(a)) for a in anchors)


def remove_nav_blocks(content_el: Tag) -> None:
    """Decompose short link-dominated blocks inside `content_el` (never `content_el` itself)."""
    for el in content_el.find_all(_NAV_BLOCK_TAGS):
        if not getattr(el, "decomposed", False) and _is_nav_block(el):
            el.decompose()
