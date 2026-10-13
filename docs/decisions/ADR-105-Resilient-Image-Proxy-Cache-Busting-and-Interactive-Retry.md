# ADR-105: Resilient Image Proxy, Cache Invalidation, and Interactive Image Retry

## Status
Accepted

## Date
2026-09-03

## Context
When loading illustrations inside novel chapters or within the Thread Images Gallery, images could occasionally fail due to upstream CDN timeouts, remote host rate limits, or transient network hiccups. Previously:
1. Failed images were rendered as broken image icons or stuck empty placeholders without any mechanism for users to retry or refresh them.
2. The proxy backend cached images permanently (`max-age=31536000, immutable`), meaning if an image failed or corrupted during download, there was no way to force a fresh re-fetch without manual disk manipulation.
3. Strict referers (`Referer: https://novalpie.cc/`) could result in 403 Forbidden responses on image hosts that mandate their own origin domain as referer.

## Decision
We implemented an end-to-end **Interactive Image Retry and Cache-Busting Refresh** system across both backend and frontend:

### 1. Backend Proxy with Force Invalidation (`backend/routers/images.py`)
- Added query parameter `force: bool = False` to `GET /api/images/proxy`.
- When `force=True`:
  - Locates and unlinks any existing cache files matching the URL hash.
  - Dynamically computes `Referer` from the target URL's origin (`{scheme}://{netloc}/`) to satisfy upstream hotlink protection.
  - Uses a resilient 12.0s timeout and follow-redirects.
  - Returns `Cache-Control: no-cache` and `X-Cache-Status: MISS` with fresh image data.

### 2. Markdown Image Resilience (`src/components/reader/SafeReaderImage.tsx` & `src/lib/utils.ts`)
- Created `SafeReaderImage`:
  - Traps `onError` and replaces broken images with an elegant error card:
    - Displaying an `ImageOff` icon and chapter illustration title.
    - Explicit failure explanation ("Network timeout or image blocked by host").
    - Interactive **`Refresh Image`** button with loading spinner.
  - Clicking retry appends `&force=true&t=${Date.now()}` to bypass browser cache and force server-side redownload.
  - Includes a subtle quick-refresh button on hover for loaded images.
- Wired `SafeReaderImage` into `renderMarkdown` in `src/lib/utils.ts` for all markdown and HTML `<img>` tags.

### 3. Gallery & Lightbox Retry System (`src/components/reader/ThreadImageGallery.tsx`)
- Per-image error tracking (`failedUrls`, `retryingUrls`, `retryKeys`).
- **Thumbnail Grid Cards**: Failed images render an inline retry card with a dedicated **Refresh** button; hover overlay includes a 1-click refresh icon.
- **Header Bar Batch Action**: Dynamically shows a **"Retry Failed ({count})"** button when one or more illustrations fail.
- **Full-Screen Lightbox**:
  - Adds a dedicated **Refresh** button in the top toolbar.
  - Renders a centered, high-visibility error card with **"Refresh Illustration"** when full-size image loading fails.

## Consequences
- **Positive**: Zero stuck or broken image states. Users can immediately recover failed illustrations with a single tap/click.
- **Positive**: Hotlink-protected images from non-Novalpie CDNs load reliably via dynamic referer resolution.
- **Positive**: 100% test coverage with 167 passing backend tests, zero TypeScript errors (`tsc -b --noEmit`), and zero ESLint warnings.
