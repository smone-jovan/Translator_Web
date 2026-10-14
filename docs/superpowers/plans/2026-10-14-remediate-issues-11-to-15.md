# Remediate Issues #11, #12, #13, #14, #15 & Global Documentation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve all 5 active project issues (#11 multi-tenancy ADR-118, #12 translation & glossary engine, #13 reader scroll physics & gesture guard, #14 model selection & polish & bookmark preservation, #15 database indexing & chapter switching perf & in-reader TOC drawer) plus #1 documentation enhancements, verify all quality gates, and commit via git/gh CLI.

**Architecture:** Layered remediation across backend SQLite indexing, SQLAlchemy query optimization, asyncio concurrency locks, and frontend React performance/gestures. Multi-tenancy invariants from ADR-118 are codified into centralized helpers in `backend/database.py` and `src/lib/api.ts` to guarantee zero state leakage between `main` and `ghost` workspaces.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, Python 3.13, React 19, TypeScript 5.8, Tailwind CSS, Lucide React, Pytest, ESLint.

**Spec:** GitHub Issues [#11](https://github.com/smone-jovan/Translator_Web/issues/11), [#12](https://github.com/smone-jovan/Translator_Web/issues/12), [#13](https://github.com/smone-jovan/Translator_Web/issues/13), [#14](https://github.com/smone-jovan/Translator_Web/issues/14), [#15](https://github.com/smone-jovan/Translator_Web/issues/15), and [#1](https://github.com/smone-jovan/Translator_Web/issues/1).

## Global Constraints
- Zero external package dependency changes without explicit user approval (no pip install or npm install).
- Frontend TypeScript strict mode with 0 errors (`npm run typecheck`).
- Frontend ESLint clean pass with 0 errors (`npm run lint`).
- Backend Pytest 100% passing across all test suites (`py -m pytest backend/tests/ -v`).
- Minimal, focused diffs matching surrounding code conventions.
- Never use raw integer IDs for in-memory compound keys (`make_workspace_key` is mandatory).
- All client-side storage keys touching library or chapter data must use `getWorkspaceStorageKey`.

## Review Focus
1. Dual-DB isolation: ensure ghost workspace data never leaks into main workspace caches or memory queues.
2. In-reader TOC drawer: drawer opens cleanly on mobile and desktop without disrupting ongoing reading scroll position.
3. Adjacent chapter prefetch: abort controller prevents race conditions when clicking Next/Prev repeatedly.
4. Soft-load batch translation: guarantees strict chapter order (1 -> 2 -> 3) with `concurrency_limit = 1`.
5. Bookmark preservation: deleting a chapter moves bookmark to nearest remaining chapter instead of dropping progress to 0%.

---

### Task 1: Codify ADR-118 & Graphify God Node Multi-Tenancy Helpers (Issue #11)

**Files:**
- Modify: `backend/database.py`
- Modify: `backend/services/background_translator.py`
- Modify: `backend/routers/translate.py`
- Modify: `backend/routers/batch.py`
- Modify: `backend/routers/images.py`
- Modify: `backend/services/image_cacher.py`
- Modify: `src/lib/api.ts`
- Modify: `src/App.tsx`
- Modify: `src/pages/LibraryPage.tsx`
- Modify: `src/components/Sidebar.tsx`
- Modify: `src/pages/SettingsPage.tsx`
- Modify: `CLAUDE.md`
- Modify: `docs/Handoff.md`
- Create: `backend/tests/test_workspace_tenancy_helpers.py`

**Interfaces:**
- Produces: `normalize_workspace(ws: Optional[Any]) -> str` in `backend/database.py`
- Produces: `make_workspace_key(workspace: Optional[Any], entity_id: int) -> tuple[str, int]` in `backend/database.py`
- Produces: `getWorkspaceStorageKey(baseKey: string, suffix?: string | number) -> string` in `src/lib/api.ts`
- Produces: `clearWorkspaceSessionCache() -> void` in `src/lib/api.ts`

- [ ] **Step 1: Write unit tests for tenancy helpers and CLAUDE.md invariants**
  Create `backend/tests/test_workspace_tenancy_helpers.py` testing `normalize_workspace`, `make_workspace_key`, and verifying that `CLAUDE.md` contains the ADR-118 directives.

- [ ] **Step 2: Add `normalize_workspace` and `make_workspace_key` to `backend/database.py`**
  Implement the two helpers in `backend/database.py` and export them.

- [ ] **Step 3: Update backend services and routers to use `make_workspace_key`**
  Update `background_translator.py`, `translate.py`, `batch.py`, `images.py`, and `image_cacher.py` to use `make_workspace_key(ws, id)`.

- [ ] **Step 4: Update `src/lib/api.ts` with `getWorkspaceStorageKey` and `clearWorkspaceSessionCache`**
  Export the helpers and update `App.tsx`, `LibraryPage.tsx`, `Sidebar.tsx`, and `SettingsPage.tsx`.

- [ ] **Step 5: Codify directives into `CLAUDE.md` and `docs/Handoff.md`**
  Add the ADR-118 Dual-Database Multi-Tenancy section to `CLAUDE.md` and Section Q to `docs/Handoff.md`.

- [ ] **Step 6: Run test suite to verify Task 1 passes**
  Run: `py -m pytest backend/tests/test_workspace_tenancy_helpers.py -v`

---

### Task 2: Core Translation, Glossary Engine & SSE Sync Remediations (Issue #12)

**Files:**
- Modify: `backend/services/context_engine.py`
- Modify: `backend/services/background_translator.py`
- Modify: `src/pages/ReaderPage.tsx`
- Create: `backend/tests/test_audit_stage5_issue12.py`

**Interfaces:**
- Produces: `ContextEngine._term_matches_text(original_term: str, text: str) -> bool`
- Produces: `get_workspace_translation_lock(workspace_id: str) -> asyncio.Lock`
- Produces: `get_thread_glossary_lock(workspace_id: str, thread_id: int) -> asyncio.Lock`

- [ ] **Step 1: Write test suite for Issue #12**
  Create `backend/tests/test_audit_stage5_issue12.py` covering `_term_matches_text`, Korean glossary pass source language detection, garbage lorebook re-validation, and workspace translation locks.

- [ ] **Step 2: Implement glossary matching & term filtering in `backend/services/context_engine.py`**
  Add `_term_matches_text`, update `build_translation_prompt` to prioritize terms appearing in the active chapter, re-validate `final_translated` in `auto_save_glossary`, and auto-detect `source_lang` in `extract_glossary_pass` and `extract_relationships_pass`.

- [ ] **Step 3: Update `backend/services/background_translator.py`**
  Implement `get_workspace_translation_lock` and `get_thread_glossary_lock`, rebuild `system_prompt` after pre-translation extraction, enforce `concurrency_limit = 1` for Soft Load, and emit `final_text` SSE event before `[DONE]`.

- [ ] **Step 4: Update `src/pages/ReaderPage.tsx` for SSE final text & workspace storage keys**
  Capture `parsed.final_text` in `handleTranslateChapter` to update translated text without reload, and scope auto-detect range storage keys with `getActiveWorkspace()`.

- [ ] **Step 5: Run tests to verify Task 2 passes**
  Run: `py -m pytest backend/tests/test_audit_stage5_issue12.py -v`

---

### Task 3: Reader Scroll Physics, Gesture Guards & Scroll Restoration (Issue #13)

**Files:**
- Modify: `src/components/reader/ChapterReader.tsx`
- Modify: `src/components/reader/SafeReaderImage.tsx`

**Interfaces:**
- Consumes: `getActiveWorkspace` from `@/lib/api`
- Produces: `syncScrollButtonVisibility(pct: number, isControlsShown: boolean) -> void`
- Produces: `evaluateDirectionalScroll(scrollTop: number, scrollHeight: number, delta: number) -> void`

- [ ] **Step 1: Implement cumulative directional scroll tracking in `ChapterReader.tsx`**
  Replace single-frame delta logic with cumulative delta tracking (`accumulatedDeltaRef`), hysteresis (+45px to hide, -75px to show), and a 380ms toggle cooldown.

- [ ] **Step 2: Implement pointer gesture recognizer & scroll cooldown**
  Add `handleReaderPointerDown`, `handleReaderPointerMove`, and filter accidental taps in `handleContentClick` (ignore if moving >8px, duration >260ms, scrolling in last 320ms, or in edge zones <12% and >85%).

- [ ] **Step 3: Fix scroll restoration dead-zones & scroll button visibility**
  Fix `hasSavedPosition` condition, cancel multi-stage timeouts when user interacts, block scroll persistence while `loadingContentRef.current === true`, and hide Scroll-to-Top button during immersive mode or <=8% scroll.

- [ ] **Step 4: Add `e.stopPropagation()` in `SafeReaderImage.tsx`**
  Update `handleRetry` so retrying image loads never propagates to toggle Reader navbar.

- [ ] **Step 5: Run frontend typecheck & lint**
  Run: `npm run typecheck && npm run lint`

---

### Task 4: Model Selection, Polish Titles, Error Handling & Bookmark Preservation (Issue #14)

**Files:**
- Modify: `src/pages/TranslatePage.tsx`
- Modify: `backend/services/ai/settings.py`
- Modify: `src/pages/ReaderPage.tsx`
- Modify: `src/components/BulkTranslateModal.tsx`
- Modify: `backend/routers/polish.py`
- Modify: `src/components/reader/ChapterListControls.tsx`
- Modify: `src/components/reader/ChapterGrid.tsx`
- Modify: `backend/routers/threads.py`
- Create: `backend/tests/test_audit_stage6_issue14.py`

**Interfaces:**
- Produces: `resolve_active_model(gs, requested_model)` guarding against sending LM Studio models to OpenRouter
- Produces: `delete_chapter(thread_id, chapter_id)` preserving `UserBookmark` to nearest chapter and re-sequencing

- [ ] **Step 1: Write test suite for Issue #14**
  Create `backend/tests/test_audit_stage6_issue14.py` testing `resolve_active_model` with OpenRouter, `delete_chapter` bookmark preservation, and Korean/Japanese polish detection.

- [ ] **Step 2: Fix Model Selection in `TranslatePage.tsx` and `BulkTranslateModal.tsx`**
  Synchronize `availableModels` with active provider, save chosen model to backend `/api/settings` and corresponding `localStorage` key, and fix the Active Model indicator in `BulkTranslateModal.tsx`.

- [ ] **Step 3: Fix OpenRouter model resolution & ReaderPage settings initialization**
  Update `backend/services/ai/settings.py` so `resolve_active_model` filters local model names for OpenRouter, and update `ReaderPage.tsx` to set `globalSettings.lm_model` based on active provider.

- [ ] **Step 4: Fix `backend/routers/polish.py` and CJK script detection in Reader UI**
  Pass `db_session=db` to `AIProviderFactory.get_provider`, use `contains_source_script` for novel title/synopsis, and update `isPolished` in `ChapterListControls.tsx` and `ChapterGrid.tsx` to include Korean and Japanese regex.

- [ ] **Step 5: Fix NDJSON error handling in `ReaderPage.tsx`**
  Parse lines in `handleTranslateTitles` and throw an error toast if `payload.status === 'error'`.

- [ ] **Step 6: Fix `delete_chapter` bookmark preservation in `threads.py` and cache cleanup in `ReaderPage.tsx`**
  In `delete_chapter`, reassign `bookmark.chapter_id` to `prev_ch or next_ch` before deleting chapter, re-sequence `ch.order`, and in `ReaderPage.tsx` remove session caches and adjust `selectedChapterIdx`.

- [ ] **Step 7: Run backend tests to verify Task 4 passes**
  Run: `py -m pytest backend/tests/test_audit_stage6_issue14.py -v`

---

### Task 5: Database Indexes, SQL Query Optimization & In-Reader Quick Chapter Drawer (Issue #15)

**Files:**
- Modify: `backend/database.py`
- Modify: `backend/routers/threads.py`
- Modify: `src/pages/ReaderPage.tsx`
- Modify: `src/components/reader/ChapterReader.tsx`
- Modify: `src/pages/LibraryPage.tsx`
- Modify: `src/components/reader/ChapterListControls.tsx`
- Modify: `src/components/reader/ChapterGrid.tsx`
- Create: `backend/tests/test_audit_stage7_issue15.py`

**Interfaces:**
- Produces: Composite index `idx_chapters_thread_order`, `idx_bookmarks_thread_id`, `idx_glossaries_thread_id` in `backend/database.py`
- Produces: `onSelectChapter?: (idx: number) => void` in `ChapterReaderProps`
- Produces: Quick Chapter Drawer (TOC slide-over) in `src/components/reader/ChapterReader.tsx`

- [ ] **Step 1: Write test suite for Issue #15**
  Create `backend/tests/test_audit_stage7_issue15.py` verifying that `list_threads` and `get_thread` do not load full chapter content text blobs into memory, and verifying SQLite indexes.

- [ ] **Step 2: Add database indexes in `backend/database.py`**
  Add `index=True` on `Chapter.thread_id`, `Chapter.order`, `Glossary.thread_id`, `UserBookmark.thread_id`, and composite indexes in `init_db()`.

- [ ] **Step 3: Eliminate full-text SQL scans in `backend/routers/threads.py`**
  Rewrite `list_threads` chapter stats query using SQL `case(...)` and `func.length` without loading `translated_content`, and rewrite `get_thread` chapter metadata query using `case(...)` and `char_len`.

- [ ] **Step 4: Implement In-Reader Quick Chapter Drawer (TOC slide-over) & line memoization in `ChapterReader.tsx`**
  Add `onSelectChapter` prop, `showChapterDrawer` state, search filtering, auto-scroll to active chapter, TOC drawer modal with `#order` badges, bottom bar button `${selectedChapterIdx + 1} / ${thread.chapters.length}`, and memoize `displayLines` and `originalLines`.

- [ ] **Step 5: Implement adjacent chapter prefetch, AbortController, and keep-previous-data in `ReaderPage.tsx`**
  Update chapter loading `useEffect` with `AbortController`, background prefetch for `N+1` and `N-1` into `sessionStorage`, smooth keep-previous-data, and pass `onSelectChapter` to `ChapterReader`.

- [ ] **Step 6: Implement Stale-While-Revalidate cache in `LibraryPage.tsx`**
  Initialize `threads` and `loading` from `sessionStorage.getItem('readomni_library_cache')` for instant library display.

- [ ] **Step 7: Optimize `ChapterListControls.tsx` and `ChapterGrid.tsx`**
  Wrap `allPolished` calculation in `useMemo` and add `content-visibility: auto` to chapter cards.

- [ ] **Step 8: Run backend tests to verify Task 5 passes**
  Run: `py -m pytest backend/tests/test_audit_stage7_issue15.py -v`

---

### Task 6: Global Documentation & Agent Playbook Enhancements (Issue #1)

**Files:**
- Create: `docs/overview.md`
- Modify: `docs/Handoff.md`
- Modify: `docs/SDLC.md`

- [ ] **Step 1: Create `docs/overview.md`**
  Document architecture overview, core data flows (Scrape -> Translate -> Reader), and key entry points for new engineers.

- [ ] **Step 2: Add "Agent Playbook" to `docs/Handoff.md`**
  Document agent operational invariants, safe scopes for refactoring, protected endpoints, and mandatory testing protocols.

- [ ] **Step 3: Add Categorized ADR Index to `docs/SDLC.md`**
  Group ADRs by domain (Batch Translation, Context Engine & Glossary, Reader & UI, Ghost Mode Dual-DB, Scraper & Security).

---

### Task 7: Full Verification & Quality Gates

- [ ] **Step 1: Run complete backend test suite**
  Run: `py -m pytest backend/tests/ -v` (expect all 321+ tests passing).

- [ ] **Step 2: Run frontend typecheck**
  Run: `npm run typecheck` (0 errors).

- [ ] **Step 3: Run frontend lint**
  Run: `npm run lint` (0 errors).

---

### Task 8: Commit & GitHub Issue Resolution via gh CLI

- [ ] **Step 1: Stage and commit all changes with conventional commit message**
  Create git commit referencing fixes for #11, #12, #13, #14, #15, and #1.

- [ ] **Step 2: Close GitHub issues #11, #12, #13, #14, and #15 with resolution comments**
  Use `gh issue close <number> --comment "<summary>"` for each resolved issue.
