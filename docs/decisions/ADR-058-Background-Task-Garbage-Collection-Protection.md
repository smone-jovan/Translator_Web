# ADR-058: Background Task Garbage Collection Protection

## Status
Accepted

## Context
The Auto-Prefetch feature, which automatically translates upcoming chapters in the background while the user reads, was reported to be malfunctioning ("prefetch tak berfungsi"). 
Investigation revealed that the system uses `asyncio.create_task()` to spawn background translation jobs without awaiting them. Starting with Python 3.7+ (and aggressively in 3.11+), the event loop only maintains *weak references* to fire-and-forget tasks. Because no strong references were kept, the Python Garbage Collector was randomly destroying the prefetch tasks mid-execution or before they even started.

## Decision
We implemented a strict strong-reference registry for all fire-and-forget asyncio tasks related to background translation:
1. **Registry Creation**: Added a global `_prefetch_tasks = set()` in `services/background_translator.py`.
2. **Task Tracking**: Whenever `asyncio.create_task()` is called inside `check_and_prefetch`, the resulting task object is explicitly added to `_prefetch_tasks`.
3. **Cleanup**: A callback (`task.add_done_callback(_prefetch_tasks.discard)`) is attached to safely remove the strong reference once the task completes natively.

## Consequences

### Positive
- Guarantees 100% execution reliability for background prefetching.
- Prevents silent failures that do not leave stack traces in the server logs.

### Negative
- Minor increase in memory usage as task objects are held in memory until completion, though this is negligible compared to LLM memory footprints.
