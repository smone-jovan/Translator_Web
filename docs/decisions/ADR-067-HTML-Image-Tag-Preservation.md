# ADR-067: HTML Image Tag Preservation in Translation Pipeline

## Status
Accepted (extends ADR-038)

## Date
2026-06-11

## Context
Some web novel sources (particularly SFACG) embed images directly in chapter content using raw HTML `<img>` tags rather than Markdown syntax. The existing rendering pipeline (ADR-038) only supported Markdown formatting (`**bold**`, `*italic*`, `![alt](url)`), causing `<img>` tags to render as raw text instead of actual images.

Additionally, the AI translation engine needed explicit instructions to preserve HTML tags during translation, as some models would strip, translate attribute values, or replace `<img>` tags with textual descriptions like "[Image]".

## Decision
Extend the rendering and translation pipeline to preserve and render HTML `<img>` tags end-to-end.

### Frontend (`utils.ts` — `renderMarkdown()`)
- Extend the regex splitter to also capture `<img>` tags: `/<img\s+[^>]*src\s*=['"][^'"]+['"][^>]*>/`
- Parse `src` and `alt` attributes from captured `<img>` tags
- Render as React `<img>` elements with appropriate styling
- Prefix relative paths (e.g., `/images/...`) with `API_BASE` for local image serving

### Backend (`context_engine.py` — Translation Prompt)
- Add explicit "HTML TAGS PRESERVATION" rule to the system prompt:
  - "If you encounter HTML tags (such as `<img src="...">`), you MUST preserve them EXACTLY as they are"
  - "DO NOT translate, remove, or replace HTML tags with textual descriptions"

## Alternatives Considered

### Convert `<img>` to Markdown Before Storage
- Pros: Unified format, simpler renderer
- Cons: Lossy conversion (HTML attributes like `class`, `style` lost), requires scraper changes per source
- Rejected: Better to support both formats in the renderer

### Use `dangerouslySetInnerHTML`
- Pros: Renders any HTML natively
- Cons: XSS vulnerability, loses React control over DOM elements
- Rejected: Security risk outweighs convenience

## Consequences
- Images from SFACG and other HTML-rich sources now render in both original and translated views
- AI translation preserves `<img>` tags intact in the translated output
- The `renderMarkdown()` function now handles a superset of Markdown + HTML images
- Future HTML tag support (e.g., `<table>`, `<a>`) can follow the same pattern
