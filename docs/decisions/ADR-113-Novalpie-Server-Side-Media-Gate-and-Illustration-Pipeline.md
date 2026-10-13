# ADR-113: Novalpie Illustration Pipeline, Metadata-Content Asymmetry, and Empirical Authentication Analysis

## Status
Accepted

## Date
2026-10-05

## Context
During the expansion of the Novalpie novel crawler (ADR-112), users observed that certain age-restricted R-18 novels (e.g. *地下城的剑士有发情期 / The Dungeon Knight's Heat Cycle*, Novel ID `350645`) display illustration counts in the Table of Contents (e.g., `EP.1 1图`, `EP.5 3图`, `EP.13 4图`), yet when scraped into Translator_Web, the local thread image gallery and chapter text show zero illustrations (`image_count = 0`).

An in-depth empirical test suite and cryptographic audit of the live Novalpie Nuxt 3 client (`BDyTnbGc.js`, `BOp3s4R4.js`, `BMCgJJg3.js`, `EO6KZzzU.js`) was executed across hundreds of chapters to establish definitive facts.

### Empirical Findings & Discovery

1. **The 720-Hour (30-Day) Gate (`readThresholdValue: 720`)**:
   - Novalpie restricts access to certain novel metadata and chapter ciphertext behind a 720-hour (30-day) account age gate. Unauthenticated requests or accounts younger than 30 days receive `403 ADULT_VERIFICATION_REQUIRED`.
   - User account `SMONE` (registered 2026-08-31, 35 days / 840 hours old) legitimately passed this gate.

2. **Debunking the "60-Day Image Gate" Myth**:
   - An earlier hypothesis suggested Novalpie strips images for accounts younger than 60 days. **Empirical testing proved this hypothesis false.**
   - On novel `352285` (*成为赛博朋克中的龙*), chapters 1 and 2 returned `<img src="https://images.novelpia.com/imagebox/cover/..." alt="插图1">` directly in the decrypted ciphertext for user `SMONE` (whose account was only 35 days old).
   - Code inspection of all Nuxt 3 chunks revealed that the only `60-day` reference (`canUseDownload: e => ... >= 60`) governs the client-side UI button for bulk EPUB/zip downloads, not chapter illustration serving.
   - **Conclusion**: There is no 60-day image restriction. Accounts $\ge 30$ days (720h) receive all illustrations that exist in Novalpie's database.

3. **True Root Cause of 0 Images on Novel 350645**:
   - Automated cryptographic scanning across **all 134 chapters** of novel `350645` revealed that **0 out of 134 chapters contain `<img` tags or image URLs in their decrypted ciphertext**.
   - Novalpie automatically mirrored the Table of Contents metadata (`imageCount: 1`, `imageCount: 3`, `trueId: 3631015`) from Novelpia Korea (`novelpia.com/novel/286052`).
   - However, the uploader/translation bot that populated the Chinese text onto Novalpie only scraped the textual paragraphs, leaving `<br><br><br>` line breaks in place of illustrations without actually uploading or linking the image files into Novalpie's chapter bodies.
   - Consequently, Translator_Web accurately records `image_count = 0` because no images exist in the source content provided by Novalpie.

4. **Multi-CDN and Illustration Placeholder Variations**:
   - When images are present (e.g. novel `352285`), Novalpie's Nuxt reader (`BMCgJJg3.js`) rewrites CDN aliases (`jpg.freenovel.sbs`, Cloudflare R2, `novelkit.top`) into `//images.novelpia.com/imagebox/{prefix}/{hash}`.
   - The editor component (`B4Uh-Fw_.js` / `EO6KZzzU.js`) supports placeholder syntax `[[img: 1]]` or `[[img: hash]]`.

---

## Decision

We formalized the **End-to-End Novalpie Scraper & Media Pipeline** across four architectural pillars:

### 1. Direct Playwright Chapter Ingestion (`backend/services/scrapers/novalpie.py`)
- Removed the deprecated, failing HTTPX REST attempt (`/api/novels/{id}/chapters/{id}` which always returned 404).
- Chapters are fetched directly through the thread-local Playwright browser pool, executing full Turnstile bypass, Nuxt 3 hydration, and WebCrypto decryption in a single pass.

### 2. Multi-CDN Normalization & Placeholder Resolution
- In `NovalpieAdapter._parse_chapter_html`:
  - Automatically transforms protocol-relative (`//images.novelpia.com/...`) and site-relative (`/...`) paths to absolute URLs.
  - Rewrites Novalpie alternative CDN domains:
    - `https://photo.1695ffc38d5faf9827f7fbd055757d56.r2.cloudflarestorage.com/` $\to$ `https://images.novelpia.com/imagebox/...`
    - `https://novelkit.top/images/` $\to$ `https://images.novelpia.com/imagebox/...`
    - `https://jpg.freenovel.sbs/{hash}` $\to$ `https://images.novelpia.com/imagebox/{hash[:2]}/{hash}`
  - Employs regex resolution for `[[img:hash]]` and `[[image:hash]]` tokens into standard Markdown image tags (`![插图](...)`).

### 3. Dynamic Parallel Concurrency in Batch Processing (`backend/services/background_translator.py`)
- For `fetch_only=True` batches (Bulk Fetch), worker allocation is uncoupled from LLM API key constraints.
- Worker count scales directly to `GlobalSetting.scraper_concurrency` (1 to 5 concurrent tabs), governed by `NovalpieAdapter.get_semaphore()`.

---

## Consequences

### Positive
- Scraper operates at maximum throughput (up to 5 concurrent Playwright workers without bottlenecking on artificial AI concurrency limits).
- Fully supports all Novalpie CDN mirrors and placeholder formats, preventing broken images when server emits CDN aliases.
- Verified that accounts $\ge 30$ days already have full image extraction capabilities on any novel where images were actually mirrored to Novalpie.

### Negative / Trade-offs
- Novels where the Novalpie uploader omitted image uploads during translation (like `350645`) will have 0 images despite TOC badges stating otherwise.

---

## Related ADRs
- [ADR-098 — Novalpie Novel Crawler and Metadata Adapter](./ADR-098-Novalpie-Novel-Crawler-and-Metadata-Adapter.md)
- [ADR-099 — Novalpie Headless Fallback and Cloudflare Bypass](./ADR-099-Novalpie-Headless-Fallback-and-Cloudflare-Bypass.md)
- [ADR-101 — Configurable Scraper Concurrency and Browser Context Reuse](./ADR-101-Configurable-Scraper-Concurrency-and-Browser-Context-Reuse.md)
- [ADR-103 — One-Click Thread Image Cacher and Reader Proxy](./ADR-103-One-Click-Thread-Image-Cacher-and-Reader-Proxy.md)
- [ADR-112 — Novalpie Dual-Mode Authenticated Scraper](./ADR-112-Novalpie-Dual-Mode-Authenticated-Scraper.md)
