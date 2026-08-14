# ADR-093: Chained Bulk Web Chapter Crawler Integration

## Status
Accepted

## Context
In [ADR-057](file:///d:/code_xI/Translator_Web/docs/decisions/ADR-057-Auto-Fetch-Next-Web-Chapter.md), we introduced on-demand scraping of the next single chapter when reaching the end of the reader. In [ADR-061](file:///d:/code_xI/Translator_Web/docs/decisions/ADR-061-Bulk-Fetch-and-RPM-Key-Scaling.md), we added Bulk Fetch for chapters already present in the database that had empty content.
However, when users reached the end of their currently imported chapters and wanted to fetch a batch of new chapters (e.g. 10 to 50 chapters) directly from the web source, they had to click the single-chapter "Fetch Next Web Chapter" button repeatedly.

## Decision
We implemented a full chained web chapter crawler with live SSE progress:
1. **Backend Route (`POST /api/threads/{thread_id}/crawl-next`)**:
   - Accepts `start_chapter_id` and `count` (1 to 50 chapters).
   - Resolves anchor chapter (defaults to latest chapter in thread with a `source_url`).
   - Recursively discovers `next_url` links (`下一章`, `next`, `下一页`, etc.).
   - Downloads HTML, cleans & converts to markdown via `html_to_markdown()`.
   - Detects VIP paywalls and stops chained crawling gracefully if VIP chapters are reached.
   - Saves new chapters sequentially into SQLite database with `translation_status="idle"` or `"vip"`.
   - Uses `StreamingResponse` (SSE) to push real-time crawl progress events (`start`, `progress`, `complete`, `error`).
   - Injects random anti-bot delays (`asyncio.sleep(random.uniform(1.2, 2.2))`) between scrapes to prevent IP bans.

2. **Frontend UI Enhancements**:
   - **Dual-Mode [BulkFetchModal.tsx](file:///d:/code_xI/Translator_Web/src/components/BulkFetchModal.tsx)**: Provides two tabs:
     - `📥 Fill Missing Content`: Downloads raw text for 0-word chapters already in the DB.
     - `🌐 Crawl Next Web Chapters`: Chains forward $N$ chapters from the latest web source URL with slider and live progress bar.
   - **Reader Quick Action ([ChapterReader.tsx](file:///d:/code_xI/Translator_Web/src/components/reader/ChapterReader.tsx))**: Added a `⚡ Bulk Crawl (+10)` button alongside `Fetch Next Web Chapter` when the user reaches the end of the novel.
   - **Novel Header Button ([NovelHeader.tsx](file:///d:/code_xI/Translator_Web/src/components/reader/NovelHeader.tsx))**: Displays Bulk Fetch whenever thread or any of its chapters contains web source URLs.

## Consequences
- **Positive**: Eliminates repetitive manual clicking; users can easily fetch dozens of new chapters with 1 click.
- **Positive**: Real-time SSE feedback keeps users informed of exactly which chapters are being scraped and saved.
- **Positive**: Built-in anti-bot delay ensures safety against scraper rate-limiting.
