# Implementation Plan: AI Translator Web (ReadOmni Clone)

> **Dibuat:** 16 Mei 2026  
> **Status:** ✅ Phase 10 — Batch Translation Studio & Smart Extraction (Complete)  
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

**Deskripsi:** Halaman Settings untuk mengkonfigurasi URL LM Studio dan memilih model. Settings disimpan di `localStorage` frontend (sebelum migrasi server-side).

**Acceptance Criteria:**
- [x] Input field untuk LM Studio base URL
- [x] Dropdown untuk memilih model (ambil dari `/v1/models`)
- [x] Test connection button
- [x] Tersimpan otomatis ke localStorage

**Files:** `src/pages/SettingsPage.tsx`  
**Scope:** Small

---

### Task 12: README & Docs Update

**Deskripsi:** Update `README.md` project menjadi panduan developer yang nyata. Sinkronisasi semua docs (`SDLC.md`, `Handoff.md`) dengan status implementasi terkini.

**Files:** `README.md`, `docs/SDLC.md`, `docs/Handoff.md`  
**Scope:** XS

---

## Phase 5: UI/UX Overhaul & Background Persistence

### Task 13: Multi-Theme Implementation (Omni/Sepia/OLED)

**Deskripsi:** Menerapkan desain visual yang sepenuhnya responsif dan mendukung multi-tema (Omni, Sepia, OLED) secara elegan menggunakan CSS variables di `index.css` tanpa hardcoding warna.

**Acceptance Criteria:**
- [x] Variabel CSS untuk `--background`, `--foreground`, dan aksen untuk masing-masing tema
- [x] Reader view merespons pergantian tema secara dinamis
- [x] Overlay settings di ReaderPage terintegrasi dengan pemilih tema visual

**Files:** `src/index.css`, `src/pages/ReaderPage.tsx`, `docs/style.md`  
**Scope:** Medium (ADR-006)

---

### Task 14: Server-Side Configuration Persistence

**Deskripsi:** Memindahkan konfigurasi LM Studio dan preferensi prefetching dari localStorage ke database SQLite backend untuk memastikan sinkronisasi multi-perangkat yang mulus (Desktop ke HP).

**Acceptance Criteria:**
- [x] Model database `GlobalSetting` dibuat di SQLite
- [x] Endpoint API GET/PUT untuk konfigurasi global
- [x] Sinkronisasi otomatis URL LM Studio, Active Model, dan rentang prefetch

**Files:** `backend/models.py`, `backend/routers/settings.py`, `src/pages/SettingsPage.tsx`  
**Scope:** Medium (ADR-008)

---

## Phase 6: Bulk Title Translation & Navigation Polish

### Task 15: Bulk Title Translation Engine

**Deskripsi:** Membangun sistem translasi judul novel/bab secara massal menggunakan asinkronitas latar belakang untuk mendukung novel dengan ratusan bab tanpa kegagalan koneksi.

**Acceptance Criteria:**
- [x] Skema basis data dual-title (judul asli + judul terjemahan)
- [x] Endpoint `POST /api/threads/{id}/translate-titles` dengan asinkronitas latar belakang
- [x] Kemampuan memoles judul bab secara bertahap tanpa memblokir pembacaan

**Files:** `backend/routers/translate.py`, `backend/services/background_translator.py`  
**Scope:** Medium (ADR-007)

---

### Task 16: Navigation UX Polish

**Deskripsi:** Memperbaiki perpindahan bab agar berjalan instan tanpa adanya flickering visual yang mengganggu mata pembaca saat berganti bab novel.

**Acceptance Criteria:**
- [x] Transisi bab yang mulus di ReaderPage
- [x] Render halaman terjemahan dan asli secara konsisten

**Files:** `src/pages/ReaderPage.tsx`  
**Scope:** Small (ADR-011)

---

## Phase 7: Stability & Reliability Guardrails

### Task 17: Stability Optimization (Chunking & Timeouts)

**Deskripsi:** Menerapkan pembatasan chunk (ukuran 50 judul) dan jeda tidur pada GPU lokal untuk menghindari LM Studio throttling. Meningkatkan timeout HTTP backend menjadi 300s. Menghapus Husky git hooks untuk menstabilkan proses commit.

**Acceptance Criteria:**
- [x] Judul diproses per 50 item dengan jeda `asyncio.sleep(1.0)`
- [x] Koneksi HTTP ke LM Studio diset dengan timeout 300s
- [x] Husky dihapus sepenuhnya dari `package.json` dan repo git

**Files:** `backend/services/background_translator.py`, `package.json`  
**Scope:** Small (ADR-011)

---

### Task 18: Race Condition Control (AbortController)

**Deskripsi:** Mengintegrasikan `AbortController` pada pemanggilan API React frontend untuk membatalkan request penerjemahan sebelumnya secara otomatis apabila pembaca berpindah bab secara cepat.

**Acceptance Criteria:**
- [x] Sinyal abort dikirim ke fetch request saat komponen unmount atau chapter berubah
- [x] Tidak ada tabrakan teks bab lama dan baru di panel pembaca

**Files:** `src/pages/ReaderPage.tsx`  
**Scope:** Small (ADR-011)

---

## Phase 8: Advanced Monitoring & Performance

### Task 19: Background Prefetch System

**Deskripsi:** Mengembangkan fitur prefetching latar belakang sekuensial yang dapat dikonfigurasi (1-5 bab) untuk memastikan bab novel berikutnya telah diterjemahkan sebelum pembaca membukanya.

**Acceptance Criteria:**
- [x] Slider pemilih rentang prefetch (1-5 bab) di halaman Settings dan ReaderPage overlay
- [x] Logika antrean latar belakang sekuensial yang ramah memori lokal GPU

**Files:** `backend/services/background_translator.py`, `src/pages/ReaderPage.tsx`  
**Scope:** Medium (ADR-013)

---

### Task 20: Real-time Polling & UI Progress Indicators

**Deskripsi:** Membuat indikator progres visual di daftar bab dan polling dinamis (5 detik) untuk memberikan feedback kepada pengguna saat bab latar belakang sedang diterjemahkan.

**Acceptance Criteria:**
- [x] Tampilan badge "Translating..." dan "Prefetched" di sidebar daftar bab
- [x] Polling berkala yang mendeteksi selesainya background tasks secara otomatis

**Files:** `src/pages/ReaderPage.tsx`, `src/components/ChapterList.tsx`  
**Scope:** Small (ADR-013)

---

## Phase 9: Premium Book Export

### Task 21: Book Builder Router & Service

**Deskripsi:** Membangun layanan ekspor buku di backend Python untuk menyusun bab-bab terjemahan menjadi file EPUB rapi (atau TXT) lengkap dengan custom cover dan metadata.

**Acceptance Criteria:**
- [x] Pembuatan EPUB menggunakan EbookLib dengan gaya dan struktur bab profesional
- [x] Endpoint `POST /api/threads/{id}/export` menerima cover image Base64 dan detail penulis

**Files:** `backend/routers/export.py`, `backend/services/epub_exporter.py`  
**Scope:** Large (ADR-014)

---

### Task 22: Selective Export UI Modal

**Deskripsi:** Membuat modal antarmuka premium di frontend dengan visual glassmorphism untuk mengonfigurasi opsi ekspor novel, mengunggah cover kustom, dan memilih bab tertentu yang ingin diekspor.

**Acceptance Criteria:**
- [x] Dialog modal Glassmorphic interaktif dengan opsi upload sampul
- [x] Opsi filter bab: "Select All" atau "Select Translated Only"

**Files:** `src/components/ExportModal.tsx`, `src/pages/LibraryPage.tsx`  
**Scope:** Medium (ADR-014)

---

## Phase 10: Batch Translation Studio

### Task 23: Batch Studio Workspace

**Deskripsi:** Menyediakan dasbor Studio Penerjemahan Massal khusus yang mendukung mode Mudah (preset Quick/Normal/Deep scan) dan Lanjutan untuk pemrosesan paralel yang aman.

**Acceptance Criteria:**
- [x] Halaman antarmuka khusus Studio Penerjemahan Massal
- [x] Pilihan bab manual/checklist interaktif dan visualisasi Status Center real-time
- [x] Aturan "Mandatory Overwrite" untuk menjamin konsistensi setelah glosarium diubah

**Files:** `src/pages/BatchStudioPage.tsx`, `backend/routers/batch.py`  
**Scope:** Large (ADR-015)

---

### Task 24: Smart Context & AI Extract Recommendation

**Deskripsi:** Mengintegrasikan logika AI Extract First yang dinamis. Jika Lorebook suatu thread memiliki < 40 entri, AI ekstraksi glosarium akan diprioritaskan sebelum penerjemahan massal dimulai. Ekstraksi dimulai dari posisi chapter terakhir dibaca secara asinkron sekuensial.

**Acceptance Criteria:**
- [x] Pengecekan jumlah Lorebook (>40 vs <40 entries) untuk merekomendasikan ekstraksi AI
- [x] Pemindaian cerdas bertahap berbasis posisi `last_read` chapter bookmark

**Files:** `backend/services/context_engine.py`, `backend/routers/batch.py`  
**Scope:** Medium (ADR-015)

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
| Task 13: Multi-Theme Implementation | ✅ Selesai | Tema Omni/Sepia/OLED dengan CSS variables (ADR-006) |
| Task 14: Server Settings Sync | ✅ Selesai | Migrasi data setting ke database SQLite server-side (ADR-008) |
| Task 15: Bulk Title Translation | ✅ Selesai | Database dual-title & endpoint asinkron (ADR-007) |
| Task 16: Navigation UX Polish | ✅ Selesai | Menghilangkan kedipan saat pergantian bab pembaca |
| Task 17: Stability Optimization | ✅ Selesai | Chunking 50 judul, sleep 1.0s, timeout 300s, hapus Husky (ADR-011) |
| Task 18: Race Condition Controller | ✅ Selesai | Integrasi AbortController pada React fetch (ADR-011) |
| Task 19: Background Prefetch Range | ✅ Selesai | Slider prefetch 1-5 bab di settings & reader overlay (ADR-013) |
| Task 20: Polling & progress badges | ✅ Selesai | Indikator visual di daftar bab & polling dinamis 5s (ADR-013) |
| Task 21: Book Exporter Service | ✅ Selesai | Python EPUB exporter with custom metadata & cover support (ADR-014) |
| Task 22: Selective Export UI Modal | ✅ Selesai | Dialog Glassmorphic dengan seleksi bab kustom (ADR-014) |
| Task 23: Batch Studio Workspace | ✅ Selesai | Antarmuka khusus batch translation massal (ADR-015) |
| Task 24: Smart Context Engine | ✅ Selesai | Logika rekomendasi AI Extract First berdasarkan lorebook (ADR-015) |
