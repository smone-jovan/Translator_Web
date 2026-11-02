"""
Deterministic TXT Import Service (ADR-139).

Parses plain text files into reviewable, non-persistent draft chapters.
Independent of FastAPI, SQLAlchemy, and filesystem writes.
"""

from dataclasses import dataclass
import re
from typing import List, Optional

MAX_WORDS_PER_CHAPTER = 6000

# Supported encodings in strict priority order (ADR-139)
SUPPORTED_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "big5", "shift_jis")

# Conservative line-boundary heading patterns
HEADING_PATTERNS = [
    re.compile(r"^\s*(?i:Chapter|Ch\.?)\s+(?:\d+|[IVXLCDM]+)\b.*$"),
    re.compile(r"^\s*(?i:Volume|Vol\.?|Book|Buku|Part|Bagian|Jilid)\s+(?:\d+|[IVXLCDM]+)\b.*$"),
    re.compile(r"^\s*(?i:Bab\.?)\s+(?:\d+|[IVXLCDM]+)\b.*$"),
    re.compile(r"^\s*第\s*[0-9０-９一二三四五六七八九十百千万萬零〇两兩\d]+\s*[章节回卷巻话話部].*$"),
]

# Patterns representing volume or part-level headings that can merge into subsequent chapter drafts
VOLUME_HEADING_PATTERN = re.compile(
    r"^\s*(?:(?i:Volume|Vol\.?|Book|Buku|Part|Bagian|Jilid)\s+(?:\d+|[IVXLCDM]+)\b|第\s*[0-9０-９一二三四五六七八九十百千万萬零〇两兩\d]+\s*[卷巻部])"
)


def _get_volume_heading_level(title: str) -> int:
    """
    Returns hierarchical level for volume-like headings:
    1: Book / Buku / 第...部
    2: Volume / Vol / Jilid / 第...[卷巻]
    3: Part / Bagian
    0: Not a volume heading (e.g. Chapter / Bab / 第...[节回话])
    """
    cleaned = title.strip()
    if re.search(r"^\s*(?:(?i:Book|Buku)\s+(?:\d+|[IVXLCDM]+)\b|第\s*[0-9０-９一二三四五六七八九十百千万萬零〇两兩\d]+\s*部)", cleaned):
        return 1
    if re.search(r"^\s*(?:(?i:Volume|Vol\.?|Jilid)\s+(?:\d+|[IVXLCDM]+)\b|第\s*[0-9０-９一二三四五六七八九十百千万萬零〇两兩\d]+\s*[卷巻])", cleaned):
        return 2
    if re.search(r"^\s*(?i:Part|Bagian)\s+(?:\d+|[IVXLCDM]+)\b", cleaned):
        return 3
    return 0


class TxtImporterError(Exception):
    """Base exception for TXT importer service."""


class TxtDecodeError(TxtImporterError):
    """Raised when uploaded bytes cannot be strictly decoded with supported encodings."""


class TxtInvalidContentError(TxtImporterError):
    """Raised when content is empty, whitespace-only, or contains NUL bytes."""


@dataclass
class ParsedDraft:
    title: str
    body: str
    source_chapter_ordinal: int
    split_ordinal: int
    split_total: int
    word_count: int
    is_oversized: bool = False


def count_words(text: str) -> int:
    """
    Counts words accurately for mixed Latin and CJK texts.
    CJK characters are counted individually; non-CJK tokens containing alphanumeric
    characters are counted as whitespace-separated words.
    """
    if not text:
        return 0
    cjk_count = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))
    non_cjk_text = re.sub(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", " ", text)
    words_count = len([w for w in non_cjk_text.split() if any(c.isalnum() for c in w)])
    return cjk_count + words_count


def decode_txt_bytes(raw_bytes: bytes) -> str:
    """
    Strictly decodes raw bytes into unicode text.
    Rejects NUL bytes, empty or whitespace-only content.
    Tries encodings in priority order: utf-8-sig, utf-8, gb18030, big5, shift_jis.
    Never falls back to permissive latin-1 or errors='ignore'.
    """
    if b"\x00" in raw_bytes:
        raise TxtInvalidContentError("Source file contains invalid NUL bytes")

    # 1. Try UTF-8 variants first
    for enc in ("utf-8-sig", "utf-8"):
        try:
            decoded = raw_bytes.decode(enc)
            if "\x00" in decoded:
                raise TxtInvalidContentError("Source file contains invalid NUL bytes")
            if not decoded.strip():
                raise TxtInvalidContentError("Source file is empty or contains only whitespace")
            return decoded
        except (UnicodeDecodeError, LookupError):
            continue

    # 2. For legacy CJK encodings (gb18030, big5, shift_jis), determine priority order
    legacy_order = ["gb18030", "big5", "shift_jis"]
    try:
        import charset_normalizer
        match = charset_normalizer.from_bytes(raw_bytes).best()
        if match and match.encoding:
            m_enc = match.encoding.lower()
            if "big5" in m_enc:
                legacy_order = ["big5", "gb18030", "shift_jis"]
            elif any(k in m_enc for k in ("sjis", "shift_jis", "cp932", "euc_jp")):
                legacy_order = ["shift_jis", "gb18030", "big5"]
            elif any(k in m_enc for k in ("gb", "cp936", "cp949", "hz")):
                legacy_order = ["gb18030", "big5", "shift_jis"]
    except Exception:
        pass

    decoded_text: Optional[str] = None
    for enc in legacy_order:
        try:
            res = raw_bytes.decode(enc)
            # gb18030 maps arbitrary bytes into Private Use Area (0xE000-0xF8FF); reject false positives
            if enc == "gb18030" and any(0xE000 <= ord(c) <= 0xF8FF for c in res):
                continue
            decoded_text = res
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if decoded_text is None:
        raise TxtDecodeError(
            "Failed to decode text file. Supported encodings: UTF-8, GB18030, Big5, Shift-JIS."
        )

    if "\x00" in decoded_text:
        raise TxtInvalidContentError("Source file contains invalid NUL bytes")

    if not decoded_text.strip():
        raise TxtInvalidContentError("Source file is empty or contains only whitespace")

    return decoded_text


def _is_heading_line(line: str) -> bool:
    cleaned = line.strip()
    if not cleaned or len(cleaned) > 200:
        return False
    return any(p.match(line) for p in HEADING_PATTERNS)


def parse_txt_to_drafts(text: str) -> List[ParsedDraft]:
    """
    Deterministically parses decoded text into ordered ParsedDraft objects.
    - Normalizes CRLF -> LF
    - Identifies headings at line boundaries
    - Non-empty text before first heading becomes 'Prologue'
    - Entire file without headings becomes 'Chapter 1'
    - Chapters over MAX_WORDS_PER_CHAPTER are safely split at paragraph boundaries
    - Heading text becomes the title and is never duplicated in the body
    - Reconstructing split bodies preserves original content without loss or duplication
    """
    if "\x00" in text:
        raise TxtInvalidContentError("Source file contains invalid NUL bytes")

    if not text.strip():
        raise TxtInvalidContentError("Source file is empty or contains only whitespace")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")

    # Find heading line indices
    heading_indices: List[int] = []
    for idx, line in enumerate(lines):
        if _is_heading_line(line):
            heading_indices.append(idx)

    raw_chapters: List[tuple[str, str]] = []

    if not heading_indices:
        # Fallback: entire file becomes a single editable "Chapter 1"
        raw_chapters.append(("Chapter 1", normalized.strip()))
    else:
        # Check for preface text before the first heading
        first_heading = heading_indices[0]
        if first_heading > 0:
            preface_lines = lines[:first_heading]
            preface_text = "\n".join(preface_lines).strip()
            if preface_text:
                raw_chapters.append(("Prologue", preface_text))

        # Extract chapters defined by headings with volume merge and empty filter
        pending_volume_entries: List[tuple[int, str]] = []
        for i, h_idx in enumerate(heading_indices):
            title = lines[h_idx].strip()
            next_idx = heading_indices[i + 1] if i + 1 < len(heading_indices) else len(lines)
            body_lines = lines[h_idx + 1:next_idx]
            body_text = "\n".join(body_lines).strip()

            if not body_text:
                lvl = _get_volume_heading_level(title)
                if lvl > 0:
                    # Remove any pending sibling or child headings at or deeper than current level
                    # (prevents sibling volumes in TOC from accumulating, while preserving Book -> Volume -> Part hierarchy)
                    pending_volume_entries = [
                        (p_lvl, p_title)
                        for (p_lvl, p_title) in pending_volume_entries
                        if p_lvl < lvl
                    ]
                    pending_volume_entries.append((lvl, title))
                else:
                    pending_volume_entries.clear()
                continue

            if pending_volume_entries:
                merged_title = " — ".join([t for _, t in pending_volume_entries] + [title])
                if len(merged_title) > 500:
                    merged_title = merged_title[:497] + "..."
                pending_volume_entries.clear()
            else:
                merged_title = title

            raw_chapters.append((merged_title, body_text))

    if not raw_chapters:
        raise TxtInvalidContentError("Source file contains no readable chapter content")

    # Split long chapters if word count exceeds MAX_WORDS_PER_CHAPTER
    drafts: List[ParsedDraft] = []
    for source_ord, (title, body) in enumerate(raw_chapters, start=1):
        total_words = count_words(body)
        if total_words <= MAX_WORDS_PER_CHAPTER:
            drafts.append(
                ParsedDraft(
                    title=title,
                    body=body,
                    source_chapter_ordinal=source_ord,
                    split_ordinal=1,
                    split_total=1,
                    word_count=total_words,
                    is_oversized=False,
                )
            )
            continue

        # Split at paragraph boundaries (\n\n)
        paragraphs = re.split(r"\n{2,}", body)
        chunks: List[List[str]] = []
        current_chunk: List[str] = []
        current_words = 0

        for p in paragraphs:
            p_words = count_words(p)
            if current_words + p_words > MAX_WORDS_PER_CHAPTER:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = [p]
                    current_words = p_words
                else:
                    # Single paragraph alone exceeds threshold: keep intact (Rule 7)
                    chunks.append([p])
                    current_chunk = []
                    current_words = 0
            else:
                current_chunk.append(p)
                current_words += p_words

        if current_chunk:
            chunks.append(current_chunk)

        split_total = len(chunks)
        for split_ord, chunk_paras in enumerate(chunks, start=1):
            chunk_body = "\n\n".join(chunk_paras)
            chunk_words = count_words(chunk_body)
            is_oversized = chunk_words > MAX_WORDS_PER_CHAPTER

            if split_total > 1:
                part_title = f"{title} — Part {split_ord}/{split_total}"
            else:
                part_title = title

            drafts.append(
                ParsedDraft(
                    title=part_title,
                    body=chunk_body,
                    source_chapter_ordinal=source_ord,
                    split_ordinal=split_ord,
                    split_total=split_total,
                    word_count=chunk_words,
                    is_oversized=is_oversized,
                )
            )

    return drafts
