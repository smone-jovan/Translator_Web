# ADR-103: One-Click Thread Image Cacher and High-Performance Reader Proxy

## Status
Accepted

## Date
2026-09-03

## Context
Following the implementation of ADR-100 (Illustrated Chapter Badge & Filtered Discovery System), readers can filter chapters to see those containing illustrations. In web novels scraped from Korean/Chinese platforms (e.g. Novelpia, Kakuyomu, SFACG), chapters contain remote image URLs.

### Problems
1. **Remote Hotlink Protection / CORS Failures**: Direct requests from reader browsers to remote CDNs frequently fail or encounter latency.
2. **Offline & Longevity Vulnerability**: If the remote host deletes images or blocks IP addresses, images break inside the reader.
3. **Redundant Downloads**: Prior to this ADR, image caching only occurred at EPUB export time. The web reader made direct HTTP requests over the internet rather than leveraging local disk storage.

## Decision
We implemented a unified, resilient **Thread Image Cacher and Reader Proxy System**:

### 1. Dedicated Image Caching Service (`backend/services/image_cacher.py`)
- Centralized disk storage in `uploads/cache/images/` using SHA-256 hash filenames.
- Magic-byte image inspection (`guess_image_ext_from_bytes`) supporting PNG, JPEG, WEBP, GIF, and SVG.
- Strict filesystem security invariants:
  - Canonicalization with `Path.resolve()`.
  - Path traversal defense with `is_relative_to(CACHE_DIR)`.
  - Rejection of NUL bytes (`\x00`).
- Resilient concurrent download engine (`prefetch_remote_images` with Semaphore 10, connect timeout 3.0s, user-agent and referer headers).
- Non-blocking background worker tracking thread image jobs in `ACTIVE_IMAGE_JOBS`.

### 2. High-Speed Image Proxy & Management Endpoints (`backend/routers/images.py`)
- `GET /api/images/proxy?url=...`:
  - Instant cache hits served directly from local disk with `Cache-Control: public, max-age=31536000, immutable`.
  - Transparent on-demand fetch and disk caching on cache misses.
- `POST /api/threads/{thread_id}/cache-images`:
  - Scans all chapters in the novel for unique remote illustration URLs and spawns a background caching task.
- `GET /api/threads/{thread_id}/cache-images/status`:
  - Provides real-time progress statistics (`total`, `cached`, `percent`, `is_all_cached`).

### 3. Transparent Reader Proxy Routing (`src/lib/utils.ts`)
- In `renderMarkdown`, remote URLs (`http://` or `https://`) in `<img>` tags and `![alt](url)` markdown are automatically rewritten to `${API_BASE}/api/images/proxy?url=${encodeURIComponent(url)}` with `loading="lazy"`.

### 4. Interactive UI Controls (`src/components/reader/ChapterListControls.tsx`)
- Placed directly next to the `Illustrated (N)` filter tab:
  - Default: `[CloudDownload] Cache Images` button.
  - Active: Spinning loader with dynamic live progress `Caching 42/308...`.
  - Completed: Emerald check badge `[CheckCircle2] All Cached`.
  - Background polling mechanism with toast notifications upon job completion.

## Consequences
- **Positive**: Readers can cache all illustrations in a novel with a single click.
- **Positive**: Reading experience is completely decoupled from remote CDN availability and hotlink restrictions.
- **Positive**: Shared cache architecture between Web Reader and EPUB Exporter: once cached via the button, subsequent EPUB exports complete with zero image download delay.
- **Positive**: 100% test passing across 164 backend tests, TypeScript typechecking, and ESLint.
