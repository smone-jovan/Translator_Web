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
            return host.lstrip("www.") or "default"
        except Exception:
            return raw
    return raw.lstrip("www.") or "default"


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
        for el in soup.find_all(["article", "main", "section", "div"]):
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
