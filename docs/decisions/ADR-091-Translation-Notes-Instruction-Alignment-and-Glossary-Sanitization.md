# ADR-091: Translation Notes Instruction Alignment & Glossary Sanitization

## Status
Accepted

## Date
2026-08-12

## Context
During background translations (particularly on compact LLMs and local models), several chapters in thread "White Night" (Thread 62) produced outputs consisting solely of `### TRANSLATOR NOTES:` bullet points without any story translation prose.

Root-cause investigation revealed two compounding flaws:
1. **Prompt Instruction Contradiction**: `build_core_translation_guidelines()` explicitly forbade footnotes and notes (`DO NOT output any Footnotes or Translator Notes section. Output ONLY the pure translated story text.`), while `build_translator_notes_instruction()` immediately followed with instructions to output `### TRANSLATOR NOTES:` for new terms. This confused models into treating the prompt as a glossary-extraction task rather than a chapter translation task.
2. **Slash-Separated Compound Term Feedback Loop**: `auto_save_glossary()` stored slash-delimited compound terms (e.g. `夏茵 / 夏恩 / 莎恩 / 夏因 / 莎茵 → Shain`) as single terms. As these long slash terms re-entered the prompt, the model copied the multi-term format into its notes, poisoning future prompts and biasing the model toward generating lists of terms.
3. **Notes Stripping & Fallback Vulnerability**: When an AI outputted only notes, `strip_translator_notes()` stripped the entire output to an empty string. `clean_final_translation()` contained a fallback (`if not cleaned.strip(): cleaned = text`) which restored the raw notes and saved them into `content_translated`, triggering Fidelity Checker warnings.

## Decision
1. **Align Prompt Guidelines (`prompt_templates.py`)**:
   - Establish an unambiguous **PRIMARY DIRECTIVE**: the AI MUST translate the complete story text from beginning to end first.
   - Clarify that `### TRANSLATOR NOTES:` is strictly optional and may only be appended after the full story translation.
   - Remove contradictory "DO NOT output notes" commands from core translation guidelines.

2. **Sanitize Auto-Saved Glossary Terms (`context_engine.py`)**:
   - In `auto_save_glossary()`, split slash-separated terms (`/`) into individual clean single terms (e.g. `夏茵`, `夏恩`, `莎恩` mapped individually to `Shain`) before persistence.
   - Prevent multi-alias compound strings from polluting the Lorebook database and context prompts.

3. **Harden Translation Cleaner (`context_engine.py`)**:
   - Upgrade `strip_translator_notes()` to strip notes headers whether they occur at the beginning (before story), middle, or end of the output.
   - In `clean_final_translation()`, if stripping notes leaves an empty string (pure notes output with no story), return an empty string `""` instead of reverting to the raw notes. This triggers empty-translation detection in `background_translator.py` rather than saving junk prose.

4. **Database Sanitization & Re-translation**:
   - Ran a migration script across `app.db` converting 136 compound slash-separated entries into clean individual terms.
   - Re-translated all 10 affected chapters in Thread 62 to restore 100% full story prose with 0 fidelity warnings.

## Consequences
- Eliminates AI prompt confusion and task hijacking.
- Prevents compound term clutter in Lorebook entries and translation prompts.
- Ensures all chapters store pure narrative prose with reliable fidelity verification.
