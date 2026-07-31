# ADR-087: Garbage Glossary Entry Filtering

## Status
Accepted

## Date
2026-08-01

## Context
Automatic glossary extraction from AI translation notes occasionally captured low-quality, placeholder, or meta terms (e.g. `N/A`, `Unknown`, `none`, `tidak ada`, `Translator Note`, untranslated raw Chinese `叶修 → 叶修`). When injected into future translation prompts, these low-quality terms caused AI hallucinations or corrupted translation outputs.

## Decision
Implement `ContextEngine.is_garbage_lorebook_entry(original_term, translated_term)` in `backend/services/context_engine.py` to filter out:
1. Placeholder translations (`N/A`, `Unknown`, `none`, `tidak ada`, `no new terms`, `context required`).
2. AI meta/instruction text (`Translator Note`, `Final List`, `Chapter Title`, `Summary`).
3. Untranslated Chinese terms where `original_term == translated_term`.
4. Pure digit strings or empty terms.

Apply this filter in both `build_translation_prompt()` (prompt construction) and `auto_save_glossary()` (database persistence).

## Consequences
- Prevents low-quality/junk terms from being saved to the database.
- Guarantees clean, high-quality term injection into LLM translation prompts.
