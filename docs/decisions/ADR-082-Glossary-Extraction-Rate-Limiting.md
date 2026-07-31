# ADR-082: Glossary Extraction Rate Limiting

## Status
Accepted

## Date
2026-06-14

## Context
When "Glossary Scan First" is enabled during batch translation, the system calls `extract_glossary_pass()` for **every chapter** in the batch. For a novel with 381 chapters, this means 381 separate AI extraction calls, each producing 5-15 new terms. The result: 304+ glossary entries accumulated for a single thread, far exceeding what's useful for translation context.

The `enforce_context_limit()` function exists but was ineffective because the user's `max_context_terms` was set to 1000, which is rarely reached.

The intended behavior of "Glossary Scan First" is to seed the glossary with key terms from the **beginning** of a novel before translation starts, not to continuously extract from every chapter.

## Decision
Limit glossary extraction in batch mode to the first N chapters, where N = `extract_chapter_count` (a setting already available in GlobalSettings, default 12).

Implementation:
1. Added `extract_count` tracker to `ActiveBatch` class
2. In the batch worker loop, check `extract_count < extract_chapter_count` before enabling `force_extract`
3. After reaching the limit, log a message and disable extraction for remaining chapters
4. Per-chapter `auto_save_glossary` (from Translator Notes in the AI response) continues normally — this is fine because it only picks up organically-mentioned terms

## Alternatives Considered

### Hard-cap total glossary entries per thread
- Pros: Simple absolute limit.
- Cons: Would block Translator Notes from saving terms too. Users who manually add terms would hit the cap.
- Rejected: Extraction rate limiting is the correct scope.

### Remove "Glossary Scan First" entirely
- Pros: Eliminates the problem.
- Cons: Feature is valuable for seeding glossary before translation.
- Rejected: The feature is useful when limited.

## Consequences
- Glossary extraction now only runs on the first N chapters (default: 12) per batch
- A typical extraction will produce 50-100 terms (12 chapters × 5-10 terms each) instead of 300+
- The `auto_save_glossary` from Translator Notes still operates per-chapter, adding terms organically
- `enforce_context_limit` will archive excess terms using LFU+LRU policy if they exceed `max_context_terms`
- All 84 tests pass
