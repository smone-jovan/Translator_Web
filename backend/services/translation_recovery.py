"""
Self-healing for chapter translations before they are saved.

Some providers (notably Gemini) stop early with a normal finish_reason, so the
length-based auto-continue never fires. These helpers verify the finished
translation and repair it: continue a translation cut off mid-sentence, and
re-translate one that was summarized. Both are best-effort and never raise.
"""

import logging
import re
from typing import Awaitable, Callable

from services.fidelity_checker import (
    _count_meaningful_paragraphs,
    is_truncated_mid_sentence,
    verify_translation_fidelity,
)

logger = logging.getLogger(__name__)

MAX_COMPLETION_ROUNDS = 2
SUMMARIZED_WARNING_PREFIX = "Paragraph count dropped"


def _identity(text: str) -> str:
    return text


MIN_OVERLAP_CHARS = 20
RESTART_PROBE_CHARS = 40
NEAR_END_RATIO = 0.9
END_SLACK_PARAGRAPHS = 2


def continuation_paragraph_budget(original: str, partial: str) -> int | None:
    """Max new paragraphs a continuation may add; None while far from the end of the source.

    Once the translation already holds nearly as many paragraphs as the source, little
    or nothing is left to translate, so anything beyond the budget is invented.
    """
    source_paragraphs = _count_meaningful_paragraphs(original)
    done_paragraphs = _count_meaningful_paragraphs(partial)
    if source_paragraphs == 0 or done_paragraphs < NEAR_END_RATIO * source_paragraphs:
        return None
    return max(source_paragraphs - done_paragraphs, 0) + END_SLACK_PARAGRAPHS


def limit_new_paragraphs(original: str, partial: str, continuation: str) -> str:
    """Cut a continuation to the paragraph budget so the model cannot write past the source."""
    budget = continuation_paragraph_budget(original, partial)
    if budget is None:
        return continuation
    kept = 0
    for line in re.finditer(r"[^\n]+", continuation):
        if len(line.group().strip()) > 5:
            kept += 1
            if kept == budget:
                return continuation[: line.end()]
    return continuation


def trim_runaway_round(
    original: str,
    before: str,
    after: str,
    clean_fn: Callable[[str], str] = _identity,
) -> str:
    """Cap the text one continuation round appended to `before` (resulting in `after`)."""
    if not after.startswith(before):
        return after
    added = after[len(before):]
    return before + limit_new_paragraphs(original, clean_fn(before), added)


def _merge_continuation(partial: str, continuation: str) -> str | None:
    """Append a continuation without duplicating text; None when it adds nothing new.

    Models often restart the truncated paragraph or repeat its tail instead of
    continuing from the last character, so both cases are folded into the partial.
    """
    base = partial.rstrip()
    cont = continuation.strip()
    if not cont or cont in base:
        return None

    head, _, last_line = base.rpartition("\n")
    last_line = last_line.strip()
    probe = last_line[:RESTART_PROBE_CHARS]
    if len(probe) >= MIN_OVERLAP_CHARS and cont.startswith(probe):
        if len(cont) <= len(last_line):
            return None
        return (head + "\n" if head else "") + cont

    for size in range(min(len(base), len(cont)), MIN_OVERLAP_CHARS - 1, -1):
        if base.endswith(cont[:size]):
            remainder = cont[size:]
            if not remainder.strip():
                return None
            separator = "" if remainder[:1].isspace() else " "
            return base + separator + remainder

    separator = "" if continuation[:1].isspace() else " "
    return base + separator + continuation.lstrip(" ")


async def complete_truncated_translation(
    original: str,
    raw_translation: str,
    continue_fn: Callable[[str], Awaitable[str]],
    clean_fn: Callable[[str], str] = _identity,
    max_rounds: int = MAX_COMPLETION_ROUNDS,
) -> tuple[str, int]:
    """Continue a translation that ends mid-sentence. Returns (text, successful_rounds)."""
    text = raw_translation
    rounds = 0
    while rounds < max_rounds and is_truncated_mid_sentence(clean_fn(text), original_text=original):
        try:
            continuation = await continue_fn(text)
        except Exception as exc:
            logger.warning("[RECOVERY] continuation failed, keeping partial translation: %s", exc)
            break
        continuation = limit_new_paragraphs(original, clean_fn(text), continuation or "")
        merged = _merge_continuation(text, continuation)
        if merged is None:
            break
        text = merged
        rounds += 1
    return text, rounds


def _is_summarized(original: str, translated: str) -> tuple[bool, float]:
    fidelity = verify_translation_fidelity(original, translated)
    summarized = any(w.startswith(SUMMARIZED_WARNING_PREFIX) for w in fidelity["warnings"])
    return summarized, fidelity["paragraph_ratio"]


async def retry_if_summarized(
    original: str,
    raw_translation: str,
    retry_fn: Callable[[], Awaitable[str]],
    clean_fn: Callable[[str], str] = _identity,
) -> tuple[str, bool]:
    """Re-translate once when paragraphs were dropped. Returns (text, retry_was_used)."""
    summarized, old_ratio = _is_summarized(original, clean_fn(raw_translation))
    if not summarized:
        return raw_translation, False
    try:
        retried = await retry_fn()
    except Exception as exc:
        logger.warning("[RECOVERY] anti-summary retry failed, keeping original translation: %s", exc)
        return raw_translation, False
    if not retried or not retried.strip():
        return raw_translation, False
    _, new_ratio = _is_summarized(original, clean_fn(retried))
    if new_ratio <= old_ratio:
        return raw_translation, False
    return retried, True
