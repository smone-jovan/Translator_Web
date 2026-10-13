# ADR-099: Novalpie Headless Browser Fallback and Cloudflare Bypass Architecture

## Status
Accepted

## Date
2026-08-31

## Context
[ADR-098](./ADR-098-Novalpie-Novel-Crawler-and-Metadata-Adapter.md) established the initial `NovalpieAdapter` using a direct REST API approach for chapter content via `/api/novels/{id}/chapters/{chapter_id}`. Post-deployment testing revealed a reliability problem:

`novalpie.cc` uses **Cloudflare Turnstile** to protect chapter content endpoints. When scraping chapters, `httpx.AsyncClient` often received either a `404` or a `200 OK` whose body contained the Cloudflare Turnstile challenge page (under 50 characters of extractable text) rather than the actual novel content.

This triggered a critical secondary bug: the global `is_vip = True` heuristic in the scraper logic (originally designed to detect paywalled chapters by short content length `< 50 chars`) was falsely activated by Turnstile challenge responses. Dozens of missing chapters were permanently marked as VIP and replaced with the `"[VIP CHAPTER] Bab ini terkunci"` placeholder, preventing them from being re-fetched by the batch translator.

Additionally, large bulk fetches via the background worker **bypassed the Playwright implementation entirely** due to a codebase regression, resulting in rapid instant-failures across the board.

## Alternatives Considered

| Option | Reason Rejected |
|---|---|
| **Playwright Async API directly** | Playwright's async API conflicts with Uvicorn's AnyIO/asyncio eventloop on Windows, causing deadlocks when called from within async route handlers. |
| **Delay-based rate limiter instead of Semaphore** | A time-based delay only throttles throughput; it doesn't cap concurrent Chromium windows. Under burst load, 10+ windows could still open simultaneously before the delay fires. |
| **`curl-cffi` TLS fingerprint spoofing (as in ADR-059)** | Cloudflare Turnstile on novalpie.cc uses JavaScript challenges, not pure TLS fingerprinting. `curl-cffi` alone cannot solve JS-based challenges. |
| **Scraping the rendered HTML from the Nuxt page directly** | Only viable after JS execution, which requires a headless browser anyway. Adds no benefit over Playwright-based extraction. |

## Decision

### 1. API First, Playwright Fallback
We attempt to hit the fast undocumented JSON API (`/api/novels/{id}/chapters/{chapter_id}` in [`novalpie.py`](file:///d:/code_xI/Translator_Web/backend/services/scrapers/novalpie.py#L208-L224)). If this fails (non-200 status, `JSONDecodeError`, or HTML body instead of JSON — which indicates a Cloudflare intercept), we seamlessly fall back to a headless Playwright browser.

### 2. Synchronous Playwright via `asyncio.to_thread()` with Semaphore
Since Playwright's async API conflicts with Uvicorn/AnyIO's eventloop on Windows, we use `sync_playwright` executed via `asyncio.to_thread()`. To prevent 15 concurrent batch worker tasks from opening 15 Chromium windows simultaneously (causing a CPU/RAM spike and an instant Cloudflare IP ban), Playwright execution is gated by a **class-level `asyncio.Semaphore(2)`** on `NovalpieAdapter._playwright_sem`.

```python
# novalpie.py — class-level semaphore (lines 234–235, 286)
if not hasattr(NovalpieAdapter, "_playwright_sem"):
    NovalpieAdapter._playwright_sem = asyncio.Semaphore(2)

async with NovalpieAdapter._playwright_sem:
    raw_html = await asyncio.to_thread(_run_playwright_sync, direct_url)
```

### 3. Novalpie VIP Check Bypass
The `len(markdown) < 50` VIP heuristic is explicitly **disabled** for `novalpie.cc` URLs. Because Novalpie has no paywalled VIP system, any short content extraction is fundamentally an extraction error (Turnstile challenge or blank page), not a locked chapter. By bypassing the VIP flag, failed chapters are correctly marked as `error` in the database, allowing the user's `fetch_only=True` batch worker to retry them on the next pass via "Fill Missing Content".

### 4. Vue Placeholder Pruning
Novalpie's DOM contains `<img>` elements initialized with Vue's lazy-load failure placeholder text (`图片加载失败`). The `_clean_content()` method in [`novalpie.py`](file:///d:/code_xI/Translator_Web/backend/services/scrapers/novalpie.py#L310-L323) strips these via BeautifulSoup tag decomposition before the final markdown pass, preventing artifact text from bleeding into translated output.

## Consequences

### Positive
- **Improved reliability**: We can bulk-queue 300+ Novalpie chapters. The system rips through unblocked ones instantly via the API, and smoothly throttles to 2-at-a-time for Cloudflare-blocked ones (~15 seconds per blocked chapter) without crashing or triggering an IP ban.
- **Accurate error states**: Intermittent Cloudflare failures no longer poison the database with fake VIP chapters. Users can click "Fill Missing Content" again to retry all `error`-state chapters.
- **Lower CPU overhead**: The semaphore strictly caps headless browser concurrency, preventing Out-Of-Memory errors during massive batch fetching.

### Negative / Trade-offs
- **Heavy optional dependency**: Playwright requires ~150MB of Chromium binaries (`playwright install chromium`). This is a significant footprint addition for an optional fallback path.
- **15-second floor latency per blocked chapter**: Each Playwright pass waits 15 seconds for Cloudflare Turnstile to resolve. Under heavy Cloudflare rate-limiting, this means 300 blocked chapters take ~37.5 minutes at Semaphore(2) concurrency.
- **Windows eventloop coupling**: The `sync_playwright` + `asyncio.to_thread()` pattern is a workaround for Windows. On Linux production servers, the Playwright async API could be used directly, but the current implementation does not take advantage of this.
- **`playwright-stealth` is optional**: The implementation gracefully degrades if `playwright-stealth` is not installed, but without it the Chromium fingerprint is less convincing and Cloudflare detection rates may be higher.

## Related ADRs
- [ADR-098 — Novalpie Novel Crawler and Metadata Adapter](./ADR-098-Novalpie-Novel-Crawler-and-Metadata-Adapter.md) ← base implementation this ADR patches
- [ADR-059 — Novel Updates Cloudflare Bypass via curl-cffi](./ADR-059-Novel-Updates-Cloudflare-Bypass-via-curl-cffi.md) ← prior art for Cloudflare bypass on a different scraper
- [ADR-050 — Handling Cloudflare and AI Safety Filters](./ADR-050-Handling-Cloudflare-and-AI-Safety-Filters.md) ← broader Cloudflare handling strategy
