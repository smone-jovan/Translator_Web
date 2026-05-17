# ADR-025: Scraped Author Metadata Integration

## Context & Problem Statement
When importing novels from external platforms (such as Novel Updates or SFACG), the scraper retrieved titles, genres, synopses, and covers, but lacked a formal mechanism to extract, store, and propagate the novel's author name. The `Thread` database table was already provisioned with an `author` column, but it remained unpopulated. Users had to manually input author names during book generation, and thread listings/dashboards fallback on static strings (e.g. `'Ancient Author'` or `'Unknown Author'`).

The objective was to parse and store the author's name automatically upon metadata scraping from both SFACG and Novel Updates sources, persist it in the SQLite database, expose it through Pydantic schemas, and display it beautifully within the frontend application.

## Proposed Decisions
1. **Automated Selector Extraction in Python Backend**:
   - **SFACG Selector**: Targeted the author using `.author-name`, `.author-info`, or fallback selector regex (such as `a[href*='/author/']`, `.novel-author`). Cleaned prefix text like `作者：` or `作者:`.
   - **Novel Updates Selector**: Targeted the author using `#showauthors` or `.author`, cleaning raw whitespace.
   
2. **Database & Schema Synchronization**:
   - Updated the SQLAlchemy `Thread` parsing logic in the `scrape_metadata` handler in `backend/routers/threads.py` to persist `thread.author`.
   - Updated the response dictionary from `scrape_metadata` to include the `author` field.
   - Modified `ThreadItemOut` schema in `threads.py` to include `author: Optional[str] = None`.
   - Mapped `author=t.author` in the `list_threads` endpoint (`/threads`) and `author=thread.author` in the `get_thread` endpoint (`/threads/{thread_id}`).

3. **Frontend Integration**:
   - Modified `src/components/ExportModal.tsx` to accept a new `threadAuthor` prop.
   - Initialized the export modal's `author` state with the thread's scraped author name (`threadAuthor || 'SMONE'`) to prevent hardcoded `'SMONE'` fallbacks when exporting EPUB/TXT files.
   - Updated `src/pages/ReaderPage.tsx` interface `ThreadDetail` and passed `threadAuthor={thread.author || undefined}` to the `ExportModal` invocation.

## Consequences
- **True Automated Metadata Extraction**: Users no longer need to look up or manually key in authors when importing novels from SFACG or Novel Updates.
- **Consistent Export Prefills**: Exporting novels automatically bundles the correct author in the EPUB metadata and TXT header.
- **Enriched UI Experience**: The Bookshelf, Recent Threads carousel, and details dashboards show the genuine literary creator instead of generic placeholders.
