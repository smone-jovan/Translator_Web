# ReadOmni AI (Translator Web) — Architecture Overview & Entry Points

Dokumen ini adalah ringkasan arsitektur tingkat tinggi sebagai pintu masuk bagi developer dan AI Agent baru.

---

## 🏛️ 1. Arsitektur Sistem

ReadOmni AI mengadopsi arsitektur terpisah antara antarmuka modern (Client-Side SPA) dan pemrosesan latar belakang berkinerja tinggi (Backend Service):

```mermaid
graph TD
    Client[React 19 + TypeScript + Vite SPA] <-->|REST API + SSE Stream| Backend[FastAPI Python 3.13]
    Backend <-->|SQLAlchemy ORM| DB_Main[(app.db - Main Workspace)]
    Backend <-->|SQLAlchemy ORM| DB_Ghost[(ghost.db - Ghost Workspace)]
    Backend <--> Scrapers[Scraper Adapters: HTTP / Playwright / Scrapling]
    Backend <--> LLM[LLM Providers: LM Studio / Gemini / OpenAI / OpenRouter]
```

### Komponen Utama:
1. **Frontend (`src/`)**:
   - Single Page Application berbasis **React 19**, **TypeScript 5.8 (Strict)**, dan **Vite**.
   - Komponen UI dibangun dengan **Tailwind CSS**, **Lucide React**, dan **Radix UI / Material UI**.
   - Integrasi cache sisi klien menggunakan `sessionStorage` (Stale-While-Revalidate) dengan isolasi workspace via `getWorkspaceStorageKey()`.

2. **Backend (`backend/`)**:
   - Web framework asinkron menggunakan **FastAPI** dengan dependency injection dan event streaming SSE (Server-Sent Events).
   - Data layer menggunakan **SQLAlchemy** dengan dual-database SQLite (`app.db` untuk perpustakaan utama, `ghost.db` untuk private vault).
   - Multi-Tenancy Invariant diatur secara terpusat melalui `normalize_workspace` dan `make_workspace_key`.

---

## 🔄 2. Tiga Alur Data Inti (Core Data Flows)

### A. Alur Ingestion & Web Scraping
```mermaid
sequenceDiagram
    participant User
    participant ScrapeRouter as routers/scrape.py
    participant Scraper as services/scrapers/
    participant DB as SQLite DB
    User->>ScrapeRouter: Input URL Novel / Bab
    ScrapeRouter->>Scraper: Validasi SSRF & Pilih Tier Scraper
    Note over Scraper: Tier 1: Pure HTTP (SFACG)<br/>Tier 2: Playwright/Patchright (Novalpie AES-GCM)<br/>Tier 3: Scrapling Turnstile Bypass
    Scraper-->>ScrapeRouter: Markdown Bersih + Metadata Bab
    ScrapeRouter->>DB: Simpan Thread & Chapters
    ScrapeRouter-->>User: TOC / Detail Novel Siap Dibaca
```

### B. Alur Ekstraksi Konteks & Terjemahan
```mermaid
sequenceDiagram
    participant Reader as ReaderPage / BulkModal
    participant TransRouter as routers/translate.py
    participant BgTrans as services/background_translator.py
    participant Engine as services/context_engine.py
    participant LLM as AI Provider
    Reader->>TransRouter: Trigger Translate Bab (SSE)
    TransRouter->>BgTrans: Queue Translation Task
    BgTrans->>Engine: extract_glossary_pass (Auto source-lang)
    Engine-->>BgTrans: Simpan Istilah Baru ke Lorebook
    BgTrans->>Engine: build_translation_prompt (Genre + Style + Lorebook)
    BgTrans->>LLM: Stream Translation (with loop detection & token cap)
    LLM-->>BgTrans: Stream Chunks
    Note over BgTrans: Post-Processing: enforce_glossary_locking,<br/>image placeholder restore, fidelity check
    BgTrans-->>TransRouter: SSE 'final_text' Event + [DONE]
    TransRouter-->>Reader: Update Teks Terjemahan Instan
```

### C. Alur Pengalaman Membaca (Reader UX)
```mermaid
graph LR
    Open[Buka Bab] --> CacheCheck{Ada di sessionStorage?}
    CacheCheck -- Ya --> InstantRender[Render Instan 0ms]
    CacheCheck -- Tidak --> ShowSkeleton[Pemuatan Halus Keep-Previous]
    InstantRender --> Prefetch[Background Prefetch Bab N+1 & N-1]
    ShowSkeleton --> FetchContent[Fetch Chapter Detail & Cache]
    FetchContent --> Prefetch
    Prefetch --> ScrollRestore[Multi-Stage Scroll Restoration]
    ScrollRestore --> ScrollPhysics[Cumulative Scroll Physics & Gesture Guard]
```

---

## 🚪 3. Titik Masuk Penting (Key Entry Points)

| Modul | Path File | Tanggung Jawab Utama |
|---|---|---|
| **Backend Entry** | `backend/main.py` | Registrasi router FastAPI, inisialisasi database, middleware CORS & workspace. |
| **Database Models** | `backend/database.py` | Definisi schema tabel, helper compound tenancy (`make_workspace_key`), auto-migration `init_db`. |
| **Context & Glossary** | `backend/services/context_engine.py` | Perakitan prompt terjemahan, ekstraksi lorebook, penguncian glosarium, deteksi bahasa sumber. |
| **Background Translator** | `backend/services/background_translator.py` | Antrean batch worker, pacing provider, lock per workspace, deteksi loop repetisi LLM. |
| **Frontend Entry** | `src/App.tsx` | State navigasi tab aplikasi, sesi aktif, dan rendering layout utama. |
| **API Client** | `src/lib/api.ts` | Wrapper fetch dengan injeksi header `X-Workspace` dan generator key storage workspace. |
| **Library Page** | `src/pages/LibraryPage.tsx` | Rak buku visual, SWR cache, filter kategori, cover generator. |
| **Reader Page** | `src/pages/ReaderPage.tsx` | Orkestrasi mode baca, prefetch bab bersebelahan, dialog kontrol chapter. |
| **Reader Component** | `src/components/reader/ChapterReader.tsx` | Fisika scroll anti-mental, Quick Chapter Drawer TOC, render teks split. |
