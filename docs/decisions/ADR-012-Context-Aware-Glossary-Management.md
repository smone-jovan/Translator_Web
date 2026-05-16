# ADR-012: Context-Aware Translation Pipeline & Glossary Management

## Status
Accepted

## Date
2026-05-17

## Context
As the project evolved, the AI translation quality needed stricter controls to maintain consistency across long novels. Key issues included:
- Glossary size growing indefinitely, causing token bloat and LLM confusion.
- Generic dictionary translations being prioritized over world-building context.
- Missing capture of new terms from AI output into the persistent glossary.
- Instability in background tasks causing "No running event loop" errors.

## Decision
Implemented a comprehensive "Context Engine" and refined the background translation pipeline.

### Key Technical Decisions:
1.  **Usage-Based Glossary Optimization**:
    - Added `usage_count` and `last_used_at` to `LorebookEntry`.
    - Limited glossary injection to the **top 50** most relevant terms per chapter.
    - Implemented automatic cleanup: When a thread exceeds 100 terms, the 20 least-used terms are deleted.
2.  **Strict Translation Ethics Injection**:
    - Integrated 4 mandatory rules into the system prompt:
        - *Context over Dictionary*: Prioritize situational meaning.
        - *Translate vs Transliterate*: Translate objects/techniques, transliterate names.
        - *World-Building*: Avoid real-world location mapping (e.g., Kyoto vs The Capital).
        - *Honorifics*: Preserve source language norms (Senior Brother, -san, etc.).
3.  **Robust Auto-Save Logic**:
    - Re-engineered `auto_save_glossary` to use flexible regex (matching `Translator's Note`, `Notes`, etc.).
    - Implemented strict duplicate checking before insertion.
    - Standardized parsing of the `- Original → Translated (Notes)` format.
4.  **Database Auto-Migration**:
    - Added startup logic to `init_db` to automatically handle `ALTER TABLE` for existing SQLite databases when new features are added.

## Consequences
- **Token Efficiency**: Dramatic reduction in prompt size for threads with large lorebooks.
- **Improved Consistency**: AI now respects established terminology more strictly due to the "Absolute Law" prompt instruction.
- **Maintenance-Free**: The glossary system is now self-maintaining through usage tracking and auto-cleanup.
- **Reliability**: Migrating background jobs to FastAPI `BackgroundTasks` resolved runtime stability issues.
