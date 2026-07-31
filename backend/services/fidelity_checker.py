"""
Post-Translation Fidelity Verification (ADR-072).

Checks that AI translation output is faithful to the input in terms of completeness.
This is a NON-BLOCKING check — it warns but doesn't reject the translation.
Designed for premium Chinese web novel translation standards where every paragraph must be present.
"""

import re
import logging

logger = logging.getLogger(__name__)


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
PROPER_ENDING_CHARS = '.!?\u2026"\u201d\u300d\u300f~*-)\u3002\uff01\uff1f'


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


def is_truncated_mid_sentence(text: str) -> bool:
    """
    Check if a translation was cut off mid-sentence.
    Returns True if the last character is NOT a proper sentence-ending character.
    This replaces the old inline logic in threads.py fix-truncated endpoint.
    """
    if not text or not text.strip():
        return True  # Empty text is considered truncated
    last_char = text.rstrip()[-1:]
    return last_char not in PROPER_ENDING_CHARS


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
            "is_suspicious": bool(original_text and not translated_text),
            "warnings": ["Empty translation output"] if (original_text and not translated_text) else [],
        }

    orig_paras = _count_meaningful_paragraphs(original_text)
    trans_paras = _count_meaningful_paragraphs(translated_text)

    orig_chars = len(original_text.strip())
    trans_chars = len(translated_text.strip())

    para_ratio = trans_paras / max(orig_paras, 1)
    char_ratio = trans_chars / max(orig_chars, 1)

    is_suspicious = False

    # Check paragraph ratio
    if para_ratio < MIN_PARAGRAPH_RATIO:
        is_suspicious = True
        warnings.append(
            f"Paragraph count dropped significantly: {orig_paras} original → {trans_paras} translated "
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

    # Quaternary check: mid-sentence truncation (merged from fix-truncated endpoint)
    truncated = is_truncated_mid_sentence(translated_text)
    if truncated:
        is_suspicious = True
        warnings.append(
            "Translation appears to be cut off mid-sentence. "
            "The last character is not a proper sentence-ending punctuation."
        )

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
        "is_truncated": truncated,
        "is_suspicious": is_suspicious,
        "warnings": warnings,
    }

