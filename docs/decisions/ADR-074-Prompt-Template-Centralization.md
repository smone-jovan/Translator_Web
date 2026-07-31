# ADR-074: Prompt Template Centralization

## Status
Accepted

## Date
2026-06-13

## Context
Translation prompts are scattered across 5+ locations in the codebase:
- `context_engine.py`: Main chapter translation prompt, glossary extraction prompt
- `polish.py`: Title translation, title cleaning, synopsis translation
- Various inline strings throughout the translation pipeline

Changing the translation philosophy (e.g., honorific handling, formality level, pronoun conventions) requires editing multiple files. Finding all prompt locations requires grep-based archaeology. This violates DRY, makes maintenance error-prone, and risks inconsistency — the chapter translation prompt might use one convention while the title translation prompt uses another.

The problem is compounded by ADR-071 (Genre-Aware Translation Prompting), which adds genre-specific prompt fragments. Without centralization, genre-specific logic would need to be duplicated across every prompt location.

## Decision
Create `services/prompt_templates.py` as the single source of truth for all prompt fragments. The module exports:

- **Named constants** for context limits (`GLOBAL_CONTEXT_MAX_CHARS`, `THREAD_CONTEXT_MAX_CHARS`, `STYLE_GUIDE_MAX_CHARS`), glossary settings (`GLOSSARY_TERM_MAX_LENGTH`, `GLOSSARY_MIN_TERM_LENGTH`), auto-continue settings (`MAX_CONTINUATIONS`, `CONTINUATION_TAIL_CHARS`), and streaming intervals (`STREAM_SAVE_INTERVAL`)
- **Builder functions** that compose fragments into complete prompts: `build_core_translation_guidelines()` (line 175), `build_glossary_extraction_prompt()` (line 319), `build_title_translation_prompt()` (line 270), `build_translator_notes_instruction()` (line 239), `build_continuation_prompt()` (line 256), `build_title_cleaning_prompt()` (line 287), `build_synopsis_translation_prompt()` (line 302), `build_relationship_extraction_prompt()` (line 356)
- **Genre-specific fragments** (ADR-071) as `GENRE_PROMPT_FRAGMENTS` dictionary keyed by genre name, including embedded honorific, onomatopoeia, and formatting rules within each genre fragment

All prompt consumers (`context_engine.py`, `polish.py`, `background_translator.py`) import from this module instead of defining prompts inline. The module is pure Python — no template engine, no file I/O, no external dependencies.

## Alternatives Considered

### YAML/JSON Template Files
- Pros: Non-developers can edit prompts, clear separation of code and content
- Cons: Adds file I/O complexity, loses IDE autocompletion and type checking, harder to compose fragments programmatically, requires handling missing/malformed files
- Rejected: The added complexity of file-based templates isn't justified — prompt changes still require deployment, and Python string formatting is sufficient

### Jinja2 Templating Engine
- Pros: Powerful templating language, widely used, supports inheritance and macros
- Cons: Adds a dependency, introduces a new abstraction layer, templates are harder to debug, team needs to learn Jinja2 syntax
- Rejected: Over-engineering for string composition — Python f-strings and string concatenation are simpler and more transparent

### Database-Stored Prompts
- Pros: Editable at runtime without deployment, per-user customization possible
- Cons: Harder to version control, no code review for prompt changes, migration complexity, risk of runtime prompt corruption
- Rejected: Prompt changes are architectural decisions that should go through version control and code review

## Consequences
- **Positive:** Single point of control for all translation prompts — changing conventions requires editing one file
- **Positive:** All prompt changes are version-controlled and reviewable in pull requests
- **Positive:** Genre-specific fragments (ADR-071) integrate naturally as `GENRE_PROMPT_FRAGMENTS` entries in the module
- **Positive:** Prompt consumers become simpler — they call builder functions instead of constructing prompts inline
- **Positive:** Honorific, onomatopoeia, and formatting rules are embedded within genre fragments, avoiding standalone constant duplication
- **Negative/Risk:** The module becomes a critical dependency — breaking changes in `prompt_templates.py` affect the entire translation pipeline
- **Negative/Risk:** New prompt types (e.g., for future features) are added by extending this module rather than scattering new inline strings
