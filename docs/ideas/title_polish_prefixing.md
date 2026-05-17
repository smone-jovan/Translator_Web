# Refined Concept: Zero-Padded Sequential Title Polish Prefixing

## Problem Statement
When polishing novel chapter titles, we want chapter titles to be consistently structured in a clean, zero-padded numbered format (e.g., `01. Title`, `002. Title`) in the database. This ensures that the reading order is highly clear, easy to navigate, and beautifully preserved when the book is exported to offline formats (EPUB, TXT).

## Recommended Direction
We will implement **Option A (Dynamic Prefixing with Strict Sanitization)** inside the FastAPI backend. 
- When the bulk title polish endpoint `/threads/{thread_id}/translate-titles` processes chapter titles, it will parse the returned translation.
- It will strip any pre-existing numbers, colons, dashes, and terms like *Chapter*, *Bab*, *Vol*, or *第几章* from the start of the title to avoid duplication.
- It will calculate the total number of chapters in the thread to dynamically choose the padding width:
  - If total chapters < 100: Pad to 2 digits (`01. Title`)
  - If total chapters between 100 and 999: Pad to 3 digits (`001. Title`)
  - If total chapters >= 1000: Pad to 4 digits (`0001. Title`)
- The clean zero-padded formatted title will be stored directly into `Chapter.title_translated` in the database.

## MVP Scope
1. **Dynamic Padding Helper**: A Python helper function in `threads.py` that sanitizes titles and formats them with zero-padding.
2. **Bulk Title Polish Endpoint Integration**: Hook this helper into the loop in `threads.py` where `title_translated` is saved.
3. **Single Chapter Polish Integration**: Support the same clean formatting when translating/polishing a single chapter title.

## Not Doing (and Why)
- **Hardcoding 2-digit padding**: Not doing because novels with 100+ or 1000+ chapters would look misaligned (e.g. `99. Title` followed by `100. Title`). Dynamic padding solves this elegantly.
- **Frontend-only prefixing**: Not doing because exported files (EPUB/TXT) would lose the clean numbers. Storing directly in the database is the most robust approach.
