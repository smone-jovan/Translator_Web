# ADR-069: TOC Scraper and Bulk Import Pipeline

## Status
Accepted

## Date
2026-06-09

## Context
Adding novels to the system previously required manual chapter-by-chapter URL entry or reliance on specific platform scrapers (SFACG). Users needed a more flexible way to onboard novels from any web source that provides a table-of-contents page with chapter links.

## Decision
Create a new `toc.py` router that provides a two-phase novel onboarding pipeline:

### Phase 1: TOC Scraping (`POST /api/threads/scrape-toc`)
- Accept any URL and scrape it for chapter links using heuristic detection
- Heuristics include: link density analysis, common chapter URL patterns, link text pattern matching (numbered titles, "Chapter X", Chinese chapter markers like 第X章)
- If fewer than 50 chapters are detected on the initial page, automatically follow links that appear to be dedicated TOC/index pages
- Return the discovered chapter list with titles and URLs

### Phase 2: Bulk Import (`POST /api/threads/bulk-import-toc`)
- Accept the scraped chapter list and create Chapter records in the database
- Chapters are created with URLs only — actual content is scraped on-demand when the user opens a chapter
- For SFACG sources, automatically fetch novel metadata (author, synopsis, cover image)
- Deduplication: skip chapters whose URLs already exist in the thread

## Alternatives Considered

### Platform-Specific Scrapers Only
- Pros: Higher accuracy per platform, structured API access where available
- Cons: Requires new scraper code for every novel source, doesn't scale
- Rejected: The heuristic approach covers 80%+ of sources with zero per-platform code

### RSS/OPML Import
- Pros: Standardized format, easy to parse
- Cons: Most Chinese web novel sites don't provide RSS feeds
- Rejected: Not applicable to the target content sources

### Full Content Scraping at Import Time
- Pros: All content available immediately offline
- Cons: Slow import (minutes for 1000+ chapters), wastes bandwidth for chapters never read, higher risk of IP blocking
- Rejected: On-demand scraping is more efficient and respectful of source servers

## Consequences
- Users can onboard novels from virtually any web source with a TOC page
- Content is scraped lazily, reducing import time from minutes to seconds
- Heuristic detection may produce false positives on non-novel pages — the user reviews and confirms the chapter list before import
- SFACG metadata enrichment runs automatically for recognized SFACG URLs
- The lazy scraping model means chapters require an internet connection on first read
