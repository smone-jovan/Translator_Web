# ADR-024: Zero-Padded Clean Title Formatting System

## Context & Problem Statement
When novel chapter titles are processed or imported, they often retain noisy prefixes (e.g. `Chapter X:`, `Bab X -`, `Vol X`, `第X章`, or leading indices like `1. `, `01 - `). When these titles are polished/translated or exported to external formats such as EPUB or TXT, the inconsistent numbering patterns make the novel difficult to read, navigate, and sort properly.

The system required a consistent, beautiful, and automated zero-padded formatting structure (e.g. `01. Title Name`, `001. Title Name`) that strips redundant chapter markers while retaining numbers for export readability.

## Proposed Decisions
1. **Implement `clean_and_format_chapter_title` Helper Function**:
   - Create a central helper function to strip redundant prefixes recursively using robust case-insensitive regular expressions.
   - Clean common wrapping brackets (`【】`, `()`, `[]`, `“` etc.) at the edges.
   - Clean common language chapter markers like `Chapter`, `Bab`, `Vol`, `Volume`, `Ch`, and Chinese counters like `第X章`, `第X话`, `第X节`, `第X回`, `第X卷`.
   - Clean redundant leading digits separated by dot, hyphen, or colons.
   - Dynamically compute zero-padding width based on the total number of chapters in the thread (e.g., width 2 for < 100 chapters, width 3 for < 1000 chapters, width 4 for >= 1000 chapters).
   
2. **Integrate into the Title Polish Pipeline**:
   - Update the `/threads/{thread_id}/translate-titles` endpoint in `threads.py`.
   - Automatically query the total count of chapters in the thread.
   - Apply the `clean_and_format_chapter_title` formatting logic to each translated/polished title before writing it back to the SQLite `chapters` table in the database (`title_translated` field).

3. **Validation & Unit Testing**:
   - Created a comprehensive test suite in `<appDataDir>\brain\<conversation-id>\scratch\test_title_polish.py` containing various typical messy inputs (such as `"Chapter 12: Battle of Gods"`, `"Bab 3 - Dynamic Power"`, `"第3章 决战"`, and large numeric sequences).
   - Validated standard ASCII and multi-byte Chinese print statements to avoid terminal encoding errors on Windows environments.

## Consequences
- **Elegant Readability**: All polished chapter titles are uniform, sequentially ordered, and cleanly prefixed (e.g. `01. First Step`, `02. Second Step`).
- **Pristine Exports**: Since the formatted title is written directly to the database's `title_translated` column, exports to EPUB or TXT formats automatically preserve the beautiful padding and structure.
- **Robust and Warning-Free**: Regex patterns have been structured to avoid Python 3.12+ `FutureWarning` sets and encoding errors.
