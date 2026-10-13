# ADR-104: Novel Thread Images Gallery and Visual Browser

## Status
Accepted

## Date
2026-09-03

## Context
Following the implementation of ADR-100 (Illustrated Chapter Badge & Filtered Discovery) and ADR-103 (One-Click Thread Image Cacher & Reader Proxy), readers could filter chapters to see those with illustrations and pre-cache them. However:
1. Readers wanting to explore or review character art, visual inserts, and cover variants across the entire novel still had to open chapters one by one.
2. There was no single visual gallery aggregating all illustrations contained across all chapters of a novel thread.

## Decision
We implemented a dedicated **Novel Thread Images Gallery & Visual Browser** integrated directly into the Chapter Controls bar:

### 1. Backend Endpoint (`backend/routers/images.py`)
- `GET /api/threads/{thread_id}/images`:
  - Scans chapters having `image_count > 0`.
  - Extracts image URLs and alt text from both original and translated text using `extract_images_with_metadata_from_chapter`.
  - Returns structured list with `url`, `chapter_id`, `chapter_order`, `chapter_title`, and `alt`.

### 2. Interactive Visual Gallery (`src/components/reader/ThreadImageGallery.tsx`)
- Responsive multi-column grid (2 cols mobile up to 5 cols desktop).
- Displays images through the local proxy `/api/images/proxy` for zero-latency, offline-capable rendering with `loading="lazy"`.
- Badges displaying chapter numbers (`Ch. {order}`) on each thumbnail.
- Chapter title and alt text metadata.
- Interactive **Full-Screen Lightbox**:
  - Image zoom control (1x to 1.5x).
  - Download original image button.
  - Previous / Next navigation buttons with keyboard arrow support.
  - "Read Chapter" quick-jump button directly opening that chapter in Reader.
- Empty state fallback with descriptive messaging.

### 3. Chapter Controls Tab Integration (`src/components/reader/ChapterListControls.tsx` & `src/pages/ReaderPage.tsx`)
- Extended `chapterFilter` type to: `'all' | 'translated' | 'illustrated' | 'images'`.
- Added the 4th tab button **`Images`** with rose styling, `Images` icon, and live badge showing total illustrations in the novel.
- Conditionally swaps the chapter grid for `ThreadImageGallery` when `Images` is selected, preserving all search and navigation controls.

## Consequences
- **Positive**: Seamless visual browsing of all novel art and illustrations in one unified gallery.
- **Positive**: Instant jumping from any illustration directly into its corresponding chapter.
- **Positive**: 100% test coverage across 166 backend tests, zero TypeScript errors, and zero ESLint warnings.
