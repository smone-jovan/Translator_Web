# ADR-010: Implementation of Reading History and Bookmark System

## Status
Accepted

## Date
2026-05-16

## Context
The application needed a way to track user reading progress across different devices and sessions. Specifically:
- Automatically remember the last chapter read in each thread.
- Display a "Continue Reading" banner on the Library page.
- Show visual indicators in the chapter list for the "Last Read" position.

## Decision
1.  **Database Table**: Created `user_bookmarks` table to store `thread_id`, `chapter_id`, and `last_read_at`.
2.  **Auto-Update**: Hooked into the `GET /api/threads/{id}/chapters/{chapter_id}` endpoint. Every time a chapter is fetched, the bookmark for that thread is updated or created.
3.  **Library Integration**: Updated `GET /api/threads` to join with bookmarks and return `last_read` title and calculated `progress` percentage.
4.  **UI Banner**: Implemented a premium-styled banner in `LibraryPage.tsx` that appears if any reading progress exists.

## Consequences
- Users can switch between laptop and mobile and resume exactly where they left off.
- The Library page feels alive and personalized.
- Slight performance overhead for bookmark updates on every chapter view (mitigated by indexed DB lookups).