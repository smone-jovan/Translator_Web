# ADR-050: Handling Cloudflare and AI Safety Filters

## Status
Accepted

## Date
2026-06-02

## Context
1. **NovelUpdates Scraping**: NovelUpdates has enabled strict Cloudflare Turnstile bot protection, making it impossible to directly scrape HTML using standard Python scripts (`httpx`, `curl_cffi` with impersonation, etc.). Previously, we built a fallback mechanism to pull `Cover` and `Genre` from MangaUpdates when NovelUpdates was blocked. However, MangaUpdates primarily contains Manhwa/Comic data, which produces incorrect covers and genres for Novels, causing user frustration.
2. **AI Safety Filters (Prohibited Content)**: When translating NSFW or explicit content, AI models (specifically Gemini) often return an `HTTP 400 Bad Request` with a Safety Violation or `finishReason: PROHIBITED`. Our previous fallback mechanism interpreted this HTTP 400 as a generic API failure and forced a fallback retry using `gemini-2.5-flash`. This fallback would inevitably also hit the safety filter, causing a complete waste of tokens, extra API latency, and ultimately returning a blank chapter anyway.

## Decision
1. **Disable MangaUpdates Fallback**: Completely disable the MangaUpdates API fallback for extracting covers and genres. The scraper will strictly rely on `Google Search` / `Yahoo Search` snippets to extract the Title and Synopsis. Cover URL and Genres will default to empty (`None`). This aligns with the strict user requirement to **only** use NovelUpdates data, allowing the user to manually paste the CDN image URL in the UI rather than automatically assigning a wrong Manhwa cover.
2. **Short-circuit Safety Violations**: Modify the `GeminiAdapter._try_chat_completion` exception handler. If an exception string contains safety-related keywords (`"prohibited"`, `"content_filter"`, `"safety"`, `"blocked"`), the adapter will immediately return a `PROHIBITED_MARKER` instead of throwing an exception or continuing the fallback loop.

## Consequences
- **Positive**: We no longer pollute the database with inaccurate Manhwa covers and genres.
- **Positive**: Prevents wasting tokens by aggressively retrying blocked content with fallback models. The chapter is instantly skipped and marked as `prohibited`.
- **Positive**: The UI's "Include Prohibited Content" toggle in Bulk Translation now functions efficiently, allowing users to safely skip previously blocked chapters or manually override them via local LLMs (LM Studio) without fear of repeated API token waste.
- **Negative**: Novel covers and genres will initially be empty when fetching from NovelUpdates via direct link, requiring manual input from the user. (This is deemed acceptable by the user over having incorrect data).
