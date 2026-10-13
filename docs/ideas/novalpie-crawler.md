# Idea Refinement: Novalpie.cc Integrated Novel Crawler & Metadata Adapter

## 1. Problem Statement
**How Might We** enable ReadOmni AI users to seamlessly import Korean/Chinese web novel projects from `novalpie.cc` with a single URL paste—automatically pulling rich novel metadata (cover, title, author, synopsis), fetching the full Table of Contents (TOC), and batch-crawling original chapter texts without dealing with client-side JavaScript rendering barriers?

---

## 2. Technical Feasibility & Site Analysis
- **Framework**: `novalpie.cc` is built on Nuxt 3 (Vue SPA). Standard HTML scraping (e.g. BeautifulSoup `<a>` tag extraction) will see an empty `<div id="__nuxt"></div>`.
- **API Endpoints**: The site exposes direct JSON REST APIs under `https://novalpie.cc/api`:
  - `GET /api/novels/{id}/detail`: Returns novel title, cover URL (`images.novelpia.com`), synopsis, author, and genre tags.
  - `GET /api/novels/{id}/chapters`: Returns structured list of chapter objects (`id`, `chapter_number`, `title`, `is_vip`).
  - Chapter Content API / HTML Reader endpoint.
- **Protection**: No aggressive Cloudflare Turnstile/reCAPTCHA blocking on public novel read routes; straightforward HTTP headers with custom User-Agent are supported.

---

## 3. Recommended Direction: Dedicated `NovalpieAdapter` & Auto-Routing
Create a modular `NovalpieAdapter` inside `backend/services/scrapers/novalpie.py` registered into `MetadataScraperEngine` and `toc.py`:
1. **Auto-Detection via URL**:
   When a user pastes any URL matching `https?://(?:www\.)?novalpie\.cc/(?:book|novel|read)/(\d+)`:
   - System automatically extracts the `novel_id`.
   - Directly calls `novalpie.cc` REST APIs rather than attempting fragile DOM parsing.
2. **Full-Spectrum Ingestion**:
   - **Step 1 (Metadata)**: Fetches cover art, synopsis, genres, and sets author.
   - **Step 2 (TOC Extraction)**: Pulls all chapter IDs and titles into a structured TOC.
   - **Step 3 (Batch Fetcher)**: Integrates with ReadOmni AI's `BulkFetchModal` to stream-download original raw chapter texts.

---

## 4. Key Assumptions
1. `novalpie.cc/api/novels/{id}/chapters` provides access to non-VIP chapters.
2. API responses remain in JSON format without unexpected schema churn.
3. Network connectivity from local backend to `novalpie.cc` remains open and responsive.

---

## 5. MVP Scope
- [x] **Adapter Class**: `NovalpieAdapter` in `backend/services/scrapers/novalpie.py`.
- [x] **Engine Registration**: Register in `backend/services/scrapers/engine.py`.
- [x] **TOC & Scrape Router Support**: Update `backend/routers/toc.py` and `backend/routers/scrape.py` to auto-route `novalpie.cc` URLs.
- [x] **Frontend UX**: Auto-detect `novalpie.cc` in TOC Import Modal and Metadata modal.
- [x] **Unit & Regression Tests**: Pytest coverage for metadata extraction and chapter TOC parsing.

---

## 6. Not Doing (Out of Scope for MVP)
- Bypassing paid/VIP chapter paywalls or logging into private user accounts.
- Writing reverse-comment scraping or user rating scrapers.
