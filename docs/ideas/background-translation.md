# Background Translation & Persistent Reading

## Problem Statement
How might we ensure that large-scale novel translations (100+ chapters) are processed consistently and continue working even when the user navigates away or closes the browser?

## Recommended Direction
**Shielded Background Jobs with Event-Based Synchronization.**
Instead of a request-scoped streaming session, the translation process is decoupled from the HTTP request. 
1. The client triggers a "Start" event.
2. The server spawns a shielded async task that manages the LLM call, glossary injection, and incremental DB saves.
3. Multiple clients can "Subscribe" to the same task's output via an SSE queue.
4. Progress is tracked via a `translation_status` field in the database.

## Key Assumptions to Validate
- [ ] **LLM Concurrency**: Can LM Studio handle multiple concurrent background tasks or should we implement a FIFO queue?
- [ ] **DB Lock**: SQLite might lock during heavy background writes; need to ensure WAL mode or batching.
- [ ] **State Recovery**: If the server restarts, background tasks should ideally be marked as "Failed" or "Pending" to allow resume.

## MVP Scope
- `translation_status` tracking (idle, processing, done, error).
- Shielded background tasks in FastAPI.
- SSE subscription to existing background jobs.
- "Re-translate" manual override.

## Not Doing (and Why)
- **Automatic Multi-Chapter Queue**: For now, translation is triggered per chapter to avoid overwhelming local compute.
- **Server-Side Rendering (SSR)**: The app remains a SPA; SEO isn't critical for a personal tool.
- **Third-Party Background Workers (Celery/Redis)**: Keeping it simple with Python `asyncio` for self-hosted ease of use.

## Open Questions
- How do we handle "Context Drift" if the background task runs for hours while the user adds new lorebook entries?
- Should we implement an "Auto-Stop" if the backend detects LM Studio is unresponsive for too long?
