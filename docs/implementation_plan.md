# Implementation Plan: AI Translator Web (ReadOmni Clone)

> **Dibuat:** 16 Mei 2026  
> **Status:** 🟡 Phase 1 — Foundation  
> **Dikerjakan oleh:** Agent-Driven Development

---

## Overview

Membangun web app penerjemah mandiri (self-hosted) yang merupakan klon fungsional dari app.readomni.com. Aplikasi berfokus pada pembacaan dan penerjemahan web novel serta EPUB dengan AI lokal (LM Studio). Memiliki sistem "Lorebook" per thread untuk menjaga konsistensi nama/istilah dalam terjemahan.

## Arsitektur Sistem

```
Frontend (React + Vite + Tailwind)
        │
        │ HTTP / REST API
        │
Backend (Python FastAPI)
   ├── Scraping Engine (Crawl4AI)
   ├── EPUB Parser (EbookLib)
   ├── AI Translation Service → LM Studio (localhost:1234)
   └── SQLite Database
            ├── threads
            ├── chapters
            └── lorebook_entries
```

## Dependency Graph

```
SQLite Schema
    │
    ├── FastAPI Models & Endpoints
    │       │
    │       ├── /api/scrape      → Web Scraping
    │       ├── /api/upload-epub → EPUB Parsing
    │       ├── /api/translate   → AI Translation
    │       ├── /api/threads     → Thread Management
    │       └── /api/lorebook    → Context/Lorebook
    │
    └── React Frontend
            ├── Layout Shell (Sidebar + Header)
            ├── TranslatePage (Input URL/EPUB + Result)
            ├── ContextLibraryPage (Lorebook CRUD)
            ├── LibraryPage (Daftar thread/buku)
            └── SettingsPage (LM Studio URL, Model)
```

---

## Phase 1: Foundation (Project Setup)

### Task 1: Perbaiki Design System Frontend

**Deskripsi:** Selaraskan token warna di `index.css` dengan palette ReadOmni yang sudah didokumentasikan di `docs/style.md`. Warna saat ini tidak sesuai (masih pakai cyan/slate bawaan Tailwind).

**Acceptance Criteria:**
- [ ] `--background` menggunakan `#151619`
- [ ] `--primary` menggunakan `#e2e6e9`
- [ ] Class `.glass` memakai warna surface dari palette ReadOmni
- [ ] Tidak ada warna hardcoded di komponen (semua lewat CSS variable)

**Verification:** `npm run dev` → visual check background dan sidebar color.  
**Dependencies:** None  
**Files:** `src/index.css`  
**Scope:** XS

---

### Task 2: Setup Backend FastAPI + SQLite Schema

**Deskripsi:** Inisialisasi project Python FastAPI di folder `backend/`. Definisikan skema SQLite dengan SQLAlchemy untuk tabel `threads`, `chapters`, dan `lorebook_entries`.

**Acceptance Criteria:**
- [ ] FastAPI server berjalan di `http://localhost:8000`
- [ ] SQLite file `app.db` terbuat otomatis saat startup
- [ ] 3 tabel terbuat: `threads`, `chapters`, `lorebook_entries`
- [ ] Endpoint `GET /` mengembalikan `{"status": "ok"}`

**Verification:** `uvicorn main:app --reload` → buka `http://localhost:8000/docs`  
**Dependencies:** None  
**Files:** `backend/main.py`, `backend/models.py`, `backend/database.py`, `backend/requirements.txt`  
**Scope:** Medium

---

### ✅ Checkpoint 1: Foundation
- [ ] Frontend berjalan (`npm run dev`)
- [ ] Backend berjalan (`uvicorn`)
- [ ] Warna sudah sesuai ReadOmni design system
- [ ] Database terbuat otomatis

---

## Phase 2: Core Features (UI Shell & Ingestion)

### Task 3: Refactor UI Shell menjadi Komponen Modular

**Deskripsi:** Pecah `App.tsx` yang monolitik menjadi komponen-komponen terpisah: `Layout`, `Sidebar`, `Header`. Buat halaman `TranslatePage`, `ContextLibraryPage`, `LibraryPage`, `SettingsPage` sebagai file terpisah.

**Acceptance Criteria:**
- [ ] Sidebar bisa collapse di mobile (hamburger menu)
- [ ] Navigasi antar tab berfungsi
- [ ] Setiap halaman ada file `.tsx` sendiri di `src/pages/`
- [ ] Komponen UI ada di `src/components/`

**Verification:** Buka di Chrome DevTools → test mobile viewport 375px  
**Dependencies:** Task 1  
**Files:** `src/components/Layout.tsx`, `src/components/Sidebar.tsx`, `src/pages/TranslatePage.tsx`, `src/pages/ContextLibraryPage.tsx`, `src/pages/LibraryPage.tsx`, `src/pages/SettingsPage.tsx`  
**Scope:** Medium

---

### Task 4: Web Scraping Endpoint (Backend)

**Deskripsi:** Buat endpoint `POST /api/scrape` menggunakan Crawl4AI. Menerima URL, scrape halaman, bersihkan dari iklan/nav, kembalikan konten Markdown bersih.

**Acceptance Criteria:**
- [ ] Endpoint menerima `{"url": "https://..."}`
- [ ] Mengembalikan `{"markdown": "...", "title": "..."}`
- [ ] Konten bersih dari tag script, nav, ads
- [ ] Error handling jika URL tidak valid

**Verification:** Test via Swagger UI (`/docs`) dengan URL web novel  
**Dependencies:** Task 2  
**Files:** `backend/routers/scrape.py`  
**Scope:** Small

---

### Task 5: EPUB Upload & Parsing Endpoint (Backend)

**Deskripsi:** Buat endpoint `POST /api/upload-epub` yang menerima file EPUB, parse dengan `EbookLib`, pisahkan menjadi chapter-chapter, simpan ke database.

**Acceptance Criteria:**
- [ ] Endpoint menerima file upload multipart
- [ ] Membuat 1 record `thread` baru di database
- [ ] Setiap chapter tersimpan sebagai record `chapter` yang terhubung ke thread
- [ ] Mengembalikan daftar chapter yang berhasil di-parse

**Verification:** Upload EPUB sample via Swagger → cek database SQLite  
**Dependencies:** Task 2  
**Files:** `backend/routers/epub.py`, `backend/utils/epub_parser.py`  
**Scope:** Medium

---

### Task 6: Frontend — Form Input & Koneksi ke Backend

**Deskripsi:** Hubungkan form input di `TranslatePage` ke backend. Input URL → panggil `/api/scrape`. Upload EPUB → panggil `/api/upload-epub`. Tampilkan konten yang berhasil di-extract di panel kiri.

**Acceptance Criteria:**
- [ ] Input URL dengan tombol "Extract" memanggil API dan menampilkan markdown
- [ ] Drag & drop / file picker untuk EPUB berfungsi
- [ ] Loading state ditampilkan saat fetching
- [ ] Error message jika API gagal

**Verification:** End-to-end test: paste URL → lihat konten muncul di panel kiri  
**Dependencies:** Task 3, Task 4, Task 5  
**Files:** `src/pages/TranslatePage.tsx`, `src/lib/api.ts`  
**Scope:** Medium

---

### ✅ Checkpoint 2: Core Features
- [ ] User bisa paste URL dan mendapatkan konten
- [ ] User bisa upload EPUB dan melihat chapter list
- [ ] Semua API endpoints ditest via Swagger
- [ ] UI responsif di mobile dan desktop

---

## Phase 3: Translation & Lorebook

### Task 7: Translation Service & Endpoint (Backend)

**Deskripsi:** Buat service yang menghubungkan FastAPI ke LM Studio (`http://localhost:1234/v1/chat/completions`). Endpoint `POST /api/translate` menerima teks + `thread_id` (untuk inject Lorebook sebagai system prompt).

**Acceptance Criteria:**
- [ ] FastAPI bisa memanggil LM Studio API lokal
- [ ] System prompt secara otomatis menyertakan terms dari Lorebook thread
- [ ] Teks di-chunk jika melebihi batas token yang aman
- [ ] Streaming response didukung (Server-Sent Events)

**Verification:** Call `/api/translate` → pastikan LM Studio menerima request + Lorebook context  
**Dependencies:** Task 2  
**Files:** `backend/services/ai_translation.py`, `backend/routers/translate.py`  
**Scope:** Medium

---

### Task 8: Lorebook CRUD (Backend + Frontend)

**Deskripsi:** Buat endpoint CRUD untuk `lorebook_entries` (GET, POST, DELETE per `thread_id`). Bangun UI di `ContextLibraryPage` untuk tambah, lihat, dan hapus term.

**Acceptance Criteria:**
- [ ] `GET /api/threads/{id}/lorebook` — list terms
- [ ] `POST /api/threads/{id}/lorebook` — tambah term
- [ ] `DELETE /api/lorebook/{entry_id}` — hapus term
- [ ] UI menampilkan list terms dengan form tambah term
- [ ] Thread selector tersedia (pilih buku/project mana)

**Verification:** Tambah term "Xianxia → Kultiasi Abadi" → trigger translate → pastikan term muncul di system prompt  
**Dependencies:** Task 2, Task 3  
**Files:** `backend/routers/lorebook.py`, `src/pages/ContextLibraryPage.tsx`  
**Scope:** Medium

---

### Task 9: Translation UI — Side-by-Side View + Streaming

**Deskripsi:** Hubungkan panel kanan di `TranslatePage` ke endpoint `/api/translate`. Implementasikan streaming output agar terjemahan muncul bertahap (bukan nunggu selesai semua). Tambahkan tombol "Translate" dan indikator progress.

**Acceptance Criteria:**
- [ ] Tombol "Translate" aktif setelah konten di-load
- [ ] Terjemahan muncul bertahap (streaming)
- [ ] User bisa pilih chapter dari EPUB yang sudah diupload
- [ ] Model selector tersedia (ambil dari LM Studio API)

**Verification:** End-to-end: Extract URL → Translate → lihat terjemahan streaming di panel kanan  
**Dependencies:** Task 6, Task 7  
**Files:** `src/pages/TranslatePage.tsx`  
**Scope:** Medium

---

### Task 10: Library Page — Thread & Chapter Management

**Deskripsi:** Bangun `LibraryPage` untuk menampilkan semua thread/buku yang sudah diimpor. User bisa klik buku → lihat daftar chapter → pilih chapter untuk diterjemahkan.

**Acceptance Criteria:**
- [ ] Grid/list view semua thread
- [ ] Klik thread → tampilkan chapter list
- [ ] Klik chapter → navigasi ke TranslatePage dengan chapter ter-load
- [ ] Bisa hapus thread beserta semua data-nya

**Verification:** Import EPUB → lihat di Library → klik chapter → translate  
**Dependencies:** Task 5, Task 9  
**Files:** `src/pages/LibraryPage.tsx`, `backend/routers/threads.py`  
**Scope:** Medium

---

### ✅ Checkpoint 3: Complete
- [ ] User bisa extract URL + translate hasilnya
- [ ] User bisa upload EPUB + translate per chapter
- [ ] Lorebook berfungsi menjaga konsistensi nama/istilah
- [ ] Library menampilkan semua buku yang sudah diimpor
- [ ] Semua fitur berjalan di mobile

---

## Phase 4: Polish & Settings

### Task 11: Settings Page (Konfigurasi LM Studio)

**Deskripsi:** Halaman Settings untuk mengkonfigurasi URL LM Studio dan memilih model. Settings disimpan di `localStorage` frontend.

**Acceptance Criteria:**
- [ ] Input field untuk LM Studio base URL
- [ ] Dropdown untuk memilih model (ambil dari `/v1/models`)
- [ ] Test connection button
- [ ] Tersimpan otomatis ke localStorage

**Files:** `src/pages/SettingsPage.tsx`  
**Scope:** Small

---

### Task 12: README & Docs Update

**Deskripsi:** Update `README.md` project menjadi panduan developer yang nyata. Sinkronisasi semua docs (`SDLC.md`, `Handoff.md`) dengan status implementasi terkini.

**Files:** `README.md`, `docs/SDLC.md`, `docs/Handoff.md`  
**Scope:** XS

---

## Risks & Mitigations

| Risiko | Impact | Mitigasi |
|:---|:---|:---|
| Website sumber di-block Cloudflare | Tinggi | Fallback ke paste manual; Crawl4AI punya mode stealth |
| EPUB format tidak standar | Sedang | Tambahkan fallback parser BeautifulSoup untuk EPUB internal HTML |
| LM Studio token overflow | Tinggi | Chunking otomatis per paragraf, max 2000 token per request |
| CORS error Frontend ↔ Backend | Rendah | Konfigurasi `allow_origins` di FastAPI |

---

## Status Tracking

| Task | Status | Catatan |
|:---|:---|:---|
| Task 1: Design System | ✅ Selesai | `src/index.css` — ReadOmni tokens applied |
| Task 2: Backend Setup | ✅ Selesai | `backend/main.py`, `database.py`, `requirements.txt` dibuat |
| Task 3: UI Shell Refactor | ✅ Selesai | 6 files: Layout, Sidebar, 4 pages |
| Task 4: Scraping Endpoint | ✅ Selesai | `backend/routers/scrape.py` |
| Task 5: EPUB Parser | ✅ Selesai | `backend/routers/epub.py` |
| Task 6: Frontend API Connect | ✅ Selesai | Form input terhubung ke endpoint Scrape & EPUB |
| Task 7: Translation Service | ✅ Selesai | `backend/routers/translate.py` |
| Task 8: Lorebook CRUD | ✅ Selesai | `backend/routers/lorebook.py` |
| Task 9: Translation UI Streaming | ✅ Selesai | Implementasi SSE Fetch di TranslatePage |
| Task 10: Library Page | ✅ Selesai | Fetch threads dan Lorebook data secara dinamis |
| Task 11: Settings Page | ✅ Selesai | LM Studio URL, model selector, test connection |
| Task 12: Docs Update | ✅ Selesai | README, SDLC, Handoff, style.md semua diperbarui |
