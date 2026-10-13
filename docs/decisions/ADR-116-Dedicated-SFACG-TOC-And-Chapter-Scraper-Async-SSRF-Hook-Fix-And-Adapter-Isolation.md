# ADR-116: Dedicated SFACG TOC & Chapter Scraper, Async SSRF Redirect Hook Bugfix, and Adapter UI Isolation

## Status
Accepted

## Date
2026-10-11

## Context
When attempting to import the Table of Contents (TOC) from SFACG (`https://book.sfacg.com/Novel/779207/MainIndex/`), several critical defects were discovered across backend networking, scraper adapter routing, and frontend bulk fetch UI:

1. **Fatal HTTP 502 in `create_safe_async_client` (`TypeError: object NoneType can't be used in 'await' expression`)**:
   In `backend/services/security.py`, `validate_redirect_response(response: httpx.Response)` was defined as a synchronous function (`def`). When registered in `create_safe_async_client` under `event_hooks["response"]`, `httpx.AsyncClient` executed `await hook(response)`. Because the synchronous hook returned `None`, `httpx` attempted to execute `await None`, raising `TypeError` and causing all outbound requests through `create_safe_async_client` (such as `/api/threads/scrape-toc` and `/api/scrape`) to fail with HTTP 502 Bad Gateway.

2. **Absence of Dedicated SFACG TOC & Chapter Scraper Adapter**:
   `SFACGAdapter` (`backend/services/scrapers/sfacg.py`) originally only implemented `scrape_metadata`. When users submitted SFACG URLs to `/api/threads/scrape-toc` or `/api/scrape`, requests fell back to generic heuristic parsing:
   - Novel titles were parsed directly from raw `<title>` tags, carrying noisy site suffixes (`我不想成为里世界女主角啊！目录列表 - 小说频道 - SF轻小说`).
   - A hardcoded filter `junk_paths = ["/stag/", "/cmts/", "/lcmt/", "/fans", "/vip/c/"]` rejected all `/vip/c/` links, dropping 121 VIP chapters out of 200 total chapters.
   - Chapter scraping lacked selector targeting (`#ChapterBody` vs ads/nav), and crawling `/crawl-next` could not resolve SFACG's *"下一章"* navigation links.

3. **Leaked Adapter Controls in Bulk Fetch Modal**:
   In `src/components/BulkFetchModal.tsx`, the `Novalpie: Mode Akun (720h/60d)` / `Novalpie: Mode Tamu` button was rendered unconditionally in the modal footer for all novels, giving the false impression that Novalpie credentials or browser engines were required or active when interacting with SFACG novels. Furthermore, crawler retry log messages were hardcoded to announce *"mencoba ulang Playwright/Browser..."* even for non-browser HTTP adapters.

---

## Decisions

### 1. Fix Asynchronous Response Event Hook in `create_safe_async_client`
- Converted `validate_redirect_response` in `backend/services/security.py` to `async def validate_redirect_response(response: httpx.Response) -> None:`.
- Verified that `httpx.AsyncClient` awaits the returned coroutine successfully on both non-redirect 200 responses and redirect responses, retaining full SSRF protection against non-global / internal IP redirects without runtime exceptions.
- Added automated regression unit tests in `backend/tests/test_services/test_security_ssrf.py`.

### 2. Implement Pure-HTTP SFACG Dedicated Adapter (`SFACGAdapter`)
In `backend/services/scrapers/sfacg.py`, implemented high-performance, non-browser methods:
- **`extract_novel_id(query)`**: Extracts integer novel IDs from URLs (`/Novel/779207/MainIndex/`, `/Novel/779207/`, `/b/779207/`) or raw ID strings.
- **`scrape_toc(query)`**: Fetches `https://book.sfacg.com/Novel/{novel_id}/MainIndex/` using `create_safe_async_client`, extracts the clean novel title from `<h1 class="story-title">`, and parses all chapters (free and VIP) from `.catalog-list li a`. Strips inline `.tag` and `.badge` tags so chapter and novel titles remain clean Mandarin Hanzi.
- **`scrape_chapter_content(url)`**: Extracts `#ChapterBody` directly by paragraphs `<p>` into clean Markdown. Detects VIP locked preview content and marks appropriate placeholder text. Runs in <0.5 seconds per chapter without starting Chromium or Playwright.
- **`get_next_chapter(current_url)`**: Resolves *"下一章"* links for chained web crawler navigation.

### 3. Strict Domain Routing & Security Hardening
- Replaced loose substring checks (`"sfacg.com" in url`) with `is_domain(url, "sfacg.com")` using exact hostname and subdomain matching in `backend/routers/toc.py`, `backend/routers/scrape.py`, and `backend/routers/threads.py`.
- Re-raised `HTTPException` in router adapters so SSRF rejection codes (400 Bad Request) are preserved rather than masked as generic 502 Bad Gateway errors.
- Added SSRF validation on `req.base_url` in `bulk_import_toc`.

### 4. Isolate Novalpie Settings to Novalpie Threads in `BulkFetchModal.tsx`
- Added `isNovalpie` detection in `src/components/BulkFetchModal.tsx` inspecting `chapters` and `anchorChapter.source_url`.
- Conditionally rendered the Novalpie account toggle button only when `isNovalpie === true`.
- Updated crawler retry logging to display adapter-appropriate descriptions (`"Playwright/Browser"` for Novalpie, `"Network/HTTP"` for SFACG and standard sources).

---

## Consequences

### Positive
- **100% Chapter Completeness**: Importing TOC from `https://book.sfacg.com/Novel/779207/MainIndex/` now extracts all 200 chapters with clean titles (e.g. `第一章 为了帝皇！`) instead of 79 chapters with noisy site suffixes.
- **Zero Browser Overhead for SFACG**: Chapter reading, on-demand reader fetching, and chained crawling execute via fast async HTTP (<0.5s/chapter) without Playwright.
- **Zero Runtime 502 Errors**: Fixed the coroutine hook defect in `create_safe_async_client`, restoring stability across all endpoints using safe HTTP clients.
- **UI Cleanliness**: The Bulk Fetch modal displays source-specific controls cleanly without Novalpie bleed-through.

### Verification
- **Backend Tests**: 289 passed in `backend/tests/` (including 8 new tests in `test_sfacg_scraper.py` and `test_security_ssrf.py`).
- **Frontend Typecheck & Lint**: Passed with 0 errors (`npm run typecheck`, `npm run lint`).
