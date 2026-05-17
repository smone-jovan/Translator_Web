# ADR-017: Database Cleanup, Glossary Consistency, and Unified Markdown Note Stripping

## Status
Accepted

## Date
2026-05-17

## Context
During development, the LLM translator occasionally outputted metadata, status summaries, or English sentence patterns instead of Chinese term entries, leading to:
1. Garbage entries in the glossary (LorebookEntry database table) containing pure English sentences, notes, and symbols.
2. Inconsistent translations of names (e.g., translating "弥安" as "Miyan" or "Miyan's" despite the original character being "米莲" -> "Millian").
3. Unstripped translator notes in stored translations when the LLM formatted the headers with Markdown markers (e.g., `**Translator Notes:**` or `---` delimiters).

These issues compromised translation quality, cluttered UI screens, and degraded user-customized terminology accuracy.

## Decision
Implement a comprehensive cleanup, safety enhancement, and unified formatting pass:
1. **Database Purge**: Created and ran `cleanup_db.py` to completely eliminate entries containing no Chinese characters, entries exceeding 30 characters in length, and redundant entries.
2. **Explicit Character Alignment**: Manually mapped variations of target names (e.g., `弥安` -> `Millian`) into the glossary to ensure complete story consistency.
3. **Strict Extraction Rules in Context Engine**: Added strict runtime validations to `auto_save_glossary`:
   - Must contain at least one Chinese (Hanzi) character.
   - Must not exceed a length of 30 characters.
   - Automatically strips markdown formatting characters like `**` or `*` from terms and definitions before saving.
4. **Markdown-Resilient Note Stripping**: Upgraded `strip_translator_notes` and `notes_header_pattern` regex patterns to be fully Markdown-aware, matching bold asterisks `**`, horizontal rules `---`, and optional spacing surrounding translator note headers. Added iterative trailing-character removal to eliminate trailing markdown scars.

## Alternatives Considered

### Relying on Prompt-Level Guidance Alone
- **Pros**: Zero backend code changes required.
- **Cons**: High variance; AI models frequently deviate from prompt formatting constraints under complex translations.
- **Rejected**: System safety and database sanity require robust runtime validation controls.

## Consequences
- The SQLite database is perfectly clean of garbage data, ensuring instant glossary lookup times.
- Character names are perfectly aligned across typos (`弥安` -> `Millian`) without any variance.
- Future auto-saved glossary entries are guaranteed to be real Chinese terms under 30 characters.
- Stored translation text is perfectly clean of translator notes, bold indicators, or horizontal line scars.
