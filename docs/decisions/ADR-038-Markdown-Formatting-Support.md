# ADR-038: Basic Markdown Formatting Support (Bold & Italic)

## Status
Accepted

## Date
2026-05-20

## Context
Users have requested the ability to see basic Markdown formatting—specifically bold (`**text**`) and italic (`*text*` or `_text_`)—while reading chapters in the app. Italics are heavily used in translated web novels to represent inner thoughts, flashbacks, or emphasized speech.

Currently, the reader simply displays plain text wrapped in a `whitespace-pre-wrap` div, exposing the raw asterisks to the user. Additionally, when exporting books to EPUB, this formatting is lost or remains as raw asterisks, degrading the reading experience on external e-readers like Kindle, Apple Books, or Calibre.

We need a way to parse and render these basic styles both in the React frontend (Reader UI) and the Python backend (EPUB Builder).

## Decision
We will implement a lightweight, custom regex-based parser for basic Markdown formatting instead of importing a heavy AST-based markdown library (like `react-markdown` or `markdown-it`).

### Frontend Implementation
1. Add a `renderMarkdown` utility to `src/lib/utils.ts`.
2. The utility will use regex (`/(\*\*.*?\*\*|\*.*?\*)/g`) to split the string and map matching segments to React `<strong>` or `<em>` elements.
3. This utility will be applied inside `ChapterReader.tsx` for both original and translated text.

### Backend EPUB Implementation
1. Modify `clean_html_content` in `backend/routers/export.py`.
2. Apply regex substitutions (`re.sub`) for bold and italic *after* HTML escaping (`&`, `<`, `>`) but *before* paragraph `<p>` wrapping.
3. This ensures the injected `<strong>` and `<em>` tags are not accidentally escaped by the HTML sanitization step.

## Alternatives Considered

### Full Markdown Library (`react-markdown` + `markdown-it`)
- **Pros:** Full spec compliance, handles complex nesting, lists, blockquotes, etc.
- **Cons:** Significantly increases bundle size. Most web novels only use simple bold/italic. Overkill for the current requirement.
- **Rejected:** The performance and bundle size cost outweighs the benefit of supporting features we don't need.

### CSS-Only Regex Highlighting
- **Pros:** Zero DOM manipulation.
- **Cons:** Requires complex Shadow DOM or experimental CSS features not widely supported. Impossible to map to EPUB.
- **Rejected.**

## Consequences
- **Positive:** Users can now clearly distinguish inner thoughts and emphasis without seeing raw asterisks.
- **Positive:** EPUB exports will look professional and native in standard e-readers.
- **Positive:** Zero new dependencies added to either `package.json` or `requirements.txt`.
- **Negative/Risk:** Regex parsing is fragile with complex nesting (e.g., `***bold and italic***`). Our implementation focuses on the simple cases (`**bold**` or `*italic*`) and may ignore or mis-render complex nested formatting. This is an acceptable trade-off for novel translation texts.
