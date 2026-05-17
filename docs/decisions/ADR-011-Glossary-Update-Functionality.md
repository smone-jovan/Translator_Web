# ADR-011: Implement Glossary Update (CRUD) Functionality

## Status
Accepted

## Date
2026-05-17

## Context
The AI Context Extraction system allows users to extract terms, but users frequently need to manually refine these terms after they are saved (e.g., changing "Vinny" to "Winnie"). Previously, the system only supported "Create" and "Delete" operations for Lorebook entries. There was no mechanism to update an existing entry, forcing users to delete and re-add terms to make changes.

## Decision
Implement a full Update (PUT) capability for Lorebook entries in both the backend and frontend.

### Backend Changes
- Added `PUT /api/lorebook/{entry_id}` to `backend/routers/lorebook.py`.
- This endpoint accepts the same `LorebookCreate` schema and updates the `original_term`, `translated_term`, and `notes` fields in the database.

### Frontend Changes
- Introduced `editingEntryId` state to `ContextLibraryPage.tsx` to track the entry currently being modified.
- Replaced the placeholder `MoreVertical` button with a functional `Edit` (FileText) button in the glossary cards.
- Updated the `addEntry` function to detect the edit state and switch between `POST` (Create) and `PUT` (Update) requests.
- Enhanced the UI to clearly indicate "Edit Mode" with updated headers, buttons, and a "Cancel Edit" option.

## Consequences
- **Improved UX**: Users can now refine terminology without losing the context of the original entry.
- **Data Integrity**: Updates happen in-place, maintaining consistent IDs for any future relationships.
- **Consistency**: The Glossary now follows standard CRUD patterns, making the codebase more predictable for future development.
