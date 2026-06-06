# ADR-057: Auto-Fetch Next Web Chapter Integration

## Status
Accepted

## Context
When reading a novel, the database eventually runs out of chapters that have been imported or scraped. Previously, users had to exit the reader UI, navigate to the source website, copy the next chapter URL, and import it manually. This breaks the immersion and disrupts the reading flow, particularly for users reading directly from sources like SFACG.

## Decision
We implemented an "Auto-Fetch Next Chapter" system that seamlessly scrapes the next chapter directly from the reading interface:
1. **Backend Route (`POST /api/threads/{thread_id}/chapters/{chapter_id}/fetch-next`)**: Extracts the current chapter's `source_url`, fetches the HTML, and searches for "Next Chapter" navigation links (e.g., "Next", "下一章"). It then automatically scrapes the target URL, extracts the markdown, and appends it to the thread.
2. **Frontend UI Integration**: The `ChapterReader` component dynamically replaces the standard "Next Chapter" button with a "Fetch Next Web Chapter" button when the user reaches the last available chapter in the database.
3. **VIP Detection**: The scraper naturally inherits the VIP paywall detection from the main scraping logic. If the next chapter is VIP, it creates an idle VIP chapter instead of crashing.

## Consequences

### Positive
- Vastly improved UX and reading immersion. Users can now read indefinitely without returning to the main dashboard.
- Reduces friction and manual URL copy-pasting.

### Negative
- Scraping logic is tightly coupled to the DOM structure of specific sites. If a site changes its navigation button text or layout, the "Next Chapter" discovery may fail.
