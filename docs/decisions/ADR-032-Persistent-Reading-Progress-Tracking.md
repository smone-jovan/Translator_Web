# ADR 032: Persistent Reading Progress Tracking & Auto-Restoration

## Context
As users read translated high-volume web novels on both mobile devices and desktops, maintaining a consistent reading position is crucial. Without persistence, a user switching devices or closing their browser would lose their place and have to search through hundreds of paragraphs manually.

Previously, we tracked the last read chapter ID via `UserBookmark`. However, we did not track the precise location *within* that chapter. Because chapters are often very long (containing thousands of words), we need a premium, frame-accurate method of saving and restoring the user's progress percentage dynamically.

## Decision
We decided to design and implement an asynchronous, debounced reading progress sync engine that connects the user's viewport directly to the SQLite backend database:

1. **Database Schema Extension:** We added `scroll_progress: Mapped[float] = mapped_column(default=0.0)` to the `UserBookmark` model in `database.py`. We implemented automatic SQLite table schema migration during `init_db()` to append the new column seamlessly if it is missing.
2. **Unified Viewport Progress Tracking:** Whether the user is reading in multi-column desktop mode (internal container scrolling) or on mobile Safari/Chrome (global window viewport scrolling), the frontend `ChapterReader.tsx` continuously measures the accurate viewport percentage:
   $$\text{Progress} = \frac{\text{ScrollTop}}{\text{ScrollHeight} - \text{ClientHeight}} \times 100$$
3. **Smart Debounced Synchronization API:** 
   - We introduced a new, fast REST endpoint: `PUT /api/threads/{thread_id}/chapters/{chapter_id}/scroll` that updates the scroll progress in the database.
   - To avoid overloading the local server and SQLite database with thousands of sequential HTTP requests during standard scrolling, we implemented a **2-second debouncing window** on the client side. The database is updated only after the user stops scrolling for 2 seconds.
4. **Auto-Restoration on Mount:** When fetching a chapter via `GET /api/threads/{thread_id}/chapters/{chapter_id}`, the backend packages the active `scroll_progress` into the `ChapterContent` payload. The frontend `ChapterReader.tsx` intercepts this, waits briefly (350ms) for DOM heights to settle, and automatically scrolls the columns or window back to the exact target coordinate smoothly.
5. **Fresh Chapter Transition Reset:** If the user manually transitions to a *different* chapter (e.g. next or previous chapter), the scroll progress is automatically initialized and saved at `0.0` to start fresh.

## Consequences
- **Positive:** Seamless, automated multi-device synchronisation. A user can read to 47.5% on their desktop, walk away, and immediately resume at the exact paragraph on their iPhone.
- **Positive:** Zero database bloat or write locks because of client-side debouncing.
- **Positive:** Unaffected page loads and standard reading feel; scroll restoration is executed instantly in the background without UI blocking.
- **Negative:** If a user abruptly closes the browser tab within 2 seconds of scroll inactivity, the absolute latest scroll coordinate might be off by a few percent. However, this is negligible in normal reading flows.

## Status
Accepted
