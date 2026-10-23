import pytest

from services.translation_recovery import (
    MAX_COMPLETION_ROUNDS,
    complete_truncated_translation,
    retry_if_summarized,
)


def _paragraphs(count: int, template: str) -> str:
    return "\n\n".join(template.format(i=i) for i in range(count))


ORIGINAL = _paragraphs(93, "Original paragraph number {i} with enough text.")
SUMMARIZED = _paragraphs(26, "Short summary {i}.")
FULL = _paragraphs(93, "Terjemahan paragraf nomor {i} dengan teks yang cukup.")


@pytest.mark.asyncio
async def test_complete_translation_does_not_call_continuation():
    calls = []

    async def continue_fn(partial: str) -> str:
        calls.append(partial)
        return "unused"

    text, rounds = await complete_truncated_translation(
        "Original sentence.", "The translation is complete.", continue_fn
    )

    assert text == "The translation is complete."
    assert rounds == 0
    assert calls == []


@pytest.mark.asyncio
async def test_truncated_translation_is_continued_until_sentence_ends():
    seen = []

    async def continue_fn(partial: str) -> str:
        seen.append(partial)
        return "and stopped after dozens of meters."

    text, rounds = await complete_truncated_translation(
        "原文。", "The fanatic flew backward,", continue_fn
    )

    assert seen == ["The fanatic flew backward,"]
    assert text == "The fanatic flew backward, and stopped after dozens of meters."
    assert rounds == 1


@pytest.mark.asyncio
async def test_continuation_keeps_paragraph_break_from_model():
    async def continue_fn(partial: str) -> str:
        return "\n\nNew paragraph ends here."

    text, _ = await complete_truncated_translation("原文。", "She walked on,", continue_fn)

    assert text == "She walked on,\n\nNew paragraph ends here."


@pytest.mark.asyncio
async def test_continuation_stops_after_max_rounds_when_still_truncated():
    calls = 0

    async def continue_fn(partial: str) -> str:
        nonlocal calls
        calls += 1
        return f"still going {calls},"

    _, rounds = await complete_truncated_translation("原文。", "It began,", continue_fn)

    assert calls == MAX_COMPLETION_ROUNDS
    assert rounds == MAX_COMPLETION_ROUNDS


@pytest.mark.asyncio
async def test_continuation_stops_when_model_returns_nothing():
    calls = 0

    async def continue_fn(partial: str) -> str:
        nonlocal calls
        calls += 1
        return "   "

    text, rounds = await complete_truncated_translation("原文。", "It began,", continue_fn)

    assert calls == 1
    assert rounds == 0
    assert text == "It began,"


@pytest.mark.asyncio
async def test_continuation_error_keeps_partial_translation():
    async def continue_fn(partial: str) -> str:
        raise RuntimeError("provider down")

    text, rounds = await complete_truncated_translation("原文。", "It began,", continue_fn)

    assert text == "It began,"
    assert rounds == 0


@pytest.mark.asyncio
async def test_truncation_check_uses_clean_function():
    async def continue_fn(partial: str) -> str:
        return "done."

    def clean_fn(raw: str) -> str:
        return raw.split("<notes>")[0]

    text, rounds = await complete_truncated_translation(
        "原文。", "Complete sentence.<notes>half-written", continue_fn, clean_fn=clean_fn
    )

    assert rounds == 0
    assert text == "Complete sentence.<notes>half-written"


@pytest.mark.asyncio
async def test_summarized_translation_is_retried_and_better_result_wins():
    calls = 0

    async def retry_fn() -> str:
        nonlocal calls
        calls += 1
        return FULL

    text, retried = await retry_if_summarized(ORIGINAL, SUMMARIZED, retry_fn)

    assert calls == 1
    assert retried is True
    assert text == FULL


@pytest.mark.asyncio
async def test_retry_result_that_is_not_better_is_discarded():
    async def retry_fn() -> str:
        return _paragraphs(10, "Even shorter {i}.")

    text, retried = await retry_if_summarized(ORIGINAL, SUMMARIZED, retry_fn)

    assert text == SUMMARIZED
    assert retried is False


@pytest.mark.asyncio
async def test_faithful_translation_is_not_retried():
    async def retry_fn() -> str:
        raise AssertionError("retry must not be called")

    text, retried = await retry_if_summarized(ORIGINAL, FULL, retry_fn)

    assert text == FULL
    assert retried is False


@pytest.mark.asyncio
async def test_retry_error_keeps_original_translation():
    async def retry_fn() -> str:
        raise RuntimeError("provider down")

    text, retried = await retry_if_summarized(ORIGINAL, SUMMARIZED, retry_fn)

    assert text == SUMMARIZED
    assert retried is False


@pytest.mark.asyncio
async def test_continuation_that_restarts_truncated_paragraph_replaces_it():
    partial = 'First paragraph.\n\n"Okay," Winnie said quietly. He felt like he had just received an important notificatio'

    async def continue_fn(text: str) -> str:
        return '"Okay," Winnie said quietly. He felt like he had just received an important notification about something big.'

    text, rounds = await complete_truncated_translation("原文。", partial, continue_fn)

    assert text == 'First paragraph.\n\n"Okay," Winnie said quietly. He felt like he had just received an important notification about something big.'
    assert text.count('"Okay,"') == 1
    assert rounds == 1


@pytest.mark.asyncio
async def test_continuation_overlapping_the_tail_is_trimmed():
    partial = "The fanatic flew backward, limbs braced against the ground,"

    async def continue_fn(text: str) -> str:
        return "limbs braced against the ground, and slid back dozens of meters."

    text, rounds = await complete_truncated_translation("原文。", partial, continue_fn)

    assert text == "The fanatic flew backward, limbs braced against the ground, and slid back dozens of meters."
    assert rounds == 1


@pytest.mark.asyncio
async def test_continuation_that_only_repeats_existing_text_makes_no_progress():
    partial = 'Intro.\n\n"Okay," Winnie said quietly after that brief explanation, and he felt like'
    calls = 0

    async def continue_fn(text: str) -> str:
        nonlocal calls
        calls += 1
        return '"Okay," Winnie said quietly after that brief explanation'

    text, rounds = await complete_truncated_translation("原文。", partial, continue_fn)

    assert calls == 1
    assert rounds == 0
    assert text == partial


# --- Continuation budget: never invent text past the end of the source -------------------

from services.translation_recovery import (  # noqa: E402
    continuation_paragraph_budget,
    limit_new_paragraphs,
    trim_runaway_round,
)

SRC = _paragraphs(20, "Original paragraph number {i} with enough text.")


def _translated(count: int) -> str:
    return _paragraphs(count, "Translated paragraph number {i} with enough text.")


def test_budget_is_unlimited_while_far_from_the_end():
    assert continuation_paragraph_budget(SRC, _translated(10)) is None


def test_budget_is_tiny_when_translation_already_covers_the_source():
    assert continuation_paragraph_budget(SRC, _translated(20)) == 2
    assert continuation_paragraph_budget(SRC, _translated(23)) == 2


def test_budget_allows_remaining_paragraphs_when_close_to_the_end():
    assert continuation_paragraph_budget(SRC, _translated(18)) == 4


def test_limit_new_paragraphs_cuts_runaway_continuation():
    runaway = _paragraphs(10, "Invented scene paragraph {i} that is not in the source.")

    limited = limit_new_paragraphs(SRC, _translated(20), runaway)

    assert limited.count("Invented scene paragraph") == 2
    assert "paragraph 0" in limited and "paragraph 1" in limited
    assert "paragraph 2 " not in limited


def test_limit_new_paragraphs_keeps_continuation_far_from_the_end():
    cont = _paragraphs(10, "Legit paragraph {i} continuing the translation.")

    assert limit_new_paragraphs(SRC, _translated(5), cont) == cont


@pytest.mark.asyncio
async def test_runaway_continuation_near_the_end_is_capped():
    partial = _translated(19) + "\n\nShe walked back to her room and then,"

    async def continue_fn(text: str) -> str:
        return "she slept.\n\n" + _paragraphs(12, "Invented epilogue paragraph {i} nobody wrote.") + "\n\n(To be continued...)"

    text, rounds = await complete_truncated_translation(SRC, partial, continue_fn)

    assert rounds == 1
    assert text.count("Invented epilogue") <= 1
    assert "(To be continued...)" not in text


def test_trim_runaway_round_caps_text_added_by_a_length_continuation():
    before = _translated(20) + "\n\nOn the way back to his dorm,"
    after = before + " he recalled the old plot.\n\n" + _paragraphs(8, "Invented paragraph {i} beyond the source.")

    trimmed = trim_runaway_round(SRC, before, after)

    assert trimmed.startswith(before + " he recalled the old plot.")
    assert trimmed.count("Invented paragraph") <= 1


def test_trim_runaway_round_leaves_normal_rounds_untouched():
    before = _translated(5) + "\n\nHe said that"
    after = before + " it was fine.\n\n" + _paragraphs(6, "Next paragraph {i} of the real translation.")

    assert trim_runaway_round(SRC, before, after) == after
