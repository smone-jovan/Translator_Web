# ADR-062: Temporary API Key Exhaustion Memory

## Status
Accepted

## Date
2026-06-06

## Context
When running large batch translations using multiple Google Gemini API keys, some keys inevitably hit their daily Requests Per Day (RPD) quota limits, returning an `HTTP 429 Resource has been exhausted` error. Previously, when a key was exhausted, the batch worker would treat it as a generic retryable error. Without persistent state, the key rotation logic would continually rotate back into the burned key on subsequent chapters, triggering repeated failures, wasting time, and eventually failing chapters permanently.

## Decision
Implement a lightweight, in-memory RAM blacklist to temporarily exclude Gemini API keys that hit their daily RPD quota limit.
- Track exhausted keys in a global dictionary (`exhausted_gemini_keys` in `secrets.py`) mapping `API_KEY` to `YYYY-MM-DD`.
- Clear keys automatically when the local day resets (`_clear_stale_exhausted_keys`).
- Introduce `QuotaExhaustedError` to gracefully stop the entire batch if *all* available keys are exhausted.
- Catch Quota errors in the `_run_batch_worker` retry block by matching "429" and "quota/exhausted" in the exception string.
- Expand API Responses (`/api/threads/active-batch` and `/api/threads/{thread_id}/batch-status`) to deliver real-time exhaustion statistics (`total_keys`, `exhausted_keys`, `quota_exhausted`).
- Update `BulkStatusCenter.tsx` to provide real-time UI feedback through an amber warning indicating exhausted key fractions (e.g., `🔑 1/3 Exhausted`) and a red "Stopped (Quota)" state when halted.
- Enhance safety filter detection in `gemini.py` to correctly capture `finish_reason="OTHER"` or vague HTTP 400 responses from Google API, so safety blocks (`PROHIBITED_MARKER`) are not misinterpreted as timeout errors.

## Alternatives Considered

### Persistent Database Blacklist
- **Pros:** Endures server restarts.
- **Cons:** Requires schema migrations and cron jobs to reset correctly at midnight (which varies per timezone, adding complexity).
- **Rejected:** The RAM approach provides the exact same benefits for normal usage scenarios without DB bloat and timezone headaches.

### Continuing Batch with Remaining Keys Silently
- **Pros:** Easier to implement (just skip the key).
- **Cons:** The user has no visibility into the health of their keys. If 4 out of 5 keys die, the system would run 5x slower, and the user would assume the app was lagging.
- **Rejected:** UI feedback is crucial for users managing their own API keys.

## Consequences
- **Improved Stability:** Batch translation stability is drastically improved because burned keys are skipped entirely for the remainder of the day.
- **Better UX:** Users are clearly notified via the UI when keys are exhausted.
- **Safety:** If all keys are burned, the batch safely halts instead of infinitely looping or discarding chapters.
- **Drawback:** Memory clears on server restart. If the backend is restarted on the same day, the system will "forget" which keys were burned. It will try them again and immediately re-blacklist them upon receiving the first 429. This is an acceptable tradeoff for simplicity.
