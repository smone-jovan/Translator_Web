"""
Post-Translation Fidelity Verification (ADR-072).

Checks that AI translation output is faithful to the input in terms of completeness.
This is a NON-BLOCKING check — it warns but doesn't reject the translation.
Designed for premium Chinese web novel translation standards where every paragraph must be present.
"""

import re
import logging
from services.hallucination_detector import HallucinationDetector

logger = logging.getLogger(__name__)

ALLOWED_KAOMOJI_CHARS = set("囧凸ㅠㅠㅋㅋㅎㅎㅜㅜ눈ωД")
SOURCE_SCRIPT_RE = re.compile(
    r"[一-鿿㐀-䶿豈-﫿가-힣぀-ゟ゠-ヿ]"
)
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
META_LEAKAGE_RE = re.compile(
    r"(\[\[TRUNCATED\]\]|\[\[PROHIBITED\]\]|"
    r"^(?:here\s+is\s+the\s+(?:indonesian|english)?\s*translation|berikut\s+adalah\s+terjemahan|"
    r"as\s+an\s+ai\s+language\s+model|i\s+cannot\s+fulfill\s+this\s+request|sebagai\s+model\s+bahasa\s+ai)\b)",
    re.IGNORECASE | re.MULTILINE,
)


def count_untranslated_script_chars(text: str) -> int:
    """Count raw East Asian characters (Hanzi, Hangul, Kana) excluding markdown image alt-text and kaomoji."""
    if not text:
        return 0
    without_imgs = MD_IMAGE_RE.sub("", text)
    chars = SOURCE_SCRIPT_RE.findall(without_imgs)
    return sum(1 for ch in chars if ch not in ALLOWED_KAOMOJI_CHARS)


# Fidelity ratio thresholds
# If translated paragraphs are less than 30% or more than 250% of original
MIN_PARAGRAPH_RATIO = 0.3
MAX_PARAGRAPH_RATIO = 2.5

# Character-count based heuristic
# Chinese → English typically expands 1.5x-3x in character count
# Chinese → Indonesian typically expands 1.5x-2.5x
MIN_CHAR_RATIO = 0.3   # very generous lower bound
MAX_CHAR_RATIO = 5.0   # very generous upper bound

# Dialogue line ratio threshold
# If translated dialogue lines are less than 20% of original, something is wrong
MIN_DIALOGUE_RATIO = 0.2

# Characters that indicate a properly-ended sentence (used for truncation detection)
PROPER_ENDING_CHARS = (
    '.!?…~*-—:;'
    '"\'"”’‘'
    ')]}》〉】〕］）｝>」』'
    '。！？；…～'
    '♥♡★☆♪♫'
)


def _count_meaningful_paragraphs(text: str) -> int:
    """Count paragraphs with actual content (not empty lines or whitespace-only)."""
    if not text:
        return 0
    # Gunakan regex untuk memisahkan berdasarkan satu atau lebih baris baru (\n)
    # Ini memperbaiki masalah EPUB yang hanya menggunakan single \n untuk paragraf
    paragraphs = re.split(r'\n+', text)
    return sum(1 for p in paragraphs if p.strip() and len(p.strip()) > 5)


def _count_meaningful_lines(text: str) -> int:
    """Count non-empty lines as a secondary metric."""
    if not text:
        return 0
    return sum(1 for line in text.splitlines() if line.strip())


def _count_dialogue_lines(text: str) -> int:
    """
    Count lines that start with dialogue markers.
    Chinese novels use various quote styles for dialogue.
    """
    if not text:
        return 0
    dialogue_markers = ('"', '\u201c', '\u300c', '\u300e', '\u2018', "'", '\u2014', '\u2014\u2014')
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and any(stripped.startswith(m) for m in dialogue_markers):
            count += 1
    return count


CHAPTER_END_PATTERN = re.compile(
    r"(?:[-—~*#_\s]*\b(?:the\s+end|to\s+be\s+continued|fin|end|tamat|selesai|bersambung)\b[-—~*#_\s]*|[(\[{<]?(?:完|全剧终|未完待续|全書完|全书完|本章完)[)\]}>]?\s*)$",
    re.IGNORECASE
)


# Author footers appended after the story body: date stamps (2025/04/18/21/29) and source URLs.
_FOOTER_WRAP = r"[\s *_`~]*"
FOOTER_LINE_RE = re.compile(
    rf"^{_FOOTER_WRAP}(?:\d{{4}}[/.\-]\d{{1,2}}[/.\-]\d{{1,2}}(?:[/.\-:\s]+\d{{1,2}})*(?:[\s ]*[x×]\d+)?|https?://\S+){_FOOTER_WRAP}$"
)


def _strip_trailing_footer(text: str) -> str:
    """Drop trailing date-stamp / URL lines so they are not mistaken for the end of the prose."""
    lines = text.rstrip().splitlines()
    while lines and (not lines[-1].strip() or FOOTER_LINE_RE.match(lines[-1])):
        lines.pop()
    return "\n".join(lines).rstrip()


def is_truncated_mid_sentence(text: str, original_text: str | None = None) -> bool:
    """
    Check if a translation was cut off mid-sentence.
    Returns True if the last character is NOT a proper sentence-ending character.
    Gracefully handles chapter-ending markers (e.g., "- The End") and cliffhanger endings
    that mirror the original source text (e.g., trailing em-dash or names).
    """
    if not text or not text.strip():
        return True  # Empty text is considered truncated
    
    cleaned = _strip_trailing_footer(text)
    if not cleaned:
        return True  # Footer-only text has no prose ending
    if CHAPTER_END_PATTERN.search(cleaned):
        return False

    # Trim markdown emphasis wrappers (like * or _ or ` or \) from the tail; '~' is a valid ending
    trimmed = cleaned.rstrip('*_`\\ \t\r\n')
    if not trimmed:
        trimmed = cleaned
        
    last_char = trimmed[-1:]
    if last_char in PROPER_ENDING_CHARS:
        return False
        
    # If original text is provided, check if the original also ended without sentence-ending punctuation or with an em-dash
    if original_text and original_text.strip():
        orig_cleaned = _strip_trailing_footer(original_text).rstrip('*_`~\\ \t\r\n')
        orig_last = orig_cleaned[-1:] if orig_cleaned else ""
        if orig_last in '—-—―~～' or orig_cleaned.endswith(('——', '...')):
            return False
        # Authors end notes with digit emoticons ("0.0"); a translation mirroring that is complete.
        if orig_last.isdigit() and last_char.isdigit():
            return False
            
    return True


def verify_translation_fidelity(
    original_text: str,
    translated_text: str,
    chapter_id: int | None = None
) -> dict:
    """
    Compare original and translated text for fidelity.

    Returns a dict with:
    - original_paragraphs: int
    - translated_paragraphs: int
    - paragraph_ratio: float
    - original_chars: int
    - translated_chars: int
    - char_ratio: float
    - is_suspicious: bool
    - warnings: list[str]
    """
    warnings = []

    if not original_text or not translated_text:
        return {
            "original_paragraphs": 0,
            "translated_paragraphs": 0,
            "paragraph_ratio": 0.0,
            "original_chars": 0,
            "translated_chars": 0,
            "char_ratio": 0.0,
            "original_dialogue_lines": 0,
            "translated_dialogue_lines": 0,
            "dialogue_ratio": 0.0,
            "untranslated_script_chars": 0,
            "has_hallucination_loop": False,
            "is_truncated": False,
            "is_suspicious": bool(original_text and not translated_text),
            "warnings": ["Empty translation output"] if (original_text and not translated_text) else [],
        }

    orig_cjk_chars = count_untranslated_script_chars(original_text)
    is_cjk_source = orig_cjk_chars > (len(original_text.strip()) * 0.30)

    orig_paras = _count_meaningful_paragraphs(original_text)
    trans_paras = _count_meaningful_paragraphs(translated_text)

    orig_chars = len(original_text.strip())
    trans_chars = len(translated_text.strip())

    para_ratio = trans_paras / max(orig_paras, 1)
    char_ratio = trans_chars / max(orig_chars, 1)

    is_suspicious = False

    # Mid-sentence truncation check
    truncated = is_truncated_mid_sentence(translated_text, original_text=original_text)
    if truncated:
        is_suspicious = True
        warnings.append(
            "Translation appears to be cut off mid-sentence. "
            "The last character is not a proper sentence-ending punctuation."
        )

    # Check paragraph ratio
    if para_ratio < MIN_PARAGRAPH_RATIO:
        avg_orig_len = orig_chars / max(orig_paras, 1)
        # Web novels frequently format 1 sentence per line (avg_orig_len < 60 chars).
        # If character expansion is healthy (char_ratio >= 1.0) and text is not truncated,
        # this is normal paragraph consolidation into prose, NOT content truncation.
        if avg_orig_len < 60 and char_ratio >= 1.0 and not truncated:
            warnings.append(
                f"Paragraph count consolidated: {orig_paras} original -> {trans_paras} translated "
                f"(ratio: {para_ratio:.2f}). Character length is healthy ({char_ratio:.2f}x); normal paragraph consolidation."
            )
        else:
            is_suspicious = True
            warnings.append(
                f"Paragraph count dropped significantly: {orig_paras} original -> {trans_paras} translated "
                f"(ratio: {para_ratio:.2f}). Possible content truncation or summarization."
            )

    if para_ratio > MAX_PARAGRAPH_RATIO:
        is_suspicious = True
        warnings.append(
            f"Paragraph count inflated: {orig_paras} original → {trans_paras} translated "
            f"(ratio: {para_ratio:.2f}). Possible hallucination or excessive splitting."
        )

    # Check character ratio
    if char_ratio < MIN_CHAR_RATIO:
        is_suspicious = True
        warnings.append(
            f"Translation is suspiciously short: {orig_chars} original chars → {trans_chars} translated chars "
            f"(ratio: {char_ratio:.2f}). Possible severe truncation."
        )
    elif is_cjk_source and orig_chars >= 600 and char_ratio < 0.70 and para_ratio < 0.65:
        is_suspicious = True
        warnings.append(
            f"Paragraph count dropped: {orig_paras} original -> {trans_paras} translated "
            f"(ratio: {para_ratio:.2f}, char ratio: {char_ratio:.2f}x). Possible AI summarization or skipped paragraphs."
        )

    if char_ratio > MAX_CHAR_RATIO:
        is_suspicious = True
        warnings.append(
            f"Translation is suspiciously long: {orig_chars} original chars → {trans_chars} translated chars "
            f"(ratio: {char_ratio:.2f}). Possible hallucination or excessive repetition."
        )

    # Secondary check: if original has significant content (>500 chars) but translation is tiny (<100 chars)
    if orig_chars > 500 and trans_chars < 100:
        is_suspicious = True
        warnings.append(
            f"Critical: Original has {orig_chars} chars but translation is only {trans_chars} chars. "
            "Translation appears to be nearly empty."
        )

    # Tertiary check: dialogue line preservation
    # If original has significant dialogue (>5 lines), check that translation preserves them
    orig_dialogue = _count_dialogue_lines(original_text)
    trans_dialogue = _count_dialogue_lines(translated_text)
    dialogue_ratio = trans_dialogue / max(orig_dialogue, 1) if orig_dialogue >= 5 else 1.0

    if orig_dialogue >= 5 and dialogue_ratio < MIN_DIALOGUE_RATIO:
        is_suspicious = True
        warnings.append(
            f"Dialogue lines dropped severely: {orig_dialogue} original -> {trans_dialogue} translated "
            f"(ratio: {dialogue_ratio:.2f}). Possible dialogue omission or reformatting issue."
        )

    # Untranslated East Asian script leakage check
    leaked_script_chars = count_untranslated_script_chars(translated_text)
    leaked_ratio = leaked_script_chars / max(trans_chars, 1)
    if is_cjk_source and (leaked_script_chars >= 15 or (leaked_script_chars >= 6 and leaked_ratio >= 0.02)):
        is_suspicious = True
        warnings.append(
            f"Untranslated source script detected: {leaked_script_chars} raw CJK/Hangul/Kana characters leaked into translation."
        )

    # Hallucination / Repetition Loop check
    word_loops = HallucinationDetector.detect_repeated_words(translated_text, threshold=8)
    phrase_loops = HallucinationDetector.detect_repeated_phrases(translated_text, threshold=4)
    has_hallucination_loop = bool(word_loops or phrase_loops)
    if has_hallucination_loop:
        is_suspicious = True
        sample_tok = word_loops[0].token if word_loops else phrase_loops[0].token
        warnings.append(f"Hallucination repetition loop detected: '{sample_tok}' repeated excessively.")

    # AI Meta-Commentary / Sentinel Leakage check
    if META_LEAKAGE_RE.search(translated_text):
        is_suspicious = True
        warnings.append("AI meta-commentary or truncation sentinel leaked into translated text.")

    # Log warnings
    ch_label = f"Chapter {chapter_id}" if chapter_id else "Unknown chapter"
    if warnings:
        for w in warnings:
            logger.warning(f"[FIDELITY] {ch_label}: {w}")
            print(f"[FIDELITY WARNING] {ch_label}: {w}")

    return {
        "original_paragraphs": orig_paras,
        "translated_paragraphs": trans_paras,
        "paragraph_ratio": round(para_ratio, 2),
        "original_chars": orig_chars,
        "translated_chars": trans_chars,
        "char_ratio": round(char_ratio, 2),
        "original_dialogue_lines": orig_dialogue,
        "translated_dialogue_lines": trans_dialogue,
        "dialogue_ratio": round(dialogue_ratio, 2),
        "untranslated_script_chars": leaked_script_chars,
        "has_hallucination_loop": has_hallucination_loop,
        "is_truncated": truncated,
        "is_suspicious": is_suspicious,
        "warnings": warnings,
    }

