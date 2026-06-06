# ADR-059: Novel Updates Cloudflare Bypass via curl_cffi

## Status
Accepted

## Context
When scraping novel metadata from Novel Updates, the `cover_image` and full synopsis were consistently missing. 
Historically, Novel Updates upgraded its Cloudflare bot protection, causing the system's `_scrape_detail_page` logic to return HTTP 503 errors. In response, the previous implementation completely disabled detail page scraping, relying solely on extracting limited text from Google Search snippets, which do not contain image URLs.

## Decision
We restored direct interaction with Novel Updates by utilizing advanced TLS fingerprinting evasion:
1. **`curl_cffi` Integration**: We re-enabled `_scrape_detail_page` and `_enhance_metadata` in `novel_updates.py`, using `curl_cffi.requests.AsyncSession` with the `impersonate="chrome120"` parameter.
2. **Targeted Enhancement**: To avoid triggering IP rate limits or secondary Cloudflare hurdles, we do not scrape detail pages for *all* search candidates. Instead, we only invoke `_enhance_metadata` on the Top 1 candidate during a candidate search (`scrape_candidates`).
3. **Data Merge**: The retrieved detail page HTML provides the high-resolution cover image URL, comprehensive genre tags, and the full synopsis, which are merged back into the candidate metadata.

## Consequences

### Positive
- Visually complete metadata retrieval. Users now correctly receive cover images when importing from Novel Updates.
- More accurate genres and synopsis compared to truncated Google snippets.

### Negative
- **Cat-and-Mouse Game**: Cloudflare routinely updates its JA3/TLS fingerprinting algorithms. If `curl_cffi`'s "chrome120" profile becomes outdated, Novel Updates scraping will break again until the library is updated.
