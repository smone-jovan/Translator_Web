"""
Scrapling-inspired Adaptive DOM Engine for BeautifulSoup & Playwright.
Provides structural & semantic element relocation, zero-shot prose density scoring,
and Scrapling-compatible AdaptivePage & AdaptiveNode classes without extra dependencies.
"""

import json
import os
import re
import threading
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Union
from bs4 import BeautifulSoup, Tag

_CACHE_LOCK = threading.Lock()
_SIGNATURE_MEMORY_CACHE: Dict[str, Dict[str, Any]] = {}
_DEFAULT_STORE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "adaptive_selectors.json"

_BOILERPLATE_TAGS = {
    "script", "style", "nav", "footer", "header", "aside",
    "noscript", "form", "button", "svg", "canvas", "iframe",
}
_BOILERPLATE_ATTR_RE = re.compile(
    r"(?<![a-zA-Z0-9])(ads?[_-]|banner|sidebar|menu|navbar|nav-|footer|comment|social|share|popup|modal|cookie|breadcrumb|pagination|recommend)",
    re.IGNORECASE,
)
_DYNAMIC_TOKEN_RE = re.compile(r"^(?:css|sc|svelte|jsx|v|data)-[a-z0-9]{4,}$|^\d+$", re.IGNORECASE)
_PROSE_PUNCT_RE = re.compile(r"[。！？；，、“”‘’.!?;,\"']")


def _extract_domain(url_or_domain: Optional[str]) -> str:
    if not url_or_domain:
        return "default"
    raw = url_or_domain.strip().lower()
    if "://" in raw:
        try:
            host = urllib.parse.urlparse(raw).hostname or raw
            return host.removeprefix("www.") or "default"
        except Exception:
            return raw
    return raw.removeprefix("www.") or "default"


def _normalize_tokens(values: Iterable[str]) -> List[str]:
    tokens: List[str] = []
    for val in values:
        if not val:
            continue
        for part in re.split(r"[\s_\-:]+", str(val).strip().lower()):
            if part and not _DYNAMIC_TOKEN_RE.match(part) and len(part) >= 2 and part not in tokens:
                tokens.append(part)
    return tokens[:12]


def _get_classes(el: Optional[Tag]) -> List[str]:
    if not el or not isinstance(el, Tag) or not getattr(el, "attrs", None):
        return []
    raw = el.get("class", [])
    if isinstance(raw, list):
        return [str(c) for c in raw if c]
    if isinstance(raw, str):
        return [c for c in raw.split() if c]
    return []


def _get_dom_depth(el: Tag) -> int:
    depth = 0
    curr = el.parent
    while isinstance(curr, Tag) and depth < 30:
        depth += 1
        curr = curr.parent
    return depth


def _jaccard_similarity(a: Sequence[str], b: Sequence[str]) -> float:
    set_a, set_b = set(a), set(b)
    if not set_a and not set_b:
        return 0.5
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


class AdaptiveDOM:
    """Scrapling-style Adaptive DOM relocation and prose-density extraction engine."""

    @staticmethod
    def compute_signature(el: Tag) -> Dict[str, Any]:
        if not isinstance(el, Tag):
            return {}
        el_id = str(el.get("id", "") or "")
        classes = _get_classes(el)
        attr_names = sorted(
            k.lower() for k in (el.attrs or {}).keys() if k.lower() not in ("class", "id", "style")
        )
        parent = el.parent if isinstance(el.parent, Tag) else None
        grandparent = parent.parent if (parent and isinstance(parent.parent, Tag)) else None

        child_counts: Dict[str, int] = {}
        for child in el.find_all(True, recursive=False):
            if isinstance(child, Tag) and child.name:
                child_counts[child.name] = child_counts.get(child.name, 0) + 1
        top_child_tags = [k for k, _ in sorted(child_counts.items(), key=lambda x: x[1], reverse=True)[:5]]

        text_content = el.get_text(strip=True)
        text_len = len(text_content)
        len_bucket = "short" if text_len < 120 else ("medium" if text_len < 600 else "long")
        link_text_len = sum(len(a.get_text(strip=True)) for a in el.find_all("a"))
        link_density = round(link_text_len / max(1, text_len), 3)

        return {
            "tag": (el.name or "").lower(),
            "id_tokens": _normalize_tokens([el_id]),
            "class_tokens": _normalize_tokens(classes),
            "attr_names": attr_names[:8],
            "parent_tag": (parent.name or "").lower() if parent else "",
            "parent_class_tokens": _normalize_tokens(_get_classes(parent)) if parent else [],
            "grandparent_tag": (grandparent.name or "").lower() if grandparent else "",
            "depth": _get_dom_depth(el),
            "top_child_tags": top_child_tags,
            "len_bucket": len_bucket,
            "link_density": link_density,
            "p_count": len(el.find_all("p")),
            "br_count": len(el.find_all("br")),
        }

    @staticmethod
    def save_signature(domain: str, key: str, signature: Dict[str, Any], store_path: Optional[Path] = None) -> None:
        if not signature:
            return
        cache_key = f"{_extract_domain(domain)}::{key}"
        target_path = store_path or _DEFAULT_STORE_PATH
        with _CACHE_LOCK:
            _SIGNATURE_MEMORY_CACHE[cache_key] = signature
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                disk_data: Dict[str, Any] = {}
                if target_path.exists():
                    try:
                        disk_data = json.loads(target_path.read_text(encoding="utf-8"))
                    except Exception:
                        disk_data = {}
                disk_data[cache_key] = signature
                tmp_path = target_path.with_suffix(".tmp")
                tmp_path.write_text(json.dumps(disk_data, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(tmp_path, target_path)
            except Exception:
                pass

    @staticmethod
    def load_signature(domain: str, key: str, store_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        cache_key = f"{_extract_domain(domain)}::{key}"
        target_path = store_path or _DEFAULT_STORE_PATH
        with _CACHE_LOCK:
            if cache_key in _SIGNATURE_MEMORY_CACHE:
                return _SIGNATURE_MEMORY_CACHE[cache_key]
            if target_path.exists():
                try:
                    disk_data = json.loads(target_path.read_text(encoding="utf-8"))
                    if isinstance(disk_data, dict) and cache_key in disk_data:
                        _SIGNATURE_MEMORY_CACHE[cache_key] = disk_data[cache_key]
                        return disk_data[cache_key]
                except Exception:
                    pass
        return None

    @staticmethod
    def compute_similarity(signature: Dict[str, Any], candidate: Tag, role: str = "content") -> float:
        if not signature or not isinstance(candidate, Tag):
            return 0.0
        cand_sig = AdaptiveDOM.compute_signature(candidate)
        if not cand_sig or cand_sig["tag"] in _BOILERPLATE_TAGS:
            return 0.0

        score = 0.0
        sig_tag, cand_tag = signature.get("tag", ""), cand_sig.get("tag", "")
        content_tags = {"article", "section", "main", "div"}
        title_tags = {"h1", "h2", "h3", "header", "div", "span"}
        if sig_tag == cand_tag:
            score += 0.22
        elif role == "content" and sig_tag in content_tags and cand_tag in content_tags:
            score += 0.14
        elif role == "title" and sig_tag in title_tags and cand_tag in title_tags:
            score += 0.14

        sig_tokens = list(signature.get("id_tokens", [])) + list(signature.get("class_tokens", []))
        cand_tokens = list(cand_sig.get("id_tokens", [])) + list(cand_sig.get("class_tokens", []))
        score += 0.20 * _jaccard_similarity(sig_tokens, cand_tokens)
        score += 0.10 * _jaccard_similarity(signature.get("attr_names", []), cand_sig.get("attr_names", []))

        if signature.get("parent_tag") and signature.get("parent_tag") == cand_sig.get("parent_tag"):
            score += 0.10
        score += 0.06 * _jaccard_similarity(
            signature.get("parent_class_tokens", []), cand_sig.get("parent_class_tokens", [])
        )
        if signature.get("grandparent_tag") and signature.get("grandparent_tag") == cand_sig.get("grandparent_tag"):
            score += 0.04

        depth_diff = abs(int(signature.get("depth", 0)) - int(cand_sig.get("depth", 0)))
        score += 0.08 if depth_diff == 0 else (0.05 if depth_diff <= 2 else (0.02 if depth_diff <= 4 else 0.0))

        score += 0.10 * _jaccard_similarity(signature.get("top_child_tags", []), cand_sig.get("top_child_tags", []))
        if signature.get("len_bucket") == cand_sig.get("len_bucket"):
            score += 0.10
        elif role == "content" and cand_sig.get("len_bucket") in ("medium", "long"):
            score += 0.05

        if role == "content":
            if cand_sig.get("link_density", 0.0) > 0.45:
                score *= 0.35
            if cand_sig.get("len_bucket") == "short":
                score *= 0.40
        elif role == "title":
            text_len = len(candidate.get_text(strip=True))
            if text_len == 0 or text_len > 260:
                score *= 0.25

        return round(min(1.0, score), 4)

    @staticmethod
    def find_similar_element(
        soup: BeautifulSoup, signature: Dict[str, Any], *, role: str = "content", min_score: float = 0.42
    ) -> Optional[Tag]:
        if not signature or not soup:
            return None
        candidate_tags = ["h1", "h2", "h3", "div", "span", "header", "p"] if role == "title" else ["article", "main", "section", "div"]
        best_el: Optional[Tag] = None
        best_score = min_score
        for el in soup.find_all(candidate_tags):
            if isinstance(el, Tag):
                sim = AdaptiveDOM.compute_similarity(signature, el, role=role)
                if sim > best_score:
                    best_score = sim
                    best_el = el
        return best_el

    @staticmethod
    def find_best_content_container(soup: BeautifulSoup, min_chars: int = 80) -> Optional[Tag]:
        if not soup:
            return None
        best_el: Optional[Tag] = None
        best_score = 0.0
        for el in soup.find_all(["article", "main", "section", "div", "td", "dd"]):
            if not isinstance(el, Tag) or el.name in _BOILERPLATE_TAGS:
                continue
            el_id = str(el.get("id", "") or "")
            classes_str = " ".join(_get_classes(el))
            if _BOILERPLATE_ATTR_RE.search(el_id) or _BOILERPLATE_ATTR_RE.search(classes_str):
                continue
            raw_text = el.get_text(" ", strip=True)
            text_len = len(raw_text)
            if text_len < min_chars:
                continue
            link_text_len = sum(len(a.get_text(strip=True)) for a in el.find_all("a"))
            link_density = link_text_len / max(1, text_len)
            if link_density > 0.50:
                continue
            p_tags = el.find_all("p", recursive=False) or el.find_all("p")
            br_tags = el.find_all("br")
            punct_count = len(_PROSE_PUNCT_RE.findall(raw_text))
            large_child_divs = sum(
                1 for child in el.find_all(["div", "article", "section"], recursive=False)
                if len(child.get_text(strip=True)) > text_len * 0.75
            )
            score = (
                min(text_len, 12000) * 0.15
                + len(p_tags) * 35.0
                + min(len(br_tags), 120) * 12.0
                + min(punct_count, 300) * 8.0
            )
            combined_meta = f"{el_id} {classes_str}".lower()
            if any(k in combined_meta for k in ("chapter", "reader", "content", "novel", "article", "text", "body")):
                score *= 1.35
            if el.name == "article":
                score *= 1.20
            if large_child_divs > 0:
                score *= 0.55
            score *= max(0.15, 1.0 - link_density * 1.4)
            if score > best_score:
                best_score = score
                best_el = el
        return best_el

    @staticmethod
    def find_best_title_element(soup: BeautifulSoup, content_el: Optional[Tag] = None) -> Optional[Tag]:
        if not soup:
            return None
        scopes = [content_el, soup] if content_el is not None else [soup]
        for scope in scopes:
            if scope is None:
                continue
            for sel in ("h1", "h2", ".chapter-title", ".ep-title", ".reader-title", "[class*='chapter-title']", "[class*='title']", "h3"):
                try:
                    for cand in scope.select(sel):
                        txt = cand.get_text(strip=True)
                        if 1 <= len(txt) <= 220:
                            return cand
                except Exception:
                    continue
        title_tag = soup.find("title")
        return title_tag if isinstance(title_tag, Tag) else None

    @classmethod
    def select_one(
        cls,
        soup: BeautifulSoup,
        selectors: Sequence[Union[str, Callable[[BeautifulSoup], Optional[Tag]]]],
        *,
        domain: str = "default",
        key: str = "content",
        role: str = "content",
        adaptive: bool = True,
        auto_save: bool = True,
        min_text_len: int = 0,
        store_path: Optional[Path] = None,
    ) -> Optional[Tag]:
        if not soup:
            return None
        for sel in selectors:
            matched: Optional[Tag] = None
            try:
                if callable(sel):
                    matched = sel(soup)
                elif isinstance(sel, str) and sel.strip():
                    matched = soup.select_one(sel)
            except Exception:
                matched = None
            if isinstance(matched, Tag):
                if min_text_len > 0 and len(matched.get_text(strip=True)) < min_text_len:
                    continue
                if auto_save:
                    cls.save_signature(domain, key, cls.compute_signature(matched), store_path=store_path)
                return matched

        if not adaptive:
            return None

        saved_sig = cls.load_signature(domain, key, store_path=store_path)
        if saved_sig:
            relocated = cls.find_similar_element(soup, saved_sig, role=role)
            if isinstance(relocated, Tag) and (min_text_len <= 0 or len(relocated.get_text(strip=True)) >= min_text_len):
                return relocated

        if role == "content":
            best_container = cls.find_best_content_container(soup, min_chars=max(40, min_text_len))
            if isinstance(best_container, Tag):
                if auto_save:
                    cls.save_signature(domain, key, cls.compute_signature(best_container), store_path=store_path)
                return best_container
        elif role == "title":
            return cls.find_best_title_element(soup)
        return None


class AdaptiveNode:
    """Scrapling-compatible DOM node wrapper around BeautifulSoup Tag."""

    def __init__(self, tag: Tag, domain: str = "default"):
        self._tag = tag
        self._domain = domain

    @property
    def text(self) -> str:
        return self._tag.get_text(" ", strip=True) if self._tag else ""

    @property
    def attrib(self) -> Dict[str, Any]:
        return dict(self._tag.attrs) if isinstance(self._tag, Tag) and self._tag.attrs else {}

    def get_all_text(self, strip: bool = True, separator: str = "\n") -> str:
        return self._tag.get_text(separator=separator, strip=strip) if self._tag else ""

    def css(self, selector: str, *, adaptive: bool = False, auto_save: bool = False) -> List["AdaptiveNode"]:
        if not isinstance(self._tag, Tag):
            return []
        try:
            matches = self._tag.select(selector)
        except Exception:
            matches = []
        if matches:
            if auto_save:
                AdaptiveDOM.save_signature(self._domain, selector, AdaptiveDOM.compute_signature(matches[0]))
            return [AdaptiveNode(m, domain=self._domain) for m in matches if isinstance(m, Tag)]
        if adaptive:
            role = "title" if any(k in selector.lower() for k in ("h1", "h2", "title")) else "content"
            relocated = AdaptiveDOM.select_one(
                self._tag, [selector], domain=self._domain, key=selector, role=role, adaptive=True, auto_save=auto_save
            )
            if relocated is not None:
                return [AdaptiveNode(relocated, domain=self._domain)]
        return []


class AdaptivePage:
    """Scrapling-compatible Page object for native Adaptive Playwright fallback."""

    def __init__(self, html: str, url: str = "", domain: Optional[str] = None, status: int = 200):
        self.html = html or ""
        self.url = url
        self.status = status
        self.domain = _extract_domain(domain or url)
        self.soup = BeautifulSoup(self.html, "html.parser")

    @property
    def text(self) -> str:
        return self.soup.get_text(" ", strip=True)

    def css(self, selector: str, *, adaptive: bool = True, auto_save: bool = False) -> List[AdaptiveNode]:
        try:
            matches = self.soup.select(selector)
        except Exception:
            matches = []
        if matches:
            if auto_save:
                AdaptiveDOM.save_signature(self.domain, selector, AdaptiveDOM.compute_signature(matches[0]))
            return [AdaptiveNode(m, domain=self.domain) for m in matches if isinstance(m, Tag)]
        if adaptive:
            role = "title" if any(k in selector.lower() for k in ("h1", "h2", "title")) else "content"
            relocated = AdaptiveDOM.select_one(
                self.soup, [selector], domain=self.domain, key=selector, role=role, adaptive=True, auto_save=auto_save
            )
            if relocated is not None:
                return [AdaptiveNode(relocated, domain=self.domain)]
        return []


_TITLE_SITE_SUFFIX_RE = re.compile(
    r"\s*(?:[-_|—–｜]\s*(?:[^-_|—–｜]{2,35}(?:小说网?|文学网?|阅读网?|书院|中文网|文庫|소설|Novel|Read|Online|Webnovel|Royal\s*Road|Scribble\s*Hub|Wattpad|Syosetu|Kakuyomu)[^-_|—–｜]*)|_最新章节.*|,最新章节.*|\(\s*全文在线阅读.*\))\s*$",
    re.IGNORECASE,
)
_AUTHOR_LABEL_RE = re.compile(
    r"(?:作\s*者|Author|저자|작가|著者|作者[:：])\s*[:：]?\s*([^\n\r|<>/\t]{1,50})",
    re.IGNORECASE,
)
_STATUS_LABEL_RE = re.compile(
    r"(?:状\s*态|Status|상태|状態)\s*[:：]?\s*(连载中?|连载|完结|完本|已完成|Ongoing|Completed|Hiatus|연재중|완결|連載中|完結)",
    re.IGNORECASE,
)


def _clean_extracted_title(raw_title: Optional[str]) -> str:
    if not raw_title:
        return ""
    cleaned = re.sub(r"\s+", " ", str(raw_title)).strip()
    cleaned = _TITLE_SITE_SUFFIX_RE.sub("", cleaned).strip()
    cleaned = re.sub(r"^【[^】]{1,12}】\s*", "", cleaned).strip()
    return cleaned or str(raw_title).strip()


def extract_universal_metadata(html: str, url: str = "") -> Dict[str, Optional[str]]:
    """
    Universal plug-and-play metadata extractor for generic novel TOC and chapter pages.
    Extracts title, original_title, author, cover_image, synopsis, genres, tags, status, and detail_url
    from og:novel:* tags, Schema.org JSON-LD, OpenGraph/Twitter meta tags, and common DOM patterns.
    """
    import urllib.parse

    result: Dict[str, Optional[str]] = {
        "title": None,
        "original_title": None,
        "author": None,
        "cover_image": None,
        "synopsis": None,
        "genres": None,
        "tags": None,
        "status": None,
        "detail_url": url or None,
    }
    if not html:
        return result

    soup = BeautifulSoup(html, "html.parser")

    def _resolve_url(candidate: Optional[str]) -> Optional[str]:
        if not candidate or not isinstance(candidate, str):
            return None
        c = candidate.strip()
        if not c or c.startswith("data:"):
            return None
        if url:
            return urllib.parse.urljoin(url, c)
        return c

    # 1. Meta tag scan (og:novel:*, OpenGraph, Twitter, standard meta)
    meta_map: Dict[str, str] = {}
    for m in soup.find_all("meta"):
        key = (m.get("property") or m.get("name") or m.get("itemprop") or "").strip().lower()
        val = (m.get("content") or "").strip()
        if key and val and key not in meta_map:
            meta_map[key] = val

    # Priority 1A: Chinese/Asian novel standard og:novel:*
    novel_title = (
        meta_map.get("og:novel:book_name")
        or meta_map.get("og:novel:title")
        or meta_map.get("book:title")
    )
    if novel_title:
        result["title"] = _clean_extracted_title(novel_title)
        result["original_title"] = result["title"]

    if meta_map.get("og:novel:author"):
        result["author"] = meta_map["og:novel:author"]
    if meta_map.get("og:novel:category"):
        result["genres"] = meta_map["og:novel:category"]
    if meta_map.get("og:novel:status"):
        result["status"] = meta_map["og:novel:status"]
    if meta_map.get("og:novel:read_url") or meta_map.get("og:novel:latest_chapter_url"):
        result["detail_url"] = _resolve_url(
            meta_map.get("og:novel:read_url") or meta_map.get("og:novel:latest_chapter_url")
        ) or result["detail_url"]

    # 2. Schema.org JSON-LD (<script type="application/ld+json">)
    for script in soup.find_all("script", type=re.compile(r"application/ld\+json", re.I)):
        raw_json = script.string or script.get_text(strip=True)
        if not raw_json:
            continue
        try:
            data = json.loads(raw_json)
        except Exception:
            continue

        items: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            if isinstance(data.get("@graph"), list):
                items.extend([x for x in data["@graph"] if isinstance(x, dict)])
            items.append(data)
        elif isinstance(data, list):
            items.extend([x for x in data if isinstance(x, dict)])

        for item in items:
            if not result["title"]:
                ld_title = item.get("name") or item.get("headline")
                if isinstance(ld_title, str) and ld_title.strip():
                    result["title"] = _clean_extracted_title(ld_title)
                    result["original_title"] = result["title"]
            if not result["author"]:
                ld_author = item.get("author") or item.get("creator")
                if isinstance(ld_author, dict):
                    ld_author = ld_author.get("name")
                elif isinstance(ld_author, list) and ld_author:
                    first_a = ld_author[0]
                    ld_author = first_a.get("name") if isinstance(first_a, dict) else str(first_a)
                if isinstance(ld_author, str) and ld_author.strip():
                    result["author"] = ld_author.strip()
            if not result["cover_image"]:
                ld_img = item.get("image") or item.get("thumbnailUrl")
                if isinstance(ld_img, dict):
                    ld_img = ld_img.get("url") or ld_img.get("contentUrl")
                elif isinstance(ld_img, list) and ld_img:
                    first_i = ld_img[0]
                    ld_img = first_i.get("url") if isinstance(first_i, dict) else str(first_i)
                if isinstance(ld_img, str) and ld_img.strip():
                    result["cover_image"] = _resolve_url(ld_img)
            if not result["synopsis"]:
                ld_desc = item.get("description")
                if isinstance(ld_desc, str) and ld_desc.strip():
                    result["synopsis"] = ld_desc.strip()
            if not result["genres"]:
                ld_genre = item.get("genre")
                if isinstance(ld_genre, list):
                    ld_genre = ", ".join(str(g).strip() for g in ld_genre if str(g).strip())
                if isinstance(ld_genre, str) and ld_genre.strip():
                    result["genres"] = ld_genre.strip()
            if not result["tags"]:
                ld_kw = item.get("keywords")
                if isinstance(ld_kw, list):
                    ld_kw = ", ".join(str(k).strip() for k in ld_kw if str(k).strip())
                if isinstance(ld_kw, str) and ld_kw.strip():
                    result["tags"] = ld_kw.strip()

    # 3. Standard OpenGraph / Twitter / HTML meta fallbacks
    if not result["title"]:
        og_title = meta_map.get("og:title") or meta_map.get("twitter:title") or meta_map.get("title")
        if og_title:
            result["title"] = _clean_extracted_title(og_title)
            result["original_title"] = result["title"]

    if not result["author"]:
        meta_author = (
            meta_map.get("author")
            or meta_map.get("book:author")
            or meta_map.get("article:author")
            or meta_map.get("twitter:creator")
        )
        if meta_author:
            result["author"] = meta_author.strip()

    if not result["cover_image"]:
        meta_img = (
            meta_map.get("og:image")
            or meta_map.get("twitter:image")
            or meta_map.get("image")
        )
        if meta_img:
            result["cover_image"] = _resolve_url(meta_img)

    if not result["synopsis"]:
        meta_desc = (
            meta_map.get("og:description")
            or meta_map.get("twitter:description")
            or meta_map.get("description")
        )
        if meta_desc:
            result["synopsis"] = meta_desc.strip()

    if not result["tags"] and meta_map.get("keywords"):
        result["tags"] = meta_map["keywords"].strip()

    # 4. DOM selector fallbacks for sites without rich meta tags
    if not result["title"]:
        for sel in ("#info h1", ".book-info h1", ".novel-info h1", ".book-title", ".novel-title", "h1", "title"):
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                result["title"] = _clean_extracted_title(el.get_text(strip=True))
                result["original_title"] = result["title"]
                break

    if not result["author"]:
        for sel in ('[itemprop="author"]', ".book-author", ".novel-author", ".author-name", ".author"):
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                txt = el.get_text(strip=True)
                m = _AUTHOR_LABEL_RE.search(txt)
                result["author"] = (m.group(1) if m else txt).strip()
                break
        if not result["author"]:
            info_text = soup.get_text("\n", strip=True)[:3000]
            m = _AUTHOR_LABEL_RE.search(info_text)
            if m:
                result["author"] = m.group(1).strip()

    if not result["cover_image"]:
        for sel in (
            '#fmimg img',
            '.book-img img',
            '.book-cover img',
            '.novel-cover img',
            '.cover img',
            'img[itemprop="image"]',
        ):
            img = soup.select_one(sel)
            if img:
                raw_src = img.get("data-src") or img.get("data-original") or img.get("src")
                resolved = _resolve_url(raw_src)
                if resolved:
                    result["cover_image"] = resolved
                    break

    if not result["synopsis"]:
        for sel in (
            '#intro',
            '.book-intro',
            '.novel-intro',
            '.synopsis',
            '.description',
            '[itemprop="description"]',
            '.intro',
        ):
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) >= 15:
                result["synopsis"] = el.get_text("\n", strip=True)
                break

    if not result["status"]:
        info_text = soup.get_text("\n", strip=True)[:3000]
        m = _STATUS_LABEL_RE.search(info_text)
        if m:
            result["status"] = m.group(1).strip()

    return result


_HYDRATION_PROSE_KEYS = (
    "chaptercontent", "novelcontent", "episodecontent", "content", "body",
    "text", "html", "paragraphs", "blocks", "matter", "rawcontent",
)
_HYDRATION_TITLE_KEYS = (
    "chaptertitle", "episodetitle", "subtitle", "title", "chaptername", "name",
)


def extract_hydration_prose(html: str) -> Optional[tuple[str, str]]:
    """
    Fallback extractor for Next.js (__NEXT_DATA__), Nuxt (__NUXT_DATA__), or custom SPA JSON
    state embedded in <script> tags when static HTML body contains an unhydrated shell.
    Returns (title, markdown) if chapter prose (>= 80 chars) is found, else None.
    """
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")

    json_blobs: List[Any] = []
    for script in soup.find_all("script"):
        sid = (script.get("id") or "").strip()
        stype = (script.get("type") or "").strip().lower()
        raw = (script.string or script.get_text() or "").strip()
        if not raw or len(raw) < 80:
            continue
        if sid in ("__NEXT_DATA__", "__NUXT_DATA__") or stype == "application/json":
            try:
                json_blobs.append(json.loads(raw))
                continue
            except Exception:
                pass
        # Check window.__INITIAL_STATE__ = {...}; or window.__NEXT_DATA__ = {...};
        m = re.search(
            r"window\.(?:__INITIAL_STATE__|__NEXT_DATA__|__PRELOADED_STATE__)\s*=\s*(\{.*\})\s*;?\s*$",
            raw,
            re.DOTALL,
        )
        if m:
            try:
                json_blobs.append(json.loads(m.group(1)))
            except Exception:
                pass

    if not json_blobs:
        return None

    best_prose = ""
    best_title = ""

    def _clean_prose_Candidate(val: str) -> str:
        s = val.strip()
        if "<p" in s.lower() or "<br" in s.lower() or "<div" in s.lower():
            frag = BeautifulSoup(s, "html.parser")
            for br in frag.find_all("br"):
                br.replace_with("\n\n")
            for p in frag.find_all(["p", "div"]):
                p.insert_before("\n\n")
                p.insert_after("\n\n")
            s = frag.get_text()
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"\n{3,}", "\n\n", s).strip()
        return s

    def _walk(node: Any, current_title: str = "") -> None:
        nonlocal best_prose, best_title
        if isinstance(node, dict):
            local_title = current_title
            for k, v in node.items():
                kl = str(k).lower().replace("_", "").replace("-", "")
                if kl in _HYDRATION_TITLE_KEYS and isinstance(v, str) and 1 <= len(v.strip()) <= 180:
                    local_title = v.strip()
                    break

            for k, v in node.items():
                kl = str(k).lower().replace("_", "").replace("-", "")
                if kl in _HYDRATION_PROSE_KEYS:
                    candidate = ""
                    if isinstance(v, str) and len(v.strip()) >= 80:
                        candidate = _clean_prose_Candidate(v)
                    elif isinstance(v, list) and v:
                        parts = []
                        for item in v:
                            if isinstance(item, str) and item.strip():
                                parts.append(item.strip())
                            elif isinstance(item, dict):
                                txt = item.get("text") or item.get("content") or item.get("paragraph")
                                if isinstance(txt, str) and txt.strip():
                                    parts.append(txt.strip())
                        if parts:
                            candidate = "\n\n".join(parts)
                    if len(candidate) >= 80 and len(candidate) > len(best_prose):
                        # Guard against minified code/URLs masquerading as prose
                        if not candidate.startswith(("http://", "https://", "function(", "{")):
                            best_prose = candidate
                            if local_title:
                                best_title = local_title
                _walk(v, local_title)
        elif isinstance(node, list):
            for item in node:
                _walk(item, current_title)

    for blob in json_blobs:
        _walk(blob)

    if len(best_prose) >= 80:
        return (best_title or "Untitled", best_prose)
    return None
