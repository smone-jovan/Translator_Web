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

- **Fix:** Per-request workspace determination via header/cookie, bukan global variable.

---

### C2. TypeScript `strict: true` Missing
- **File:** `tsconfig.app.json`, `tsconfig.node.json`
- **Problem:** `strict` defaults ke `false` — `strictNullChecks`, `noImplicitAny`, `strictFunctionTypes` semua OFF. TypeScript tidak catch null/undefined bugs.
- **Fix:** Add `"strict": true` ke kedua tsconfig.

---

### C3. Broken `typecheck` Script
- **File:** `package.json` (Line 10)
- **Problem:** `"typecheck": "tsc --noEmit"` tapi root tsconfig pakai project references (`"files": []`). Ini checks **zero files** dan selalu exit 0 — type errors lolos semua.
- **Fix:** Change to `"tsc -b --noEmit"`.

---

### C4. Path Traversal Edge Case (Windows)
- **File:** `backend/main.py` (Lines 62-72)
- **Problem:** `str.startswith()` path traversal check bisa di-bypass di Windows karena case insensitivity + path separator differences.

```python
# CURRENT — string prefix check (fragile on Windows)
if not file_path.startswith(safe_base):
    raise HTTPException(status_code=403)
```

- **Fix:** Use `pathlib.Path.resolve()` comparison:
```python
from pathlib import Path
safe_base = Path("uploads/images").resolve()
file_path = (safe_base / rest_of_path).resolve()
if safe_base not in file_path.parents and file_path != safe_base:
    raise HTTPException(status_code=403)
```

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
- **File:** `launcher.py` (Line 131)
- **Problem:** Spawns backend with `py` instead of `sys.executable`, bypasses virtualenv, breaks on macOS/Linux.
- **Fix:** `cmd = [sys.executable, "-u", "-m", "uvicorn", ...]`

---

### H7. Duplicated VIP Detection (3× copy-paste)
- **File:** `backend/routers/scrape.py` — lines 214, 494, 658
- **Problem:** Same VIP detection logic repeated 3 times.
- **Fix:** Extract `is_vip_chapter(url, title, markdown)` utility function.

---

### H8. `.env.example` Missing `OPENROUTER_API_KEY`
- **File:** `backend/.env.example`
- **Problem:** Code supports OpenRouter, but template doesn't list the key.
- **Fix:** Add `OPENROUTER_API_KEY=` to the example file.

---

### H9. `start_app.bat` Bypasses Virtualenv
- **File:** `start_app.bat`
- **Problem:** Hardcodes `py launcher.py`, no venv detection, window closes on crash.
- **Fix:** Add virtualenv fallback + error pause:
```bat
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launcher.py
) else if exist "backend\.venv\Scripts\python.exe" (
    "backend\.venv\Scripts\python.exe" launcher.py
) else (
    py launcher.py 2>nul || python launcher.py
)
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Launcher exited with error code %ERRORLEVEL%.
    pause
)
```

---

## 🟡 MEDIUM Issues

| # | Issue | File(s) |
|---|-------|---------|
| M1 | Missing Vite proxy → relies on wide CORS | `vite.config.ts` |
| M2 | No production chunk splitting → massive vendor bundle | `vite.config.ts` |
| M3 | `user-scalable=no` blocks accessibility zoom | `index.html` |
| M4 | Missing `.prettierignore` → formats Python/DB files | Project root |
| M5 | ESLint scans backend/ and temp dirs | `eslint.config.js` |
| M6 | `.gitignore` missing `uploads/`, `ecc-temp-dir/`, `.pytest_cache/` | `.gitignore` |
| M7 | Missing `useCallback`/`useMemo` in heavy components | `src/pages/ReaderPage.tsx`, `src/components/reader/ChapterReader.tsx` |
| M8 | Polling overlap — duplicate setInterval on remount | `src/components/BulkStatusCenter.tsx` |
| M9 | Silent API error swallowing (`.catch(() => {})`) | Multiple frontend files |
| M10 | Hardcoded ports in 12+ places in launcher | `launcher.py` |
| M11 | Banner shows "STARTING" then never auto-updates | `launcher.py` (Lines 211-214) |
| M12 | Giant single-file pages (SettingsPage=1561 lines, ContextLib=60KB) | `src/pages/SettingsPage.tsx`, `src/pages/ContextLibraryPage.tsx` |
| M13 | Manual `.env` parser breaks on quotes/escapes | `backend/services/ai/secrets.py` (Lines 68-83) |
| M14 | Missing `DOM.Iterable` in tsconfig lib | `tsconfig.app.json` (Line 5) |
| M15 | No format/lint-fix scripts in package.json | `package.json` |

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
- Fix path traversal (`main.py` → pathlib)
- Fix typecheck script (`package.json`)
- Fix launcher (`sys.executable`, port constants, banner refresh)
- Fix `start_app.bat` (venv detection + error pause)
- Update `.env.example`, `index.html`, `.gitignore`, `eslint.config.js`
- Create `.prettierignore`

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
