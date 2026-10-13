# ADR-095: Library Reading Status Filters & Smart Sorting

## Status
Accepted

## Date
2026-08-27

## Context
As users built large collections of translated and imported web novels (EPUBs, URL scrapers, SFACG), a critical UX discovery bottleneck emerged on the main **Library** dashboard:

1. **New Imports Buried Active Reads**: All threads were returned and displayed ordered strictly by their creation/import timestamp (`created_at DESC`). Consequently, whenever a user imported a new web novel or scraped chapters, that new book immediately pushed their actively read novels down into the grid.
2. **Carousel Misalignment**: The *"Continue Reading"* carousel sorted active books by `created_at` instead of the actual timestamp when the user last read them (`last_read_at`), causing newly created unread or low-progress books to displace long-read novels.
3. **No Reading Lifecycle Segmentation**: Users had no quick way to filter their library into actionable segments: books they are currently reading, unread new additions, or completed/finished stories.

## Decision
We implemented an end-to-end **Library Reading Status & Smart Sorting System** across backend and frontend:

### 1. Backend Timestamp Exposure (`backend/routers/threads.py`)
- Extended `ThreadItemOut` and `ThreadDetail` schemas with `last_read_at: Optional[str] = None`.
- Upgraded the 1-query batch bookmark loader (`bookmarks_stmt`) in `GET /api/threads` to join `UserBookmark.last_read_at`.
- Populated `last_read_at` on both collection and single-thread retrieval endpoints.

### 2. Frontend Status Filter Tabs (`src/pages/LibraryPage.tsx`)
- Added interactive navigation pills above the library grid with real-time book count badges:
  - **`Semua (All)`**: Complete novel collection.
  - **`🔥 Sedang Dibaca (Reading)`**: Books with active reading progress (`0% < progress < 100%`).
  - **`✨ Belum Dibaca (Unread)`**: New books that have never been opened (`progress === 0%`).
  - **`✅ Selesai (Completed)`**: Books with 100% reading progress.
- Added contextual empty state cards for each tab with reset filter buttons.

### 3. Dynamic Smart Sorting (`src/pages/LibraryPage.tsx`)
- Introduced a sort control dropdown with four deterministic sorting strategies:
  - **`Terakhir Dibaca (Default)`**: Sorts by `last_read_at DESC`, falling back to `created_at DESC`.
  - **`Baru Ditambahkan`**: Sorts by `created_at DESC`.
  - **`Progres Baca (%)`**: Sorts by `progress DESC`.
  - **`Judul (A-Z)`**: Sorts alphabetically by book title.
- Updated the **Continue Reading Carousel** to strictly sort by `last_read_at DESC`.

### 4. Automated Integration Test Suite (`backend/tests/test_routers/test_library_sorting_and_status.py`)
- Verified `last_read_at` extraction for bookmarked threads.
- Verified null handling and zero progress for unread threads.
- Verified thread detail endpoint contract.

## Consequences
- **Positive**: Active novels are never buried by newly imported books; opening a chapter immediately brings that book to the top of the Library.
- **Positive**: Users can toggle between active reading lists and unread queues in a single click.
- **Positive**: Zero database schema migrations required (reused existing `user_bookmarks.last_read_at` column).
- **Positive**: 100% backward compatible with existing API consumers.
