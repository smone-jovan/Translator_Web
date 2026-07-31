# ADR-081: Foreign Key Index Optimization

## Status
Accepted

## Date
2026-06-14

## Context
Users reported noticeable lag when navigating from the Library page to the Context/Lorebook page. Investigation revealed the root cause:

- The SQLite database had grown to **157 MB** with **11,655 chapters** and **5,684 lorebook entries**
- **No indexes existed on any foreign key columns** (`thread_id`, `chapter_id`)
- Every query like `SELECT * FROM chapters WHERE thread_id = ?` or `SELECT * FROM lorebook_entries WHERE thread_id = ?` required a **full table scan** — reading all 11,655 chapter records just to find ~200 belonging to one thread

This is a textbook database performance anti-pattern. SQLAlchemy does NOT automatically create indexes on `ForeignKey` columns; only `primary_key=True` and explicit `index=True` get indexes.

## Decision
1. **Add `index=True`** to all foreign key columns in the SQLAlchemy models:
   - `Chapter.thread_id`
   - `TranslationSegment.chapter_id`
   - `UserBookmark.thread_id` and `UserBookmark.chapter_id`
   - `CharacterRelationship.thread_id`
   - `LorebookEntry.thread_id`

2. **Create indexes on the live database** via direct SQL:
   - `CREATE INDEX idx_chapters_thread_id ON chapters(thread_id)`
   - `CREATE INDEX idx_lorebook_entries_thread_id ON lorebook_entries(thread_id)`
   - `CREATE INDEX idx_translation_segments_chapter_id ON translation_segments(chapter_id)`
   - `CREATE INDEX idx_character_relationships_thread_id ON character_relationships(thread_id)`

3. **Run VACUUM and ANALYZE** to reclaim space and update the query planner.

## Alternatives Considered

### Migrate to PostgreSQL
- Pros: Better concurrent write support, more robust indexing.
- Cons: Adds deployment complexity for a single-user desktop application.
- Rejected: SQLite with proper indexes is more than sufficient for this use case.

### Add query-level pagination
- Pros: Reduces data transfer per request.
- Cons: Doesn't fix the underlying scan problem; even page 1 would be slow without indexes.
- Rejected: Indexes are the correct fix. Pagination can be added later if needed.

## Consequences
- Context/Lorebook page load time improves from O(n) full table scan to O(log n) index lookup.
- Database size reduced from 157 MB to 150 MB after VACUUM.
- Future `create_all()` calls will automatically create these indexes on new databases.
- All 84 existing tests continue to pass.
