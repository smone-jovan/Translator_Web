# ADR-098: Dedicated Novalpie.cc Novel Metadata and Chapter Crawler Adapter

## Status
Accepted

## Date
2026-08-31

## Context
ReadOmni AI previously supported metadata scraping and TOC extraction primarily for Novel Updates and SFACG (SF轻小说), alongside generic heuristic HTML scrapers for static web pages.

When users attempted to import Korean web novel raws/MTLs from `https://novalpie.cc/`, traditional HTML scrapers (BeautifulSoup parsing of `<a>` anchors) failed because `novalpie.cc` is a modern **Nuxt.js 3 / Vue SPA (Single Page Application)** where page structures are dynamically rendered on the client. Server-side DOM parsing returns an empty shell with no readable content.

Upon reverse engineering the Nuxt bundle assets of `novalpie.cc`, we discovered that the site exposes internal REST APIs under `https://novalpie.cc/api/`:
- `GET /api/novels/{novel_id}/detail` → title, cover URL (`images.novelpia.com`), synopsis, author, genre tags, and status.
- `GET /api/novels/{novel_id}/chapters` → structured array of chapter objects with ID, chapter number, title, and VIP lock status.
- `GET /api/novels/{novel_id}/chapters/{chapter_id}` → raw chapter content and body text.

The `scrape_toc()` method consumes both the `/detail` endpoint (for novel title) and the `/chapters` endpoint (for the chapter list) in sequence.

## Alternatives Considered

| Option | Reason Rejected |
|---|---|
| **Playwright-only from the start** | Too slow and resource-heavy for simple metadata/TOC fetches. The REST API is fast and always available for non-Cloudflare-blocked requests. |
| **Generic BeautifulSoup heuristic scraper** | Returns empty HTML shell on Nuxt SPA. Zero content without JS execution. |
| **Pyppeteer (Chrome DevTools Protocol wrapper)** | Unmaintained since 2022, poor Windows asyncio compatibility. |

## Decision
We implemented a dedicated `NovalpieAdapter` adhering to the `BaseScraperAdapter` port architecture (established in [ADR-029](./ADR-029-Swappable-Scrapers-and-LLM-Adapters.md)):

### 1. `NovalpieAdapter` — `backend/services/scrapers/novalpie.py`
- **URL & ID extraction** — supports `https://novalpie.cc/book/{id}`, `/novel/{id}`, `/read/{id}/{chapter_id}`, direct numeric IDs, and a fallback `re.search(r'(\d+)')` heuristic.
- **`scrape_metadata(query)`** — Direct JSON ingestion via `/api/novels/{id}/detail`. Key field mappings confirmed via live API inspection:
  - `title` → Chinese/translated title (e.g. `成为赛博朋克中的龙`)
  - `trueName` → `original_title`, the Korean source title from novelpia.com (e.g. `사이버펑크 속 드래곤이 되었다`)
  - `authorName` → author (e.g. `짱빠른토끼`)
  - `spans` → status badge text; `"完结"` in spans maps to `"Completed"`, otherwise `"Ongoing"` (there is no dedicated `status` field in the API)
  - `photoTrueUrl` → preferred high-res cover (over `photoUrl` which is a thumbnail)
- **`scrape_toc(query)`** — Calls `/api/novels/{id}/detail` (for title) then `/api/novels/{id}/chapters` (for chapter list). Each chapter entry carries `id`, `chapterNumber`, `title`, `trueId` (novelpia.com source ID), `wordCount`, and `is_vip` fields.
  > **Note on duplicate titles:** The `/chapters` API may return multiple chapters with identical titles (e.g. 3× `"米可"`, 3× `"最初的魔法"`). These are **not crawler bugs** — they are distinct chapters with unique `chapterNumber` values and unique `id`s from novalpie.cc's own data, reflecting chapters inserted mid-series from the source.
- **`scrape_chapter_content(url)`** — Attempts `GET /api/novels/{id}/chapters/{chapter_id}` first. **This endpoint currently returns `404 "API endpoint not implemented in Laravel yet."` for all chapters.** Therefore chapter content fetch **always falls through to the Playwright headless browser fallback** defined in [ADR-099](./ADR-099-Novalpie-Headless-Fallback-and-Cloudflare-Bypass.md). The API-first code path is retained as future-proofing for when novalpie.cc implements this endpoint.

### 2. Integration into Core Scraper Engine & Routers
- **`engine.py`**: Registered `"novalpie"` in adapter map and added auto-routing when URLs match `novalpie.cc`.
- **`toc.py`**: `/api/threads/scrape-toc` routes `novalpie.cc` URLs directly to `NovalpieAdapter.scrape_toc`, bypassing empty HTML DOM parsing. `/api/threads/bulk-import-toc` auto-populates metadata upon thread creation.
- **`scrape.py`** & **`threads.py`**: `/api/scrape`, `/api/threads/import-url`, and on-demand reader fetching utilize `NovalpieAdapter.scrape_chapter_content`.

### 3. Frontend UI Enhancements
- **`ScrapeNUModal.tsx`**: Added Novalpie (`novalpie`) as a 3rd source tab alongside Novel Updates and SFACG, with auto-detection from thread URL/title.

## Consequences

### Positive
- 1-click importing of novels from `novalpie.cc` now works reliably, extracting high-resolution covers, accurate TOCs, and clean markdown chapters.
- Zero performance overhead on server-side DOM parsing since data is ingested directly via lightweight JSON responses.
- Full test suite coverage in `backend/tests/test_services/test_novalpie_scraper.py` (132/132 tests passing).

### Negative / Trade-offs
- **Undocumented API dependency** — The `/api/novels/` endpoints are internal and undocumented. A Nuxt bundle update or backend restructure at novalpie.cc could silently break all scraping without any public deprecation notice.
- **No search capability** — Unlike Novel Updates or SFACG, `novalpie.cc` exposes no search API. Users must supply the novel URL or numeric ID directly; title-based lookup is not supported.
- **Cloudflare Turnstile exposure** — Chapter content fetches (not metadata/TOC) are gated by Cloudflare Turnstile on some requests, requiring the Playwright headless fallback defined in ADR-099. This adds ~150MB Chromium installation as an optional runtime dependency.

## Related ADRs
- [ADR-029 — Swappable Scrapers and LLM Provider Adapters](./ADR-029-Swappable-Scrapers-and-LLM-Adapters.md) ← defines the `BaseScraperAdapter` port this adapter implements
- [ADR-059 — Novel Updates Cloudflare Bypass via curl-cffi](./ADR-059-Novel-Updates-Cloudflare-Bypass-via-curl-cffi.md) ← prior art for Cloudflare bypass strategy
- [ADR-099 — Novalpie Headless Browser Fallback and Cloudflare Bypass](./ADR-099-Novalpie-Headless-Fallback-and-Cloudflare-Bypass.md) ← supersedes chapter-fetch reliability issues discovered post-deployment
