# ADR-037: Thread-Level TXT Cleaning and Book Builder Cleanup Preview

## Status
Proposed

## Date
2026-05-19

## Context
The codebase now has two different cleanup flows:

1. A file-based `TXT Cleaner` endpoint at `/api/tools/txt-cleaner-file` that accepts an uploaded `.txt`, applies deterministic Python cleanup, and returns a cleaned `.txt` download.
2. Per-thread destructive cleaners at `/api/threads/{thread_id}/txt-cleaner` and `/api/threads/{thread_id}/epub-cleaner` that modify the canonical SQLite chapter records in place.

That split leaves a product gap for older dirty EPUB threads:

- Users may want to clean an already-imported book without immediately mutating the stored thread.
- Users may want a downloadable cleaned `.txt` artifact first, then decide whether the cleanup should also be applied to the thread.
- The requested flow must stay local, deterministic, and LLM-free. Cleanup should be done with Python rules and existing database content only.

Current implementation gaps that motivate this ADR:

1. `TXT Cleaner` for uploaded files is disconnected from thread/book workflows.
2. Per-thread cleaners are destructive and do not offer preview, notification, or user confirmation.
3. `Book Builder` currently exports selected chapters, but it is not yet a cleanup surface and does not provide a pre-export sanitation checkpoint for old noisy threads.
4. `clean_title()` falls back to the original title when cleanup removes everything, which can preserve fully noisy titles instead of surfacing them for review.

## Decision
We will treat cleanup as a two-stage thread-level workflow centered around the existing book/thread model:

1. **Thread-Sourced TXT Build**
   - Add a `Book Builder` cleanup mode that assembles thread chapter content into a generated `.txt`.
   - The source of truth is the existing chapter data already stored in SQLite.
   - No LLM is involved at any stage.

2. **Deterministic Cleanup Preview**
   - Run the same Python/rule-based cleanup family used by `TXT Cleaner` against the generated thread text.
   - Produce a downloadable cleaned `.txt` artifact for the user before any destructive write-back.
   - Return structured counts such as chapters scanned, lines removed, suspicious titles found, and candidate junk chapters.

3. **Explicit User Choice**
   - Surface a thread-level notification/modal after cleanup finishes.
   - Offer two actions only:
   - `Apply to thread`: write cleaned content back into the existing chapter records.
   - `Keep original thread`: leave the database untouched and only keep the downloaded cleaned `.txt`.

4. **Scope Boundary**
   - This flow is for legacy or dirty imported threads, especially EPUB imports with ad spam and junk pages.
   - It does not replace the standalone upload-based `TXT Cleaner`; that tool remains useful for one-off local files outside the library.

## Alternatives Considered

### Keep Only Destructive Per-Thread Cleaners
- **Pros**: Simpler backend and UI.
- **Cons**: Too risky for cleanup on old threads because users cannot inspect output first.
- **Rejected**: The requested workflow explicitly needs preview plus user choice.

### Route Cleanup Through an LLM
- **Pros**: Could catch more nuanced garbage.
- **Cons**: More cost, slower, nondeterministic, and risky for destructive editing.
- **Rejected**: The cleanup requirement is specifically local, database/Python-driven, and non-LLM.

### Export-Only Cleaning With No Thread Integration
- **Pros**: Safest possible data preservation.
- **Cons**: Leaves the library dirty forever and forces users to repeat cleanup every export.
- **Rejected**: Users need the option to promote the cleaned result back into the thread.

## Consequences
- Cleanup becomes safer because users can inspect a generated result before mutating stored chapters.
- `Book Builder` gains a practical maintenance role for old imported books, not just export formatting.
- Backend cleanup logic should be refactored so file-based, thread-based, and preview-based cleanup all share the same deterministic rule engine.
- The feature should be documented as `Proposed` until the preview/notification/apply flow is actually implemented in both backend and UI.
