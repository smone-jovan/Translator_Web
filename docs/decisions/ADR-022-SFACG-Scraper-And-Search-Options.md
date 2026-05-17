# ADR-022: Multi-Source Metadata Scraping and Dual Search Options for Novel Updates

## Status
Accepted & Implemented

## Date
2026-05-17

## Context
Following the successful integration of the Novel Updates scraper (ADR-020) and the immersive dashboard details view (ADR-021), the platform has become highly proficient at rendering enriched novel metadata. However, two key operational challenges arose:
1. **Search Query Ambiguity on Novel Updates**: Novel Updates maps search indexing differently depending on the query language. Searching only by Chinese original title sometimes failed or fetched suboptimal matches if the search index lacked the Chinese title. Users need a way to force search query execution via either the **Original Title (Hanzi)** or the **Translated Title (English)** depending on what they have available.
2. **Direct Chinese Novel Scraping (SFACG / 菠萝包轻小说)**: For novels sourced directly from major Chinese platforms like SFACG (`book.sfacg.com`), querying Novel Updates or search engines is redundant. The platform should support direct parsing of the book page itself. The parsed Mandarin text (Chinese titles, descriptions, and genres) must remain in raw Hanzi characters without Latin/Pinyin transcription, so that the reader can subsequently execute the bulk AI "Polished Title" translation on-demand.

## Decision
We will implement an advanced, multi-source metadata scraping strategy and a highly interactive segmented UI control inside `ScrapeNUModal.tsx` to handle these scenarios.

### 1. Backend Integration & Direct SFACG Parser
We updated the FastAPI `/threads/{thread_id}/scrape_metadata` endpoint inside `backend/routers/threads.py`:
- **Request Expansion**: Added optional `search_by` (`"original" | "translated"`) and `source` (`"novelupdates" | "sfacg"`) attributes to `ScrapeMetadataRequest`.
- **Automatic Host Detection**: The backend parses incoming input URL strings. If the string contains `sfacg.com` or if `source` is set to `"sfacg"`, it skips the search engine step entirely and executes a direct, high-performance HTML scrape of the target book page.
- **SFACG Selector Rules**:
  - **Book Title**: Parses `.d-summary .title`, fallback to `.d-normal-banner .title`.
  - **Synopsis/Description**: Parses `.d-summary .introduce` (retains raw Chinese characters).
  - **Genres**: Parses `.tag-list .tag a`.
  - **Cover Image**: Parses `.d-normal-banner .summary-pic img` and normalizes the source protocol.
- **Flexible Title CLEANSING Fallback**: For Novel Updates queries, if `search_by` is set to `"translated"`, it uses the English title. Otherwise, it extracts clean Chinese characters using our local LM Studio AI model to bypass noisy brackets or annotations.

### 2. Segmented, Theme-Aware UI Controls
We designed a high-impact, premium user interface block inside `ScrapeNUModal.tsx` that includes:
- **Source Selection Segment**: A tactile 2-way grid selector enabling instant switching between:
  - 🌐 **Novel Updates** (Search-based)
  - 🍍 **SFACG (菠萝包)** (Direct link or ID-based)
- **Search Query Type Toggle**: Available when Novel Updates is active, letting the user toggle search execution between:
  - 🇨🇳 **Original Title (Hanzi)**
  - 🇬🇧 **Translated Title (English)**
- **Intelligent Host Auto-Detection**: When the modal opens, it analyzes the thread's raw title or original title attributes. If an SFACG URL is detected, the UI automatically defaults the source segmented toggle to **SFACG** and pre-fills the input field with the URL, eliminating manual friction.
- **Adaptive Explanatory Banners**: Dynamically updates the informational card text based on the active source and search type, detailing exactly what parameters the system is using.

## Consequences
- **Complete Scrape Autonomy**: Users can now enrich their personal library books using direct Mandarin text from raw Chinese pages (SFACG) or search indexes (Novel Updates).
- **Zero Latin/Pinyin Pollution**: SFACG fields stay in beautiful native Mandarin characters, matching the user's exact specification.
- **Robustness Against 403 blocks**: Giving the option to switch between English and Chinese search modes on Novel Updates dramatically improves success rates when one title form is blocked or rate-limited.
- **Publication-Grade Interface**: The new segmented toggles, emojis, and adaptive forms align perfectly with the "Obsidian Night" and "Sepia" themes, ensuring an ultra-premium reading experience.
