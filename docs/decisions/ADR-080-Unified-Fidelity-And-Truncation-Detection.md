# ADR-080: Unified Fidelity and Truncation Detection

## Status
Accepted

## Date
2026-06-14

## Context
The system had two separate, overlapping mechanisms for detecting translation quality problems:

1. **Fidelity Checker** (`fidelity_checker.py`) — runs automatically after each translation. Checks paragraph ratio, character ratio, and dialogue line ratio. Saves a `fidelity_warning` flag but does NOT reset the translation.

2. **Fix Truncated** (`threads.py` endpoint) — runs manually when user clicks a button. Checks if the last character of the translation is a proper sentence-ending punctuation. If not, it resets the chapter to `idle` (deletes the translation).

These two systems detected *related but different* problems using *completely separate code paths*:
- Fidelity caught: summarization, paragraph omission, content hallucination
- Fix-truncated caught: AI stopping mid-sentence (e.g., `finish_reason=length`)

The ending-character check was hardcoded inline in `threads.py` with a magic string `'.!??"」』~*-)\u2026'`, making it impossible to test independently or reuse in other contexts.

## Decision
Merge the truncation detection logic into `fidelity_checker.py` as the **single source of truth** for all translation quality checks:

1. Added `PROPER_ENDING_CHARS` constant to `fidelity_checker.py`
2. Created `is_truncated_mid_sentence(text)` function — a clean, testable, reusable utility
3. Integrated the truncation check as the 4th metric in `verify_translation_fidelity()` (returns `is_truncated` flag)
4. Refactored `fix-truncated` endpoint in `threads.py` to import and use `is_truncated_mid_sentence` instead of inline logic

## Alternatives Considered

### Keep them separate
- Pros: No refactoring needed.
- Cons: Two sources of truth for "proper ending characters". If we add a new punctuation mark (e.g., Chinese full stop `。`), we'd need to update two places. Violates DRY.
- Rejected: Maintenance burden.

### Replace fix-truncated entirely with fidelity warnings
- Pros: One system only.
- Cons: Users need the ability to reset truncated chapters and re-translate them. Fidelity warnings are informational only.
- Rejected: Both behaviors (warn AND reset) are needed. The shared function serves both use cases.

## Consequences
- `fidelity_checker.py` is now the **single source of truth** for all translation quality metrics (5 checks):
  1. Paragraph ratio
  2. Character ratio
  3. Dialogue line ratio
  4. Mid-sentence truncation
  5. Critical empty translation
- The `fix-truncated` endpoint is now a thin wrapper that calls `is_truncated_mid_sentence()`.
- Future punctuation additions (e.g., `。`, `！`) only need to update `PROPER_ENDING_CHARS` in one place.
- All 84 existing tests pass without modification.
