# ADR-049: Batch Worker Reliability

## Status
Accepted

## Date
2026-05-30

## Context
The batch translation worker had several reliability issues:

1. **Infinite loop**: After a chapter translated successfully, it was not removed from `batch.chapter_ids`. The `while True` loop would pick it up again, find it already translated, and skip it — repeating indefinitely.
2. **No retry for transient errors**: Service unavailable (429/503) errors permanently failed chapters instead of retrying.
3. **Skip check too loose**: Only checked `content_translated` — a chapter with `translation_status="done"` but empty content would still be skipped.
4. **Delete all translations incomplete**: Only reset chapters with `content_translated` or `title_translated` — chapters with `translation_status="done"` but no content were missed.

## Decision

### Fix 1: Remove completed chapters from work list
- After a chapter succeeds or permanently fails, remove it from `batch.chapter_ids`.
- Increment `batch.completed` for both success and failure cases.
- The `while True` loop rebuilds the work queue from `batch.chapter_ids` — empty list = done.

### Fix 2: Retry logic for transient errors
- Added `_is_retryable_error()` helper: detects 429, 503, 502, 408, rate limit, timeout, etc.
- When `_do_translate()` hits a retryable error, it re-raises instead of marking as "error".
- Batch worker catches retryable errors and re-queues the chapter with exponential backoff:
  - Round 1: wait 10s
  - Round 2: wait 20s
  - Round 3: wait 40s
  - Max 3 retries per chapter
- Chapter status resets to "idle" during retry wait.
- Non-retryable errors or max retries exceeded → permanent failure, move to `failed_ids`.

### Fix 3: Stricter skip check
- Changed from: `if chapter.content_translated and not force_overwrite`
- Changed to: `if chapter.translation_status == "done" and chapter.content_translated and not force_overwrite`
- Both conditions must be true to skip.

### Fix 4: Robust delete all translations
- `delete_all_translations` now checks: `content_translated or title_translated or translation_status == "done"`
- Any of these conditions triggers a full reset (content nullified, status set to "idle").

## Alternatives Considered

### Use a task queue (Celery, RQ)
- **Pros**: Proper retry, scheduling, monitoring.
- **Cons**: Adds infrastructure dependency (Redis/RabbitMQ); overkill for a single-user app.
- **Rejected**: asyncio-based retry is sufficient for this scale.

### Persist batch state to database
- **Pros**: Survives server restarts.
- **Cons**: Complex state management; batch is ephemeral by design.
- **Rejected**: Batch state is in-memory by design — server restart = user re-starts batch.

### Mark failed chapters with "retry_pending" status
- **Pros**: UI can show which chapters are pending retry.
- **Cons**: Adds a new status value; complicates status checks throughout codebase.
- **Rejected**: "idle" status during retry is sufficient — user sees the chapter is not "done".

## Consequences
- **Positive:** Batch worker no longer loops infinitely on completed chapters.
- **Positive:** Transient API errors (rate limits, service unavailable) are automatically retried with backoff.
- **Positive:** "Delete All Translations" correctly resets all chapters regardless of edge cases.
- **Negative/Risk:** Retry delays may slow batch completion during API instability (acceptable trade-off).
- **Negative/Risk:** Exponential backoff (10s → 20s → 40s) may be too aggressive for some providers.
