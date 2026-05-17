# ADR-020: Novel Updates Metadata Scraping System with AI Title Cleanup

## Status
Implemented & Refined

## Date
2026-05-17

## Context
When reading and translating web novels on the platform, users need a way to fetch detailed metadata (such as Genres, Tags, Status, Country of Origin status, Synopses, and Cover Images) to enrich their personal library collection. 
Novel Updates (NU) is the premier indexing platform for web novels. To fetch the correct series page:
1. Search should be performed by the **Original Chinese Title** because English translated titles are highly volatile, whereas Chinese characters are exact and mapped directly on Novel Updates under "Associated Names".
2. Original titles supplied by users or scraped from sites are often noisy (e.g. containing descriptive tags in brackets or parentheses like `“我怎么可能是圣女？（无女主，变百，轻松）”`). We must isolate only the core original Chinese title of the book before searching.
3. This is a personal-use platform. Complex tracking details (like views, bookmarks count, since, and weekly release speed) are unnecessary and will be skipped. Only relevant metadata (Genre, Tags, Status, Status in COO, Synopsis, and optional Cover Image) will be scraped and stored.

## Decision
We will implement an automated metadata scraping and AI-assisted title cleaning pipeline.

### 1. Database Schema Extension
We will extend the `Thread` model in `backend/database.py` with the following nullable columns to store fetched metadata:
- `original_title` (`VARCHAR(500)`): Stores the cleaned original Chinese title.
- `genres` (`TEXT`): Stores comma-separated genres (e.g. `Action, Adventure, Harem`).
- `tags` (`TEXT`): Stores comma-separated descriptive tags (e.g. `Gender Bender, Cultivation`).
- `status` (`VARCHAR(100)`): Stores translation status (e.g. `Ongoing`, `Completed`).
- `status_coo` (`VARCHAR(200)`): Stores status in country of origin (e.g. `120 Chapters (Completed)`).
- `synopsis` (`TEXT`): Stores the clean book description/synopsis.

A database auto-migration routine will be injected into `init_db()` to dynamically check and run SQLite `ALTER TABLE threads ADD COLUMN ...` statements without losing user data.

### 2. Backend Scrape Metadata Route (`POST /api/threads/{thread_id}/scrape_metadata`)
A new REST endpoint in `backend/routers/threads.py` manages the pipeline:
1. **AI Title Cleansing**: Accepts an optional `original_title` string in the request body. If the string is noisy, it utilizes local AI to isolate the clean core Chinese characters.
2. **Multi-Stage Search Resolution (Search Engine First)**:
   - **Primary Stage (Search Engine)**: Queries Yahoo Search (`https://search.yahoo.com/search?p={title}+site:novelupdates.com`) using `curl_cffi` chrome impersonation to retrieve candidate links, bypassing Cloudflare scraping protections.
   - **Fallback Stage (Direct NU)**: If Yahoo Search yields no candidates, falls back to direct Novel Updates search (`https://www.novelupdates.com/?s={title}`).
3. **Deep Cross-Check Matcher**: Loops through the top candidates, fetches each detail page, and extracts the `official_title` and `associated_names` (from `#editassociated` splitting `<br>` lines).
   - **Normalized Similarity Match**: Uses substring matches and Chinese character intersection overlap (threshold >=50%) to verify that either the query title or raw title belongs to the Novel Updates entry. Matches successfully even if the main title is in English and query was original Chinese, and vice-versa.
   - **First Candidate Fallback**: If no candidate reaches the threshold, falls back to the first candidate to ensure maximum availability.
4. **Resilient & Precise Selector Detail Extraction**:
   - Official English title from `.seriestitlenu` or `.seriestitle span` or `.seriestitle`.
   - Cover Image URL from `.seriesimg img`.
   - Genres from `#seriesgenre a`.
   - Tags from `#showtags a` or `#seriestags a`.
   - Synopsis from `#editdescription`.
   - Status in COO from `#editstatus` (which contains volume and chapter lists, joined cleanly with commas).
   - Translation Status from `#showtranslated` or `#edittranslated` (e.g., "Completely Translated: No").
5. **Persistence**: Saves the fields to the SQL database and returns the populated payload.

### 3. Frontend Premium Interactive Modal (`ScrapeNUModal.tsx`)
A stunning glassmorphic modal will be built in React utilizing the existing theme-aware tokens:
- **Menu Item**: A new `"Scrape from NU"` item will be added to the three-dot library card context menu.
- **Form Controls**: Shows a text field pre-filled with the title or original title, allowing users to verify or input custom/messy original titles, along with a toggle option to `"Update Book Cover Image"`.
- **Elegant Loading State**: Shows a custom progress animation stating: *"Cleaning title with local AI & querying Novel Updates..."*.
- **Post-Scrape Preview**: After a successful scrape, displays the metadata beautifully (high-contrast genre/tag badges, status panels, cover thumbnail, and synopsis) inside the modal so the user gets immediate visual satisfaction before closing.

## Consequences
- Single-click metadata synchronization for any novel inside the user's library.
- Highly consistent naming and tag grouping inside the bookshelf.
- Automatically handles messy, parenthesized original titles via local LLM logic.
- Maintains lightweight design with absolute server portability.
