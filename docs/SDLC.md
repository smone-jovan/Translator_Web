# SDLC — AI Translator Web (ReadOmni Clone)

> **Terakhir diperbarui:** 16 Mei 2026  
> **Status Aktif:** Phase 1 — Foundation  
> **Lihat rencana detail:** [`docs/implementation_plan.md`](./implementation_plan.md)

---

## 1. Planning & Analysis

**Goal:** Self-hosted web app untuk membaca dan menerjemahkan web novel & EPUB menggunakan AI lokal.

**Fitur Inti:**
1. Web Scraping (URL → Markdown bersih via Crawl4AI)
2. EPUB Management (Upload → per-chapter parsing)
3. AI Translation (via LM Studio lokal, `localhost:1234`)
4. Context/Lorebook Memory (term consistency per thread)

**Tech Stack:**
| Layer | Teknologi | Alasan |
|:---|:---|:---|
| Frontend | React 19 + Vite + TailwindCSS v4 | Sudah diinisialisasi, cepat |
| Backend | Python 3.11 + FastAPI | Ecosystem AI/ML terbaik |
| Scraping | Crawl4AI | Output Markdown bersih, LLM-friendly |
| EPUB | EbookLib (Python) | Presisi parsing per chapter |
| Database | SQLite (SQLAlchemy) | Ringan, cukup untuk self-hosted |
| AI | LM Studio (OpenAI-compatible API) | Self-hosted, privacy |

**Target Platform:** Web — Responsive / Mobile-first.

---

## 2. Design

**Arsitektur:** Client-Server.
- Frontend React memanggil FastAPI backend via REST.
- FastAPI mengorkestrasi Crawl4AI, EbookLib, dan LM Studio.

**UI/UX:**
- Klon visual ReadOmni (glassmorphism, sidebar nav, dark mode).
- Design tokens didefinisikan di [`docs/style.md`](./style.md).

---

## 3. Implementation Phases

| Phase | Fokus | Status |
|:---|:---|:---|
| **Phase 1** | Foundation: Design system, Backend setup, DB schema | 🟡 Sedang berjalan |
| **Phase 2** | Core: UI Shell, Scraping, EPUB, API connect | ⬜ Belum |
| **Phase 3** | Translation: LM Studio, Lorebook, Streaming | ⬜ Belum |
| **Phase 4** | Polish: Settings, Library, Docs | ⬜ Belum |

Detail task ada di [`docs/implementation_plan.md`](./implementation_plan.md).

---

## 4. Testing

- **Unit test:** Parsing logic (EPUB chapter splitting, Markdown cleaning).
- **API test:** Semua endpoint via FastAPI Swagger UI (`/docs`).
- **UI test:** Chrome DevTools — viewport 375px (mobile), 1280px (desktop).
- **E2E test:** URL extract → Translate → Lorebook inject → Result.

---

## 5. Deployment

- Self-hosted di mesin lokal (atau Docker).
- LM Studio harus berjalan di port `1234` sebelum backend distart.
- Docker Compose planned untuk orkestrasi `frontend + backend + nginx`.

---

## Catatan Developer

- Frontend ada di `/src`, jalankan dengan `npm run dev`.
- Backend (planned) ada di `/backend`, jalankan dengan `uvicorn main:app --reload`.
- Semua konfigurasi LM Studio disimpan di `localStorage` frontend (Settings page).
