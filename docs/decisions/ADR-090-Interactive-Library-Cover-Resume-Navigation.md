# ADR-090: Interactive Library Cover & Instant Resume Navigation

## Status
Accepted

## Date
2026-08-07

## Context
In `LibraryPage.tsx`, entering a novel thread required hovering over the card to locate a play button overlay or opening the card's three-dot menu. Furthermore, users lacked a direct 1-click option on individual book cards to immediately resume reading from their last read chapter.

## Decision
1. **Interactive Cover Poster Area**: Update `LibraryBookCard` poster box (`aspect-[3/4]`) to be fully interactive (`cursor-pointer onClick={() => onOpen()}`). Clicking anywhere on the cover image or title gradient opens the thread overview.
2. **Direct "Resume Reading" Action Button**:
   - Render a primary `Resume: [Chapter Name]` button directly below the cover image / above progress in `LibraryBookCard`.
   - Clicking the Resume button invokes `onOpen(thread.last_read_id)`, passing `last_read_id` to `openReaderFromLibrary(threadId, chapterId)` in `App.tsx`.
   - `App.tsx` sets `openChapterId`, causing `ReaderPage.tsx` to automatically jump to and open the exact last read chapter.
   - For new unread novels, render a `Start Reading` outline button that opens chapter 1.

## Consequences
- Cover image boxes feel tactile and immediately clickable.
- Readers can resume their reading journey in 1 click directly from the Library card.
- Smooth fallback to "Start Reading" for newly imported books.
