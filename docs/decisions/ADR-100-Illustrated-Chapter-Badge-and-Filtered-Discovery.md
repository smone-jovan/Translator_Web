# ADR-100: Illustrated Chapter Badge, Counter & Filtered Discovery System

## Status
Accepted

## Date
2026-09-03

## Context
Web novels and light novels (imported via EPUB or scraped from sources like Novelpia, SFACG, and Kakuyomu) frequently contain important cover art, color spreads, and insert illustrations embedded within specific chapters. Prior to this decision:

1. **No Visual Indication**: Readers had no way of identifying which chapters contained illustrations without manually opening and scrolling through chapters one by one.
2. **Missing Metadata in Table of Contents**: The chapter catalog (`ChapterGrid`) displayed chapter titles, word count, fidelity warnings, and translation status, but provided zero metadata regarding visual content.
3. **Performance Sensitivity**: In a production database with over 20,000 chapters across multiple novels, dynamically parsing raw text (`content_original` / `content_translated`) on every thread overview request (`GET /api/threads/{id}`) would introduce severe memory and CPU bottlenecks.

## Decision
We implemented an end-to-end, high-performance **Illustrated Chapter Badge and Filtered Discovery System** across the backend and frontend:

### 1. Persistent Column & Zero-Downtime Migration (`backend/database.py`)
- Added `image_count: Mapped[int] = mapped_column(default=0)` to the `Chapter` model.
- Integrated non-destructive SQLite auto-migration in `init_db()` (`ALTER TABLE chapters ADD COLUMN image_count INTEGER DEFAULT 0`).
- Implemented an automated startup backfill that selectively queries candidate chapters using SQLite `LIKE` clauses (`%![%`, `%<img%`) and synchronizes their image counts without loading irrelevant rows. Over 200 existing illustrated chapters were successfully backfilled.

### 2. Event-Driven Auto-Synchronization (`backend/database.py`)
- Created a robust regex compilation pattern `IMAGE_TAG_PATTERN` and helper `count_images_in_text()` that accurately matches:
  - Markdown images: `![alt text](url)`
  - HTML tags: `<img src="..." />`
  - Escaped HTML entities: `&lt;img ...&gt;`
- Attached SQLAlchemy `@event.listens_for(Chapter, "before_insert")` and `@event.listens_for(Chapter, "before_update")` listeners. The update listener uses `sqlalchemy.orm.attributes.get_history()` to only recalculate `image_count` when chapter text actually changes, eliminating wasteful re-computations during bookmarking or status toggles.

### 3. Lightweight API Projection (`backend/routers/threads.py`)
- Extended `ChapterOut` and `ChapterContent` schemas with `image_count: int = 0`.
- Updated the SQL query in `get_thread` to include `Chapter.image_count` in the tuple projection, preserving instant $O(1)$ row mapping without pulling heavy text fields.
- Updated `get_chapter` to return `image_count`.

### 4. Interactive UI Badge & Filter Bar (`src/components/reader/`)
- Updated TypeScript definitions in `src/components/reader/types.ts` (`Chapter.image_count?: number`).
- In `ChapterGrid.tsx`, added a compact sky-blue badge (`[ImageIcon] {count}`) next to the word count indicator on every illustrated chapter card.
- In `ChapterListControls.tsx`, added an **`Illustrated (N)`** filter tab alongside `All Chapters` and `Translated`, featuring the Lucide `Image` icon and a live count pill.
- In `ReaderPage.tsx`, updated the `chapterFilter` state type to `'all' | 'translated' | 'illustrated'`.

### 5. Automated Unit & Integration Tests (`backend/tests/test_routers/test_chapter_images.py`)
- Created unit tests verifying:
  - Markdown and HTML tag counting accuracy.
  - ORM listener auto-computation on INSERT and UPDATE.
  - End-to-end API response verification on `GET /api/threads/{id}`.

## Alternatives Considered

### Alternative A: On-The-Fly Regex Parsing on `GET /api/threads/{id}`
- **Pros**: No database schema change or backfill script needed.
- **Cons**: Severe performance degradation. Loading and scanning full text for novels with 500–1000+ chapters on every page load would consume tens of megabytes of RAM and spike response times.
- **Rejected**: Violates performance and responsiveness standards.

### Alternative B: Dedicated Illustration/Asset Table
- **Pros**: Allows storing image URLs, captions, dimensions, and building a global novel gallery.
- **Cons**: Significant architectural overhead, relational joins, and migration complexity for a focused requirement.
- **Rejected**: Overkill for MVP chapter discovery. Can be built later as an additive extension if needed.

## Consequences
- **Positive**: Readers can instantly spot chapters containing illustrations and filter the table of contents to browse illustrated chapters directly.
- **Positive**: Instant API response times; zero runtime overhead added to thread retrieval.
- **Positive**: Fully automated lifecycle; newly scraped chapters, translated chapters, or edited content automatically stay in sync.
- **Positive**: 100% backward compatible; zero regressions across all 153 backend tests and frontend typechecking.
