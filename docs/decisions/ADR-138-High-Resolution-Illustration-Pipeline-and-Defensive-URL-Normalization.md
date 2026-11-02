# ADR-138: High-Resolution Illustration Pipeline, Multi-Tier Defensive URL Normalization, and Gallery Resiliency

## Status
Accepted

## Date
2026-11-01

## Context
Following user reports that novel threads containing illustrations (both legacy threads and recently scraped Novalpie threads) exhibited broken image loads and falsely displayed the *"No Illustrations Found"* empty state in the reader's Images tab (`ThreadImageGallery`), an in-depth empirical investigation across the codebase and database (`backend/app.db`) was performed.

### Empirical Findings & Root Cause Analysis

1. **Illustration Payload Ceiling Rejection (`MAX_IMAGE_BYTES`)**:
   - Modern web novel platforms (e.g., Novelpia Korea / Novalpie) frequently serve high-resolution lossless PNG and 4K digital illustrations ranging from **11 MB to 19 MB** (e.g., Thread 91: 18.91 MB; Thread 137 Ch 34: 13.49 MB; Thread 140 Ch 37: 11.59 MB).
   - In `backend/services/image_fetcher.py`, `MAX_IMAGE_BYTES` was historically capped at 10 MB (10,485,760 bytes). Any illustration payload exceeding 10 MB triggered `ResponseTooLarge` in `_fetch_httpx`, causing `/api/images/proxy` to return HTTP 404. Over 66 chapter illustrations and 2 book covers in the database were affected.
2. **Protocol-Relative URL Proxy Bypass (`//images.novelpia.com/...`)**:
   - Novalpie's API payloads format image sources with protocol-relative URLs (`//images.novelpia.com/...`).
   - Frontend validation in `renderMarkdown`, `coverImageSrc`, and `SafeReaderImage` strictly checked `startsWith("http://") || startsWith("https://")`. As a result, protocol-relative URLs bypassed the local backend proxy (`/api/images/proxy`) and were requested directly by the client browser, failing due to CORS policies and CDN hotlinking protections.
3. **Naive String Replacement Regression (`https:https://`)**:
   - An earlier migration script executed `replace("//images.novelpia.com", "https://images.novelpia.com")` on raw chapter content.
   - Because standard absolute URLs already contain `//images.novelpia.com`, this string substitution prepended an extra `https:`, converting 1,428 URLs across 772 chapters into corrupted duplicate-scheme URLs: `https:https://images.novelpia.com/...`.
4. **Gallery Extraction Breakdown (`extract_images_with_metadata_from_chapter`)**:
   - In `backend/services/image_cacher.py`, `extract_images_with_metadata_from_chapter` utilized a strict regex `r'!\[(.*?)\]\(((?:https?://|//|/images/)[^\s\)]+)\)'`.
   - The malformed `https:https://` URLs failed the regex match. Consequently, `get_thread_images` returned 0 illustrations for 23+ threads (including Threads 60, 79, 81, 88, 89, 90, 91, 92, 93, 94, 95, 97, 98, 99, 100, 101, 105, 113, 114, 136, 137, 138, 139, 140, 142), triggering the *"No Illustrations Found"* banner.
5. **Inverted Markdown in Pixiv Scraper Imports (Thread 60)**:
   - 25 chapters in Thread 60 contained inverted markdown produced by third-party novel downloaders: `![https://i.pximg.net/...](chapter-...)`, where the remote illustration URL was stored in the `alt` attribute and the URL field held a dead relative EPUB filename.
6. **LLM Translation Placeholder Hallucinations**:
   - Neural translation models occasionally transformed image tokens (`❖IMAGE_0❖`) into hallucinated dummy tags (`<img src="image_0.png">`, `![image_0](placeholder)`), losing the original illustration links.

---

## Decisions

### 1. Payload Ceiling & Network Timeout Expansion
- In `backend/services/image_fetcher.py`:
  - Raised `MAX_IMAGE_BYTES` from 10 MB to **25 MB** (26,214,400 bytes) to accommodate lossless 4K novel illustrations.
  - Increased network timeout in `_fetch_httpx` to **25.0 seconds** (connect timeout 5.0s) to handle large multi-megabyte image transfers reliably.

### 2. Multi-Tier Defensive URL Normalization (Defense-in-Depth)
Implemented a canonical, idempotent URL normalization function across both backend and frontend:
- **Backend (`normalize_image_url`)** in `services/image_cacher.py`, `services/image_fetcher.py`, and `routers/images.py`:
  ```python
  def normalize_image_url(url: Optional[str]) -> str:
      if not url:
          return ""
      u = url.strip()
      u = re.sub(r'^(?:https?:)+(//)', r'https:\1', u, flags=re.IGNORECASE)
      if u.startswith("//"):
          u = f"https:{u}"
      return u
  ```
- **Frontend (`normalizeImageUrl`)** in `src/lib/utils.ts`, `ThreadImageGallery.tsx`, and `SafeReaderImage.tsx`:
  ```typescript
  export function normalizeImageUrl(url: string | null | undefined): string {
    if (!url) return "";
    let clean = url.trim();
    clean = clean.replace(/^(?:https?:)+(\/\/)/i, "https:$1");
    if (clean.startsWith("//")) {
      clean = `https:${clean}`;
    }
    return clean;
  }
  ```
- Applied before SSRF validation, proxy fetching, cache lookups, and markdown rendering.

### 3. Resilient Gallery & Chapter Image Extraction
- Updated `extract_images_with_metadata_from_chapter` and `extract_remote_image_urls_from_text` in `backend/services/image_cacher.py`:
  - Regex pattern expanded to `(?:(?:\w+:)+//|//|/images/|[^\s\)]+\.(?:jpe?g|png|webp|gif|file))` to match any duplicated scheme or local asset safely.
  - Added fallback inverted resolution: if `url` is a dead local filename and `alt` contains a valid `http(s)://` URL, `url` is swapped to `alt`.

### 4. Scraper Routing & Translation Restoration Hardening
- In `backend/services/scrapers/novalpie.py`:
  - Filenames containing `"cover"` or `"_q_ori"` route to `/imagebox/cover/{hash}`, while content illustrations route to `/imagebox/{prefix}/{hash}`.
  - Added CDN alias normalization (`jpg.freenovel.sbs`, `novelkit.top`, Cloudflare R2) and placeholder replacements (`[[img:hash]]`, `[图片: URL]`).
- In `backend/services/background_translator.py`:
  - `_restore_images_in_text` regex expanded to restore AI-altered placeholder tags (`<img src="image_0.png">`, `![image_0](...)`) back to original illustrations and strip orphaned dummy tags.

### 5. Comprehensive Database Repair
Executed automated database migration on `backend/app.db`:
- Corrected 1,428 corrupted `https:https://` instances across 772 chapters to canonical `https://`.
- Normalized standalone `//images.novelpia.com` using negative lookbehind regex (`(?<!:)//images\.novelpia\.com`).
- Repaired all 25 inverted markdown chapters in Thread 60 to standard `![插图](https://i.pximg.net/...)`.
- Resynchronized `image_count` column across all 27,237 chapters in `app.db`.

---

## Consequences

### Positive
- **Zero Empty Galleries**: All 59 threads with illustrations in `backend/app.db` successfully populate their gallery in `ThreadImageGallery` (100% success rate, 0 false *"No Illustrations Found"*).
- **High-Resolution Support**: Full support for large 4K web novel illustrations up to 25 MB without timeouts or truncation.
- **Architectural Immunity**: Defensive normalization at all layers prevents malformed URLs from breaking image proxying or database queries in the future.
- **Preserved Safety Invariants**: Zero new external dependencies, strict TypeScript compliance (`tsc -b --noEmit`), and zero lockfile changes.

### Verification Evidence
- **Backend Test Suite**: 69 unit and integration tests passing (`pytest` across `test_image_cacher.py`, `test_chapter_images.py`, `test_image_fetcher.py`, `test_novalpie_scraper.py`, `test_background_translator.py`, `test_manga_fallback.py`).
- **End-to-End API Audits**:
  - Thread 88: 308 gallery images verified
  - Thread 91: 150 gallery images verified
  - Thread 99: 194 gallery images verified
  - Thread 136: 92 gallery images verified
  - Thread 140: 65 gallery images verified
  - Thread 97: 44 gallery images verified
  - Thread 142: 25 gallery images verified
  - Thread 137: 22 gallery images verified
  - Thread 60: 16 gallery images verified
- **Live Proxy Caching**:
  - Thread 137 Ch 34 (13.49 MB PNG): HTTP 200, `image/png`
  - Thread 140 Ch 37 (11.59 MB PNG): HTTP 200, `image/png`
  - Thread 60 Ch 0 (294 KB JPEG via Pixiv): HTTP 200, `image/jpeg`
- **Quality Gates**:
  - TypeScript: `npm run typecheck` (`tsc -b --noEmit`) $\to$ Exit code 0 (0 errors).
  - Linter: `npm run lint` (`eslint .`) $\to$ Exit code 0 (0 errors).
