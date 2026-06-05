# ADR-056: Chapter Bookmarks (Favorites)

## Status
Accepted & Implemented

## Date
2026-06-05

## Context
Readers of serialized web novels often want to bookmark or "star" specific chapters (e.g., epic fight scenes, important lore reveals, or favorite moments) to revisit later. While the application previously tracked reading progress (`UserBookmarks` / `last_read_id`), there was no explicit "Favorites" functionality for individual chapters. Furthermore, a Star icon existed in the Sidebar UI but was unmapped to any feature.

## Decision
We implemented a robust Chapter Bookmarks system:

1. **Database Schema Update**:
   - Added an `is_bookmarked` boolean column to the `Chapter` model in SQLAlchemy (`backend/database.py`).
   - Implemented a lightweight auto-migration in `init_db()` to append the column to existing tables using `ALTER TABLE chapters ADD COLUMN is_bookmarked BOOLEAN DEFAULT 0`.

2. **Backend API**:
   - `PUT /api/threads/{thread_id}/chapters/{chapter_id}/bookmark`: Toggles the star state of a given chapter.
   - `GET /api/bookmarks`: Retrieves a cross-thread list of all bookmarked chapters, including thread metadata (to group the results in the UI).
   - Updated `ChapterContent` and `ChapterOut` schemas to serialize the `is_bookmarked` boolean.

3. **Frontend UI**:
   - **Bookmarks Page (`BookmarksPage.tsx`)**: A dedicated page displaying all starred chapters, grouped visually by Novel/Thread. Clicking a chapter routes the user directly to the Reader view.
   - **Reader Integration**: Added an interactive Star button in the sticky top header of `ChapterReader.tsx`. It synchronizes its local state with the backend value.
   - **Global Navigation**: Wired the unused Star icon in the Sidebar (Desktop) and BottomNav (Mobile) to open the new `bookmarks` tab.

## Consequences
- **Improved UX**: Users now have a clear, persistent mechanism to save and revisit their favorite translated chapters without cluttering their reading progress.
- **Data Persistence**: Because bookmarks are stored in the backend SQL database, they sync across the user's mobile and desktop environments automatically.
- **Frontend State Management**: Adjusted the `App.tsx` router to handle specific `initialChapterId` injections when navigating from the Bookmarks page directly into a thread.
