# ADR-092: Punctuation False-Positive Elimination and Fidelity Warning Clarity

## Status
Accepted

## Date
2026-08-14

## Context
Following the implementation of ADR-072 (Fidelity Verification) and ADR-080 (Unified Fidelity and Truncation Detection), users noticed a high volume of `fidelity_warning` flags appearing on newly translated web novels.

Upon systematic investigation across 5 active novel threads (544 chapters total), two key architectural deficiencies were identified:

1. **False Positives in Truncation Detection:**
   The `PROPER_ENDING_CHARS` list omitted common valid web novel sentence and chapter endings:
   - Single closing quotes (`'`) used in English dialogues.
   - Bracket terminators (`]`, `}`, `)`) frequently used in game status windows and system announcements (e.g. `[...What true despair.]`, `[Special Conception: Added!]`).
   - East Asian closing brackets and punctuation (`」`, `』`, `】`, `》`, `〉`, `；`).
   - Emotive / expressive ending symbols common in web novels (`♥`, `♡`, `★`, `☆`, `♪`, `♫`).
   - Markdown formatting wrappers (e.g., italics `*'It's over.'*` or bold `**Bab Selesai.**`), where trailing emphasis characters obscured inner punctuation.

2. **Misleading Warning Messages in Database:**
   Whenever `verify_translation_fidelity()` flagged any issue (including mid-sentence truncation or dialogue drop), both `background_translator.py` and `threads.py` persisted a hardcoded string reporting only paragraph counts:
   `"Suspicious translation structure: Original has X paragraphs, Translated has Y paragraphs (ratio: Z.ZZ)."`
   This created significant confusion for users who saw chapters with normal ratios (e.g., `0.97`, `1.00`, `1.12`) tagged with "Suspicious translation structure".

## Decision

1. **Expanded `PROPER_ENDING_CHARS` & Markdown Trimming in `services/fidelity_checker.py`:**
   - Extended `PROPER_ENDING_CHARS` to comprehensively support ASCII quotes/brackets, CJK quotes/brackets, punctuation, and web novel emotion glyphs.
   - Updated `is_truncated_mid_sentence()` to strip trailing markdown emphasis markers (`*`, `_`, `` ` ``) before verifying the terminating character.

2. **Detailed Diagnostic Warning Messages in Storage:**
   - Updated `background_translator.py` and `routers/threads.py` to persist the actual underlying causes returned in `fidelity["warnings"]` (`" | ".join(fidelity["warnings"])`) rather than a generic paragraph ratio formula.

3. **Database Migration & Sanitization:**
   - Performed a retroactive audit and cleanup on all existing chapters in `app.db`, immediately removing false positive flags and updating genuine truncation warnings with specific diagnostic details.

4. **Regression Test Coverage:**
   - Added automated tests in `backend/tests/test_services/test_fidelity_checker.py` testing quotation marks, brackets, emotive symbols, markdown wrappers, real truncations, and paragraph ratio drops.

## Consequences

- **Zero False-Positive Warnings:** Chapters ending with valid dialogue quotes, system brackets, emojis, or markdown formatting are no longer falsely flagged as truncated.
- **Actionable Diagnostics:** When a chapter is flagged, the user and UI reader display the exact reason (e.g., *"Translation appears to be cut off mid-sentence"* vs *"Paragraph count dropped significantly: 212 original → 50 translated"*).
- **Cleaner Reader UX:** 14 false-positive warnings were cleaned from the active database, leaving only the 24 chapters that legitimately require re-translation.
- **Backward Compatibility:** All existing 109 backend tests and frontend builds pass cleanly.
