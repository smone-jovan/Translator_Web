# ADR-071: Genre-Aware Translation Prompting

## Status
Accepted

## Date
2026-06-13

## Context
The translation prompt in `context_engine.py` is hardcoded to 3 genres (urban/system/transmigration). Chinese web novels span 10+ genres — xianxia, wuxia, xuanhuan, sci-fi, historical/court, danmei, and more — each with drastically different terminology and tone requirements. A wuxia novel demands martial arts register and jianghu vocabulary, while a historical court novel requires formal speech, imperial titles, and political intrigue terminology. The current 3-genre approach produces generic translations that miss genre-specific nuance.

## Decision
Genre detection is performed at runtime via `detect_primary_genre()` in `services/prompt_templates.py:374`, which parses the FIRST genre from the existing `genres` and `tags` text fields already stored on the Thread model — no additional database column is needed. Genre-specific prompt fragments live in `services/prompt_templates.py` (shared with ADR-074). The `build_core_translation_guidelines()` function in `prompt_templates.py:175` is called by `context_engine.py:51` to inject genre-appropriate instructions based on the thread's primary translation genre.

Each genre fragment includes:
- Tone and register guidance (e.g., formal for court, visceral for wuxia)
- Genre-specific terminology conventions (e.g., cultivation ranks for xianxia, martial techniques for wuxia)
- Common pitfalls to avoid (e.g., don't modernize speech in historical novels)

10 genre categories are supported (cultivation, wuxia, xuanhuan, urban, system, transmigration, sci-fi, historical, romance, horror) with a default fallback for unclassified novels.

## Alternatives Considered

### Manual Per-Thread Prompt Editing by Users
- Pros: Maximum flexibility, users can fine-tune exactly
- Cons: Requires translation expertise to write effective prompts, too complex for casual users
- Rejected: Most users want good defaults, not a prompt engineering interface

### Auto-Detect Genre from Text
- Pros: Zero user effort, fully automatic
- Cons: Unreliable — genre detection from a single chapter is error-prone, especially for novels that blend genres
- Rejected: Incorrect genre detection would produce worse translations than no genre at all

### Hardcode All Genres into One Mega-Prompt
- Pros: Simple implementation, no branching logic
- Cons: Wastes context window with irrelevant instructions (e.g., cultivation terms in a modern romance), confuses the model with contradictory guidance
- Rejected: Context bloat degrades translation quality, especially on smaller-context models

## Consequences
- More accurate genre-specific translations with appropriate tone, register, and terminology
- `Thread.genres` field gains semantic importance — the first genre drives translation behavior
- New module `services/prompt_templates.py` becomes the single source of truth for prompt fragments (see ADR-074)
- Adding a new genre requires only adding a new prompt fragment to `prompt_templates.py`
- Novels with no genre set fall back to the existing generic prompt — no regression for current users
