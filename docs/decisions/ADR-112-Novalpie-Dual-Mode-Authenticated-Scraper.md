# ADR-112: Novalpie Dual-Mode Authenticated Scraper for Age-Restricted Novels and Chapter Illustrations

## Status
Accepted

## Date
2026-10-04

## Context
Novalpie.cc (Nuxt 3 / Vue SPA) imposes strict server-side account age restrictions on certain novels and chapter content:
1. **Restricted Novels / Sections**: Requires an active user account registered for $\ge 720$ hours (30 days). Unauthenticated guest requests to chapter content (`/api/chapters/{id}/content`) receive `403 Forbidden` / access denied errors.
2. **Chapter Illustrations / Manhwa Media**: Requires an account aged $\ge 60$ days. Otherwise, chapter image tags are stripped by the backend API or blocked from rendering.

Previously, `NovalpieAdapter` ran exclusively in guest mode (anonymous Playwright Chromium browser contexts without cookies and unauthenticated HTTPX clients). Furthermore, reverse-engineering confirmed that Novalpie uses cryptographically signed Bearer tokens (`auth_token`) stored in cookies/localStorage, and server-side AES-GCM decryption routines (`BOp3s4R4.js`). Artificial client-side bypasses (faking account age without an account) are mathematically impossible because the registration timestamp `created_at` is evaluated on Novalpie's database.

## Decision

We implemented a **Dual-Mode (Guest vs. Authenticated) Scraper Architecture**:

### 1. Database Schema & Secrets Management (`backend/database.py`, `backend/services/ai/secrets.py`, `backend/routers/settings.py`)
- Added `novalpie_auth_enabled: Mapped[int] = mapped_column(default=0)` (0 = Guest mode, 1 = Authenticated mode) in `GlobalSetting`.
- **Security-First Token Storage (`.env`)**: To prevent private session tokens from ever leaking into public Git commits or database exports, `novalpie_cookie` is saved exclusively to `backend/.env` (under `NOVALPIE_COOKIE`), which is strictly gitignored. SQLite stores only the toggle flag (`novalpie_auth_enabled`) while the token column is sanitized/empty.
- Exposed securely through `GET /api/settings` and `POST /api/settings` via `load_secrets()` and `save_secrets()`.

### 2. Dual-Mode Scraper Engine (`backend/services/scrapers/novalpie.py`)
- **`get_novalpie_auth_config()`**: Resolves whether authentication is active, parses cookie strings (`name=value; ...`) or raw Bearer tokens into structured Playwright cookies and HTTP headers.
- **HTTPX REST API Integration**: Injects `Cookie: auth_token=...` and `Authorization: Bearer <auth_token>` into `get_request_headers()` for metadata (`/api/novels/{id}/detail`) and TOC (`/api/novels/{id}/chapters`) endpoints.
- **Direct Playwright Chapter Ingestion**: Because Novalpie's origin Laravel backend does not serve unencrypted chapter content over REST API (`/api/novels/{id}/chapters/{chapter_id}` always returns 404), chapter content scraping now routes directly into Playwright. This eliminates an unnecessary failing HTTP roundtrip on every chapter, cutting bulk fetch latency significantly.
- **Playwright Chromium Ingestion**:
  - Automatically calls `context.add_cookies(pw_cookies)` on the thread-local browser context.
  - Injects `localStorage.setItem("auth_token", token)` via `context.add_init_script(...)` so Nuxt 3's authentication helper (`Yn.get()`) detects the user session instantly upon initialization.
- **Media Preservation & CDN Normalization**: Enhanced `_parse_chapter_html` to normalize protocol-relative (`//images.novelpia.com/...`) and relative image paths, as well as Novalpie's alternative CDN domains (`jpg.freenovel.sbs`, Cloudflare R2, `novelkit.top`) into canonical `images.novelpia.com/imagebox/` URLs. Also added pattern resolution for `[[img:hash]]` placeholders into markdown images.
- **Batch Worker Scraper Concurrency**: Updated `BackgroundTranslator._run_batch_worker` to dynamically scale task concurrency using `scraper_concurrency` (1–5) whenever `fetch_only=True`, ensuring bulk fetching runs at full parallel worker capacity rather than falling back to AI LLM provider limits.

### 3. Dual UI Controls (`SettingsPage.tsx`, `BulkFetchModal.tsx`)
- **Settings Page**: Added an account authentication card inside the Web Crawler section with mode indicator badges (`Mode Akun (720h/60d)` vs `Mode Tamu (Guest)`), switch toggle, and token textarea.
- **Bulk Fetch Modal**: Added a quick toggle button in the modal footer dialog so users can switch between Guest and Authenticated modes right before initiating bulk chapter downloads.

## Consequences

### Positive
- Fully unlocks age-restricted novels (720h) and illustrations (60d) for users who provide their own mature account token.
- Retains guest mode by default, preserving zero-setup accessibility for public novels.
- Fully compatible with dynamic concurrency (`scraper_concurrency`) and thread-local browser reuse (ADR-101) without race conditions.
- 100% backward-compatible: all 244 backend unit and integration tests pass cleanly.

### Negative / Trade-offs
- Users must manually retrieve and paste their session cookie/token from browser DevTools.
- Session tokens may expire after extended inactivity, requiring the user to refresh the token in Settings.

## Related ADRs
- [ADR-098 — Novalpie Novel Crawler and Metadata Adapter](./ADR-098-Novalpie-Novel-Crawler-and-Metadata-Adapter.md)
- [ADR-099 — Novalpie Headless Fallback and Cloudflare Bypass](./ADR-099-Novalpie-Headless-Fallback-and-Cloudflare-Bypass.md)
- [ADR-101 — Configurable Scraper Concurrency and Browser Context Reuse](./ADR-101-Configurable-Scraper-Concurrency-and-Browser-Context-Reuse.md)
- [ADR-103 — One-Click Thread Image Cacher and Reader Proxy](./ADR-103-One-Click-Thread-Image-Cacher-and-Reader-Proxy.md)
