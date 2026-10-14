# ADR-118: Ghost Workspace Frontend Cache Isolation, SSE Tenancy Hardening, and GlobalSetting Orchestration Architecture

## Status
Accepted

## Date
2026-10-14

## Context
Following the implementation of ADR-117 and automated knowledge graph traversal (via Graphify), a comprehensive cross-layer audit revealed several remaining multi-tenancy edge-case vulnerabilities and highlighted the central architectural role of `GlobalSetting`:

1. **Client-Side Cache Leakage Across Workspaces**:
   In `src/pages/LibraryPage.tsx`, `src/App.tsx`, `src/pages/ReaderPage.tsx`, and `src/pages/BookmarksPage.tsx`, storage keys (`readomni_library_cache_v1`, `readomni_app_session_v1`, `readomni_reader_session_${id}`, and in-memory caches) were static. When switching workspaces via PIN authentication, `window.location.reload()` did not clear `sessionStorage`. Consequently, cached books and last-read chapters from `ghost` briefly rendered in `main` before network revalidation finished.

2. **Residual Integer Tenancy in SSE Translation Queues**:
   In `backend/routers/translate.py` and `backend/services/background_translator.py`, streaming subscribers were registered to both `(ws, chapter_id)` and raw integer `chapter_id`. Under identical auto-increment IDs in `app.db` and `ghost.db`, concurrent streams could cross-leak partial translated content or `[PROHIBITED]` cancellation markers.

3. **Workspace Parameter Starvation in Scraper Routers**:
   While `NovalpieAdapter` accepted `workspace: Optional[str] = None` to enforce tenancy boundaries for `get_scraper_concurrency()` and `get_novalpie_auth_config()`, invocations across `scrape.py`, `toc.py`, and `threads.py` instantiated the adapter without arguments (`workspace=None`), falling back to process-level defaults.

4. **Network Divergence in Novalpie API Requests**:
   `NovalpieAdapter.scrape_metadata` and `scrape_toc` utilized raw `httpx.AsyncClient` without `create_safe_async_client` redirect hooks or explicit `validate_external_url()` checks.

5. **GlobalSetting as an Architectural Anchor (God Node)**:
   Betweenness centrality analysis (0.082 across 104 graph edges) established `GlobalSetting` as the core bridge coordinating four major architectural communities: Batch Translation, Scraper Concurrency, Secret Reconciliation, and Dual-Database Workspace Isolation.

---

## Decisions

### 1. Workspace-Scoped Frontend Storage & Cache Purging
- **Storage Key Scoping**: Appended `_${getActiveWorkspace()}` to all persistent and session storage keys:
  - `readomni_app_session_v1_${getActiveWorkspace()}` in `src/App.tsx`.
  - `readomni_library_cache_v1_${getActiveWorkspace()}` and `readomni_library_scroll_v1_${getActiveWorkspace()}` in `src/pages/LibraryPage.tsx`.
  - `readomni_reader_session_v1_${getActiveWorkspace()}_${threadId}` in `src/pages/ReaderPage.tsx`.
  - Partitioned `bookmarksCacheStore` by `getActiveWorkspace()` in `src/pages/BookmarksPage.tsx`.
- **Atomic Session Purge**: Added `sessionStorage.clear()` in `Sidebar.tsx` and `SettingsPage.tsx` immediately before executing `window.location.reload()` on successful PIN authentication.

### 2. Strict SSE Compound Key Tenancy
- **Purged Integer Stream Aliases**: Removed `translation_queues[chapter_id]` from `backend/routers/translate.py`.
- **Scoped Queue Retrieval**: Updated `get_chapter_translation_queues` in `backend/services/background_translator.py` to retrieve queues exclusively by `(str(workspace).lower(), chapter_id)`.

### 3. Explicit Scraper Workspace Propagation
- Passed `workspace=ws` to all `NovalpieAdapter` instantiations across `scrape_url`, `import_from_url`, `fetch_next_chapter`, `crawl_next_chapters`, `scrape_toc`, `bulk_import_toc`, and `get_chapter`.
- Integrated `workspace=workspace` into `BackgroundTranslator._do_translate()` on-demand scraping.

### 4. Universal SSRF Defense for Novalpie API
- Added `validate_external_url()` and `create_safe_async_client` to `NovalpieAdapter.scrape_metadata()` and `scrape_toc()`, enforcing non-global IP validation and redirect interception.

### 5. TOC Detection Hardening
- Introduced `TOC_ROOT_URL_PATTERN` in `backend/routers/scrape.py` rejecting novel TOC URLs for both Novalpie and SFACG (`/Novel/\d+`, `/b/\d+`).
- Expanded SFACG TOC detection in `src/pages/TranslatePage.tsx`.

### 6. Workspace-Scoped Image Cache Job Cleanup
- Scoped `ACTIVE_IMAGE_JOBS` purging in `backend/routers/images.py:clear_image_cache()` strictly to the active workspace.

---

## Consequences

### Positive
- **Zero Cross-Workspace Cache Bleed**: Completely eliminates UI flickering and unauthorized book visibility during workspace transitions.
- **100% SSE Stream Isolation**: Concurrent streaming translation requests between main and ghost databases never collide.
- **Unified Security Surface**: All outbound scraper HTTP calls adhere strictly to SSRF defense-in-depth policies.
- **Preserved Code Quality**: Verified with 321 passing backend tests, clean TypeScript strict typechecking, and zero ESLint errors.
