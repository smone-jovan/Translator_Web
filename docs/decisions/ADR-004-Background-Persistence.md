# ADR-004: Persistent Background Translation

## Status
Accepted

## Date
2026-05-16

## Context
Translation of large chapters (4000+ words) can take several minutes. Standard HTTP requests or browser-side SSE streams are fragile; if the user refreshes the page, navigates away, or the browser puts the tab to sleep, the translation connection is severed. This leads to wasted tokens/compute and a frustrating user experience where they have to restart the translation.

## Decision
Implement a **Shielded Background Task** architecture in the FastAPI backend combined with a **Thread-Safe Queue** for SSE streaming.

1. **Decoupled Processing**: The backend spawns an `asyncio.create_task` (shielded) that handles the LLM streaming and incrementally saves progress to the SQLite database.
2. **Persistence State**: A `translation_status` field is added to the `Chapter` model to track whether a chapter is `idle`, `processing`, or `done`.
3. **SSE Synchronization**: Instead of streaming directly from the AI Provider to the HTTP response, the background task pushes chunks into a list of memory queues. The SSE endpoint then simply consumes from its assigned queue.
4. **Auto-Resume**: The frontend checks the `translation_status` on load. If `processing`, it automatically establishes a connection to the stream, picking up from the current live progress.

## Alternatives Considered
### Celery / Redis
- **Pros**: Robust, handles task persistence across server restarts.
- **Cons**: Overkill for a local self-hosted tool. Requires a separate Redis process.
- **Decision**: Rejected in favor of native `asyncio` to keep the installation simple for users.

### Client-Side LocalStorage Saving
- **Pros**: No server changes needed.
- **Cons**: Doesn't continue if the tab is closed. Unreliable for long tasks.
- **Decision**: Rejected.

## Consequences
- **Server Load**: Multiple background tasks can run simultaneously. We need to monitor LM Studio's ability to handle concurrent requests.
- **Data Integrity**: We must ensure that only one background task runs per `chapter_id` at a time.
- **User UX**: The reader feels "alive" and respects the user's time.
