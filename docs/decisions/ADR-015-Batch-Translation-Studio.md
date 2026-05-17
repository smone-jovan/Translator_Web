# ADR-015: Batch Translation Studio & Smart Context Logic

## Status
Accepted

## Date
2026-05-17

## Context
User needs a way to translate many chapters at once (Bulk Translation) with granular control over AI extraction and progress visualization. Manual one-by-one translation is too slow for large novels.

## Decision
Implement a **Batch Translation Studio** consisting of:
1. **Dual-Mode UI**: 
   - **Easy Mode**: Fixed ranges (5, 10, 15 chapters) with recommended settings.
   - **Advanced Mode**: Interactive chapter checklist and manual extraction toggles.
2. **Smart Extraction Logic**:
   - If the thread's Lorebook has **> 40 entries**, AI Extraction is considered optional (not forced).
   - If **< 40 entries**, AI Extraction is recommended/prioritized to build a consistent glossary.
3. **Bulk Status Center**: A global persistent UI element that tracks the progress of the current batch.
4. **Processing Logic**: 
   - Always **Overwrite** existing translations in batch mode to ensure consistency after potential glossary updates.
   - Sequential processing to avoid overwhelming the LLM backend (LM Studio).

## Alternatives Considered
- **Parallel Translation**: Rejected because local LLMs (LM Studio) usually run on a single GPU and handle requests better sequentially. Parallelism would lead to massive timeouts.

## Consequences
- Significant increase in platform productivity.
- Better consistency in names/terms due to the "AI Extract First" recommendation.
- Requires new API endpoints for bulk queue management.
