# ADR-088: Real-Time Live Batch Translation Event Broadcasting

## Status
Accepted

## Date
2026-08-07

## Context
During background batch translation, users observed that green chapter translation indicators ("logo hijau") and polished titles did not update live in `ReaderPage.tsx` (the chapter list grid) or `LibraryPage.tsx`. Users were forced to reload the webpage or exit and re-open the thread to see which chapters had finished translating.

Investigation revealed:
- `BulkStatusCenter.tsx` polled `/api/threads/active-batch` every 2 seconds, but only emitted a `batch-completed` event when the entire batch finished.
- `ReaderPage.tsx` and `LibraryPage.tsx` only listened to `batch-completed` events, remaining static while individual chapters finished translating in the background.

## Decision
1. **Event Dispatching in `BulkStatusCenter.tsx`**: Update `checkStatus()` to dispatch a custom window event `'batch-progress'` with payload `{ thread_id, completed, total, current_chapter_id, failed_ids }` every 2 seconds while `data.active` is `true`.
2. **Reactive Listener in `ReaderPage.tsx`**: Add a `batch-progress` event listener in `ReaderPage.tsx`. When `detail.thread_id === threadId` and `detail.completed` or `detail.current_chapter_id` changes, silently invoke `fetchThread({ silent: true })`.
3. **Reactive Listener in `LibraryPage.tsx`**: Add a `batch-progress` event listener in `LibraryPage.tsx` to refresh book progress counts live.

## Alternatives Considered
- **WebSockets / Server-Sent Events (SSE)**:
  - Pros: Push-based notification from backend.
  - Cons: Requires persistent socket connections, connection lifecycle management, and architectural overhaul for simple polling intervals.
  - Rejected: Custom window event decoupling over existing status polling provides identical 0ms UI reactivity with zero backend complexity.

## Consequences
- Chapter grid items update live in real-time as each chapter finishes translating.
- Green translation indicators turn on dynamically without page reload.
- Polished titles and animated `<Loader2>` badges update seamlessly during active batch translation.
