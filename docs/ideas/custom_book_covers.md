# Custom Book Covers System (custom_book_covers.md)

## Problem Statement
How Might We allow users to personalize their translation library by uploading custom cover files or pasting image URLs directly from the 3-dots menu of any book in their library, while maintaining highly-portable database storage and visual excellence?

## Recommended Direction
We will implement an integrated, fully portable cover image workflow:
1. **Base64 & URL Persistence**: The SQLite database will store either raw Base64 strings (for local uploads compressed in the frontend to < 100KB) or direct image URLs in a new `cover_image` text column on the `threads` table.
2. **Automated Migration**: We will enhance `backend/database.py`’s `init_db()` function to automatically detect and add the `cover_image` column if it is missing, guaranteeing zero data loss.
3. **Title-Based Seeded Gradient Covers**: If a book does not have a custom cover, the frontend will automatically render a premium CSS abstract gradient dynamically generated from a hash of the book's title.
4. **Glassmorphic Editor Modal**: A premium `EditCoverModal` will be added to the library page, letting users upload a local file or paste a web URL with a live preview.

## MVP Scope

### Backend
- Add `cover_image` to the `threads` table and update the SQLite initialization auto-migration logic.
- Expose `cover_image` in the `ThreadItemOut` and `ThreadDetail` schemas.
- Build a new `PUT /api/threads/{id}/cover` endpoint to update the cover string.

### Frontend
- Create a reusable, elegant `EditCoverModal` supporting local file selection (with canvas compression to ensure Base64 strings stay < 100KB) and URL text inputs.
- Add an "Edit Cover" option to the `LibraryBookCard`'s 3-dots menu.
- Integrate the cover display: Render custom covers when present, and automatically fall back to the seeded dynamic gradient cover when not.

## Not Doing (and Why)
- **Backend File System Image Storing**: Avoids cross-platform file path complications (Windows vs Linux) and simplifies multi-device synchronization (e.g. accessing from an iPhone over local WiFi) since Base64 stays portable inside the database.
- **Deep cropping library tools**: Keeps frontend dependencies lightweight and code clean. Simple scale-to-fit CSS object-cover is sufficient.
