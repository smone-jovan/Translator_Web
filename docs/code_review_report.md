# 🔍 ReadOmni AI — Full Code Review Report

**Date:** 2026-08-15  
**Reviewed by:** Antigravity AI (3 parallel reviewers + direct analysis)  
**Scope:** Backend (Python/FastAPI), Frontend (React/TypeScript), Config/Build

---

## Executive Summary

Project ini secara keseluruhan **sudah solid** — arsitekturnya clean (FastAPI + React 19 + SQLite WAL), fitur-fiturnya lengkap dan production-worthy (batch translation, glossary injection, auto-continue, key rotation, fidelity checking). Launcher CLI-nya juga impressive.

**Tapi** ada beberapa masalah serius yang perlu dibenerin, terutama di area thread safety, type safety, dan build configuration.

| Severity | Count | Impact |
|----------|-------|--------|
| 🔴 CRITICAL | 4 | Data corruption, security vulnerabilities, silent type errors |
| 🟠 HIGH | 9 | Runtime crashes, resource leaks, broken tooling |
| 🟡 MEDIUM | 15 | Degraded UX, performance issues, maintenance burden |
| 🔵 LOW | 10 | Code style, minor optimizations |

---

## 🔴 CRITICAL Issues

### C1. Thread-Unsafe Database Workspace Switching
- **Status:** ⏳ **PENDING (Patch B - Architecture Design Ready)**
- **File:** `backend/database.py` (Lines 37-43)
- **Problem:** `ACTIVE_WORKSPACE` adalah global variable yang menentukan database mana yang dipakai. Di FastAPI yang concurrent, kalau satu request switch workspace, SEMUA request ikut berubah — ini bisa menyebabkan data dari workspace `main` masuk ke `ghost` dan sebaliknya.

```python
# CURRENT (BROKEN) — global state shared across all requests
ACTIVE_WORKSPACE = "main"

def SessionLocal():
    if ACTIVE_WORKSPACE == "ghost":
        return SessionLocalGhost()
    return SessionLocalMain()
```

- **Fix Plan:** Stateless per-request workspace determination via header `X-Workspace` + explicit `workspace` context pada `BackgroundTranslator`.

---

### C2. TypeScript `strict: true` Missing
- **Status:** ✅ **RESOLVED in Patch A (Commit `39504d2`)**
- **File:** `tsconfig.app.json`, `tsconfig.node.json`
- **Solution:** Menambahkan `"strict": true` pada kedua tsconfig dan `"DOM.Iterable"` pada `tsconfig.app.json`. Terverifikasi 100% lulus `tsc -b --noEmit` dengan 0 error.

---

### C3. Broken `typecheck` Script
- **Status:** ✅ **RESOLVED in Patch A (Commit `39504d2`)**
- **File:** `package.json` (Line 10)
- **Solution:** Mengubah script menjadi `"typecheck": "tsc -b --noEmit"` sehingga mengevaluasi seluruh *project references*.

---

### C4. Path Traversal Edge Case (Windows)
- **Status:** ✅ **RESOLVED in Patch A (Commit `39504d2`)**
- **Files:** `backend/main.py` (Lines 62-85), `backend/routers/export.py` (Lines 170-185)
- **Solution:** Mengganti string `startswith()` dengan canonical containment `pathlib.Path.resolve()` dan `candidate.is_relative_to(base_dir)`. Dilengkapi dengan 8 unit regression tests di `backend/tests/test_routers/test_security_path_traversal.py`.

---

## 🟠 HIGH Issues

### H1. Sync DB Calls Blocking Async Event Loop
- **Files:** All routers + `backend/services/background_translator.py`
- **Problem:** Synchronous SQLAlchemy di `async def` routes blocks the entire event loop. Saat DB query jalan, semua request lain harus nunggu.
- **Fix:** Wrap sync DB ops dalam `asyncio.to_thread()` atau migrate ke SQLAlchemy AsyncSession.

---

### H2. Monster Migration Function (240+ lines)
- **File:** `backend/database.py` (Lines 212-454)
- **Problem:** `init_db()` berisi 240+ baris manual `ALTER TABLE` yang repetitif. Setiap kolom baru butuh copy-paste pattern yang sama.
- **Fix:** Refactor ke loop-based migration atau adopt Alembic.

---

### H3. Monolithic `_do_translate()` (360+ lines)
- **File:** `backend/services/background_translator.py` (Lines 168-530)
- **Problem:** Single method does: DB fetch, web scraping, prompt assembly, lock management, SSE streaming, loop detection, image protection, fidelity checking, and error handling.
- **Fix:** Break into smaller functions: `_prepare_chapter()`, `_stream_translation()`, `_verify_and_save()`.

---

### H4. Pervasive `any` Types in Frontend
- **Files:** `src/components/BulkTranslateModal.tsx`, `src/components/BulkFetchModal.tsx`, `src/components/ScrapeNUModal.tsx`
- **Problem:** Unsafe `any` casts dan `@ts-ignore` throughout. TypeScript protections defeated.
- **Fix:** Define proper interfaces untuk API responses dan component props.

---

### H5. Resource Leaks — EventSource & Object URLs
- **Files:** `src/components/ExportModal.tsx`, `src/components/BulkFetchModal.tsx`
- **Problem:** `URL.createObjectURL()` never revoked; EventSource connections not closed on unmount.
- **Fix:** Add cleanup in `useEffect` return dan revoke Object URLs after use.

---

### H6. Launcher Uses `py` Instead of `sys.executable`
- **Status:** ✅ **VERIFIED RESOLVED**
- **File:** `launcher.py` (Line 194)
- **Status Detail:** Launcher telah memanggil backend menggunakan `sys.executable` (`[sys.executable, "-u", "-m", "uvicorn", ...]`), menjaga isolasi virtualenv.

---

### H7. Duplicated VIP Detection (3× copy-paste)
- **Status:** ⏳ **PENDING (Phase 2)**
- **File:** `backend/routers/scrape.py` — lines 214, 494, 658
- **Problem:** Same VIP detection logic repeated 3 times.
- **Fix:** Extract `is_vip_chapter(url, title, markdown)` utility function.

---

### H8. `.env.example` Missing `OPENROUTER_API_KEY`
- **Status:** ✅ **RESOLVED in Patch A (Commit `39504d2`)**
- **File:** `backend/.env.example`
- **Solution:** Menambahkan entri template `OPENROUTER_API_KEY=` pada `backend/.env.example`.

---

### H9. `start_app.bat` Bypasses Virtualenv
- **Status:** ✅ **VERIFIED RESOLVED**
- **File:** `start_app.bat`
- **Status Detail:** `start_app.bat` telah dilengkapi hierarki deteksi `.venv`, `venv`, `backend/.venv`, dan `backend/venv` serta pause penanganan error code.

---

## 🟡 MEDIUM Issues

| # | Issue | File(s) | Status |
|---|-------|---------|:------:|
| M1 | Missing Vite proxy → relies on wide CORS | `vite.config.ts` | ⏳ Pending Phase 3 |
| M2 | No production chunk splitting → massive vendor bundle | `vite.config.ts` | ⏳ Pending Phase 3 |
| M3 | `user-scalable=no` blocks accessibility zoom | `index.html` | ⏳ Pending Phase 3 |
| M4 | Missing `.prettierignore` → formats Python/DB files | Project root | ✅ **RESOLVED (Patch A)** |
| M5 | ESLint scans backend/ and temp dirs | `eslint.config.js` | ✅ **RESOLVED (Patch A)** |
| M6 | `.gitignore` missing `uploads/`, `ecc-temp-dir/`, `.pytest_cache/` | `.gitignore` | ⏳ Pending Phase 1 Clean |
| M7 | Missing `useCallback`/`useMemo` in heavy components | `src/pages/ReaderPage.tsx`, `src/components/reader/ChapterReader.tsx` | ⏳ Pending Phase 3 |
| M8 | Polling overlap — duplicate setInterval on remount | `src/components/BulkStatusCenter.tsx` | ⏳ Pending Phase 3 |
| M9 | Silent API error swallowing (`.catch(() => {})`) | Multiple frontend files | ⏳ Pending Phase 3 |
| M10 | Hardcoded ports in 12+ places in launcher | `launcher.py` | ⏳ Pending Phase 4 |
| M11 | Banner shows "STARTING" then never auto-updates | `launcher.py` (Lines 211-214) | ⏳ Pending Phase 4 |
| M12 | Giant single-file pages (SettingsPage=1561 lines, ContextLib=60KB) | `src/pages/SettingsPage.tsx`, `src/pages/ContextLibraryPage.tsx` | ⏳ Pending Phase 4 |
| M13 | Manual `.env` parser breaks on quotes/escapes | `backend/services/ai/secrets.py` (Lines 68-83) | ⏳ Pending Phase 2 |
| M14 | Missing `DOM.Iterable` in tsconfig lib | `tsconfig.app.json` (Line 5) | ✅ **RESOLVED (Patch A)** |
| M15 | No format/lint-fix scripts in package.json | `package.json` | ⏳ Pending |

---

## 🔵 LOW Issues

| # | Issue |
|---|-------|
| L1 | Inconsistent naming (mixed Indonesian/English in comments/variables) |
| L2 | `_pacing_lock` created via try/except instead of module-level init |
| L3 | `print()` statements everywhere instead of structured logging |
| L4 | `re.compile()` called inside hot loops (should be module-level constants) |
| L5 | MUI + Tailwind + Radix UI + shadcn all in one project — heavy dependency overlap |
| L6 | Browser globals applied to Node config files in eslint |
| L7 | `@types/d3` and `@tailwindcss/vite` in runtime dependencies (should be devDependencies) |
| L8 | Redundant `postcss` + `autoprefixer` with Tailwind v4 |
| L9 | Redundant/duplicate `.gitignore` entries |
| L10 | Generic `<title>translator-web</title>` instead of "ReadOmni AI" |

---

## Recommended Fix Phases

### Phase 1: Critical + Quick Wins
- [x] Fix path traversal (`backend/main.py`, `backend/routers/export.py` → `pathlib.Path.resolve()`) ✅ *(Commit `39504d2`)*
- [x] Fix typecheck script (`package.json` → `tsc -b --noEmit`) ✅ *(Commit `39504d2`)*
- [x] Enable TypeScript strict mode & `DOM.Iterable` (`tsconfig.app.json`, `tsconfig.node.json`) ✅ *(Commit `39504d2`)*
- [x] Create `.prettierignore` ✅ *(Commit `39504d2`)*
- [x] Scope ESLint ignores (`eslint.config.js`) ✅ *(Commit `39504d2`)*
- [x] Update `.env.example` with `OPENROUTER_API_KEY` ✅ *(Commit `39504d2`)*
- [x] Verify launcher (`sys.executable`) & `start_app.bat` (venv detection) ✅
- [ ] Database Workspace Isolation & Concurrency Safety ⏳ *(Patch B - Design Ready)*

### Phase 2: Backend Code Quality
- Refactor `init_db()` migration (240 → ~30 lines)
- Extract `is_vip_chapter()` utility
- Refactor `_do_translate()` into smaller functions
- Fix `_pacing_lock` module-level init

### Phase 3: Frontend Fixes
- Fix resource leaks (Object URL, EventSource cleanup)
- Add error toast for silent API failures
- Fix polling overlap in BulkStatusCenter
- Add production chunk splitting in Vite

### Phase 4: Nice-to-Haves
- Structured logging
- Client-side router (react-router)
- Break giant page components
- Remove redundant dependencies
- TypeScript strict mode (generates many fixable errors)

---

## Verification

```bash
# Backend tests
cd backend && py -m pytest tests/ -v

# Frontend checks
npm run lint && npm run typecheck && npm run build

# Manual
# - Start via start_app.bat, verify all features
# - Test Ghost Mode workspace switch
# - Test batch translation
# - Verify mobile access via LAN
```
