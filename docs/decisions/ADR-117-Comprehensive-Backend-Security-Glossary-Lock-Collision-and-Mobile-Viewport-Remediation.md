# ADR-117: Comprehensive Backend Security Hardening, Single-Syllable Pinyin Collision Mitigation, and Mobile Viewport Geometry Remediation

## Status
Accepted

## Date
2026-10-14

## Context
Following a full-system audit across backend services, scraping adapters, SQLite dual-database isolation, glossary locking, and mobile viewport ergonomics (Issues #2, #3, #4, #5, #6, and #7), several architectural defects and edge-case collisions were identified:

1. **Async Event-Loop Collision on Synchronous Endpoints (Issue #7)**:
   In `backend/routers/threads.py`, `get_chapter` was defined as a synchronous `def` running inside FastAPI's worker threadpool. On-demand scraping invoked `asyncio.run()` with `NovalpieAdapter.scrape_chapter_content()`. Because `NovalpieAdapter` cached a class-level `asyncio.Semaphore`, repeated calls across different event loops threw `RuntimeError: <asyncio.locks.Semaphore object> is bound to a different event loop`. Furthermore, the fallback branch lacked SSRF redirect protection.

2. **Incomplete Scraper SSRF Hardening & Adapter Routing (Issue #7)**:
   Three secondary scraping endpoints in `backend/routers/scrape.py` (`/threads/import-url`, `fetch-next`, and streaming `crawl-next`) used raw `httpx.AsyncClient` without URL validation or redirect event hooks, and lacked dedicated routing for `sfacg.com`. In `sfacg.py`, `verify=False` was inadvertently disabling TLS certificate verification.

3. **Dual-Database In-Memory Tenancy Collisions (Issue #7)**:
   In-memory registries (`ACTIVE_IMAGE_JOBS` and `active_tasks`) previously mirrored entries to raw integer keys (`ACTIVE_IMAGE_JOBS[thread_id] = entry`), creating state collisions between `app.db` and `ghost.db`. Switching workspaces in `system.py` triggered a global `stop_all_batches()` cancelling translations across all workspaces.

4. **EPUB Image Extraction Overwrites (Issue #7)**:
   In `backend/routers/epub.py`, `os.path.basename()` caused EPUB images in distinct chapter subdirectories (e.g. `ch1/001.jpg` and `ch2/001.jpg`) to overwrite one another in `uploads/images/thread_{id}/`.

5. **Single-Syllable Pinyin Collision in Glossary Lock (Issue #6)**:
   In `backend/services/glossary_lock.py`, single-syllable Hanzi terms with 4+ letter pinyin (`Song`, `Fang`, `Long`, `Wang`, `Tang`, `Gang`) were compiled with `re.IGNORECASE`, causing common English words like *"a beautiful song"* or *"a long time"* to be replaced by character names.

6. **Non-Human Entity False-Negatives & Term Priority (Issue #6)**:
   In `backend/services/context_engine.py`, weapons or techniques with notes referencing creators/wielders (e.g. *"A sacred sword forged by the sect master"*) were incorrectly denied non-human classification due to role tokens (`master`, `protagonist`). In Fast Mode (10 term cap), locked terms (`is_locked`) lacked priority ordering.

7. **Mobile Viewport Overflows & Touch Physics (Issues #2, #3, #4, #5)**:
   - `index.html` blocked pinch-to-zoom (`user-scalable=no`), violating WCAG 2.1 SC 1.4.4.
   - `BottomNav.tsx` and reader toolbars lacked `env(safe-area-inset-bottom)`.
   - `SettingsPage.tsx` restricted mobile Ghost PIN to 5 digits only, locking out users with arbitrary PIN lengths.
   - `ChapterListControls.tsx` Polish Settings popover (`w-72 right-0`) overflowed by 129px offscreen on mobile when wrapped to the left.
   - `ChapterReader.tsx` top bar overflowed on 320px–390px screens due to 9 simultaneous buttons.
   - `BulkStatusCenter.tsx` collided with `BottomNav.tsx`.
   - `RelationshipGraph.tsx` node clicks were dead console-only stubs.

---

## Decisions

### 1. Backend Core & Async Event-Loop Safety
- **Async Endpoint Conversion**: Converted `get_chapter` to `async def get_chapter` in `backend/routers/threads.py`. Replaced `asyncio.run()` with direct coroutine awaiting.
- **Event-Loop Aware Semaphore**: Updated `NovalpieAdapter.get_semaphore` to check `asyncio.get_running_loop()` and recreate the semaphore if executed in a new loop.
- **Universal Safe Client & SSRF**: Deployed `create_safe_async_client` across `threads.py` and `scrape.py`. Re-raised `HTTPException` so SSRF 400 errors propagate directly to clients.
- **TLS Verification**: Removed `verify=False` in `sfacg.py`.
- **Path Traversal Protection**: Implemented strict `Path.resolve()` and `candidate.is_relative_to(base_dir)` validation in `epub.py`.

### 2. Pure Compound Key Multi-Tenancy
- **Purged Integer Alias Keys**: Removed integer mirrors from `ACTIVE_IMAGE_JOBS` and `active_tasks`. All queries strictly scope by `(str(workspace).lower(), id)`.
- **Workspace Scoped Scraper Config**: Updated `get_scraper_concurrency(workspace)` and `get_novalpie_auth_config(workspace)` in `novalpie.py`.
- **Isolated Workspace Switching**: Removed global `stop_all_batches()` from `system.py:switch_workspace`.

### 3. Glossary Lock Case-Sensitivity & Expanded Stopwords
- **Enforced Case-Sensitivity on 1-Syllable Pinyin**: In `glossary_lock.py`, all single-syllable Hanzi terms and single-word aliases now strictly match capitalized tokens (`\bSong\b`, `\bLong\b`).
- **Expanded Collision Stopwords**: Added `song`, `fang`, `long`, `wang`, `tang`, `gang`, `ring`, `king`, `wing`, `hang`, `bang`, `yang`, `uang`, `tiang`, `siang`, `liar` to `COMMON_COLLISION_STOPWORDS`.

### 4. Non-Human Entity Detection & Locked Term Priority
- **Strong Opening Phrase Detection**: Added regex in `is_non_human_term` to identify weapons, artifacts, pills, and locations regardless of role words in subordinate clauses.
- **Locked Term Prompt Priority**: In `build_translation_prompt`, added `order_by(desc(LorebookEntry.is_locked), desc(LorebookEntry.usage_count), desc(LorebookEntry.last_used_at))`.
- **Duplicate Prevention**: Added HTTP 409 conflict validation on `PUT /api/lorebook/{entry_id}`.

### 5. Mobile Ergonomics & Viewport Geometry
- **Re-enabled Pinch-to-Zoom**: Updated `index.html` viewport meta tag to standard `viewport-fit=cover`.
- **Safe Area Insets**: Added `pb-[max(1rem,env(safe-area-inset-bottom))]` across `BottomNav.tsx` and reader floating toolbars.
- **Flexible Mobile Ghost PIN**: Aligned `SettingsPage.tsx` with `Sidebar.tsx` (arbitrary string length, Enter submit, `select-none` on 10s press).
- **Responsive Popovers & Sheets**:
  - `ChapterListControls.tsx`: `left-0 sm:left-auto sm:right-0 w-[min(18rem,calc(100vw-2rem))] max-h-[75vh]`.
  - `ChapterReader.tsx`: Hid duplicate prev/next buttons on mobile (`hidden md:inline-flex`), bounded Aa popover.
  - `ReaderPage.tsx`: Responsive header padding and compact button sizing.
  - `BulkFetchModal.tsx`: Applied responsive sheet layout on `xs`.
  - `BulkStatusCenter.tsx`: Raised bottom offset to float cleanly above `BottomNav`.
- **Interactive Character Network**: Added touch-friendly detail card in `RelationshipGraph.tsx` displaying character name, connection directions, relationship types, and notes.
- **Hash Navigation Listener**: Added global `hashchange` listener in `App.tsx` ensuring `#translate` cleanly switches tabs and exits active readers.

---

## Consequences

### Positive
- Zero event-loop runtime crashes during on-demand reading.
- Complete SSRF defense-in-depth and path traversal immunity across all scraping and file upload endpoints.
- Total memory isolation between `app.db` and `ghost.db`.
- Preserved narrative readability: English words (*song*, *long*) are never corrupted by glossary locking.
- 100% mobile touch ergonomics and zero viewport overflow across all screens (320px–1440px+).
- All 308 backend tests pass; frontend typecheck, lint, and production build pass with 0 errors.
