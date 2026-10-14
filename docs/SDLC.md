# SDLC — AI Translator Web (ReadOmni Clone)

> **Terakhir diperbarui:** 15 Agustus 2026  
> **Status Aktif:** ✅ Phase 20 — Punctuation False-Positive Elimination & Chained Bulk Crawler (Complete)  
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
| **Phase 1** | Foundation: Design system, Backend setup, DB schema | ✅ Selesai |
| **Phase 2** | Core: UI Shell, Scraping, EPUB, API connect | ✅ Selesai |
| **Phase 3** | Translation: Lorebook Engine, AI Etik Enforcement | ✅ Selesai |
| **Phase 4** | Automation: Auto-save, Glossary Extraction Loop | ✅ Selesai |
| **Phase 5** | UI/UX Overhaul: Omni-Sepia & Background Persistence | ✅ Selesai |
| **Phase 6** | Navigation: Bulk Title Translation & Navigation Polish | ✅ Selesai |
| **Phase 7** | **Stability & Quality**: Chunking, Husky Removal, AbortController | ✅ Selesai |
| **Phase 8** | Advanced Monitoring & Performance | ✅ Selesai |
| **Phase 9** | Premium Book Export (EPUB/TXT) | ✅ Selesai |
| **Phase 10** | **Batch Translation Studio** | ✅ Selesai |
| **Phase 11** | **TDD & Code Quality Verification** | ✅ Selesai |
| **Phase 12** | **Custom Book Cover Personalization** | ✅ Selesai |
| **Phase 13** | **Infinite Polish & Scraped Author Integration** | ✅ Selesai |
| **Phase 14** | **Batch Reliability & Global Progress UX** | ✅ Selesai |
| **Phase 15** | **Configurable Chapter Token Safety Cap** | ✅ Selesai |
| **Phase 16** | **Hallucination Audit, Context Expansion & Target Language Enforcement** | ✅ Selesai |
| **Phase 17** | **Quality/Fast Mode, Auto-Continue, Cleanup Hardening & Batch Reliability** | ✅ Selesai |
| **Phase 18** | **Mobile Screen Sleep Recovery, Model Catalog Refresh & Glossary Filtering** | ✅ Selesai |
| **Phase 19** | **Translation Notes Prompt Alignment & Glossary Sanitization** | ✅ Selesai |
| **Phase 20** | **Punctuation False-Positive Elimination & Chained Bulk Crawler** | ✅ Selesai |
| **Phase 21** | **Fidelity Management Hub & Selective Repair System** | ✅ Selesai |
| **Phase 22** | **Universal Bi-Directional Load Mode Synchronization** | ✅ Selesai |
| **Phase 23** | **Novel Thread Image Caching, Reader Proxy & Visual Gallery** | ✅ Selesai |
| **Phase 24** | **Resilient Image Proxy, Cache Invalidation & Interactive Refresh** | ✅ Selesai |
| **Phase 25** | **Glossary Hard-Locking, Gender-Aware Consistency & Visual Controls** | ✅ Selesai |
| **Phase 26** | **Adaptive Source Language Prompt Engine & Direct Korean Translation** | ✅ Selesai |

## Phase 1: Foundation (COMPLETE)
- **Goal**: Membangun fondasi arsitektur backend, skema basis data, dan design system frontend yang seragam.
- **Implementation**: Inisialisasi FastAPI, database SQLite/SQLAlchemy, dan TailwindCSS v4 dengan design tokens (ADR-001).
- **Status**: Finished.

## Phase 2: Core Features (COMPLETE)
- **Goal**: Mendukung pengimporan novel melalui web scraping dan pemrosesan file EPUB lokal.
- **Implementation**: Mengintegrasikan Crawl4AI untuk scraping aman dan parser EbookLib untuk split bab EPUB (ADR-002, ADR-003).
- **Status**: Finished.

## Phase 3: Lorebook Engine (COMPLETE)
- **Goal**: Menjamin konsistensi istilah terjemahan antar bab menggunakan glosarium per-thread.
- **Implementation**: Sistem CRUD database untuk Lorebook, injeksi dinamis glosarium ke context window LLM lokal, dan sensor etika AI (ADR-004, ADR-005).
- **Status**: Finished.

## Phase 4: Automation & Auto-Save (COMPLETE)
- **Goal**: Mempercepat alur pembacaan melalui fitur simpan otomatis dan pendeteksi glosarium otomatis.
- **Implementation**: Logika deteksi peristilahan otomatis saat membaca bab baru, penambahan cepat entri lorebook (ADR-009, ADR-010).
- **Status**: Finished.

## Phase 5: UI/UX Overhaul & Background Persistence (COMPLETE)
- **Goal**: Overhaul visual bertema premium (Omni, Sepia, OLED) dan migrasi data setting ke server-side database.
- **Implementation**: CSS variable themes (style.md) di frontend, table `global_settings` di database SQLite backend untuk multi-device sync (ADR-006, ADR-008).
- **Status**: Finished.

## Phase 6: Navigation & Title Polish (COMPLETE)
- **Goal**: Mendukung penerjemahan massal judul-judul bab novel berukuran besar dan menghilangkan kedipan visual.
- **Implementation**: BackgroundTasks asinkron untuk penerjemahan judul massal (ADR-007) dan optimalisasi UX rendering bab di ReaderPage.
- **Status**: Finished.

## Phase 7: Stability & Reliability Guardrails (COMPLETE)
- **Goal**: Mencegah kegagalan batch, race conditions, dan throttling GPU lokal.
- **Implementation**: Pembatasan batch chunking 50 judul, jeda 1.0s, HTTP timeout 300s, pembersihan Husky git hooks, dan integrasi `AbortController` (ADR-011).
- **Status**: Finished.

## Phase 8: Advanced Monitoring & Performance (COMPLETE)
- **Goal**: Visibilitas status background task, prefetching bab latar belakang sekuensial cerdas.
- **Implementation**: Rentang prefetching 1-5 bab dikonfigurasi server-side, indikator visual status bab ("Prefetched", "Translating...") di sidebar, polling progres dinamis 5s (ADR-013).
- **Status**: Finished.

## Phase 9: Premium Book Export (COMPLETE)
- **Goal**: Memungkinkan ekspor hasil terjemahan novel ke format buku e-reader premium (EPUB/TXT) dengan metadata dan sampul kustom.
- **Implementation**: Service Python EPUB exporter, Upload cover Base64, dan antarmuka seleksi bab di modal glassmorphism (ADR-014).
- **Status**: Finished.

## Phase 10: Batch Translation Studio (COMPLETE)
- **Goal**: Dasbor sentral pemrosesan batch terjemahan massal dengan mitigasi konsistensi (AI Extract First).
- **Implementation**: Batch Studio Workspace dengan mode Mudah/Lanjutan, visualisasi status Center, deteksi lorebook <40 entri untuk rekomendasi ekstraksi AI (ADR-015).
- **Status**: Finished.

## Phase 11: TDD & Code Quality Verification (COMPLETE)
- **Goal**: Menjamin keandalan logika pembersihan teks, parser AI, dan meminimalkan warning serta error di frontend/backend.
- **Implementation**: Unit test mandiri `test_context_engine.py` menggunakan in-memory SQLite, standardisasi stream stdout di Windows `main.py`, dan pembersihan 100% eslint & typescript compile errors (ADR-018).
## Phase 12: Custom Book Cover Personalization (COMPLETE)
- **Goal**: Menghadirkan kustomisasi sampul buku premium menggunakan upload gambar base64 yang dikompresi secara lokal, link URL langsung, dan linear gradient fallback visual yang dinamis.
- **Implementation**: Canvas-based local compressor di frontend, SQLite schema auto-migration untuk field `cover_image` di backend, hash HSL generator berdasarkan judul buku, serta sinkronisasi visual pada rak buku dan komidi putar riwayat baca (ADR-019).
- **Status**: Finished.

## Phase 13: Infinite Polish & Scraped Author Integration (COMPLETE)
- **Goal**: Mengotomatiskan ekstraksi dan integrasi metadata penulis dari platform Novel Updates & SFACG serta menstabilkan proses pembersihan judul orisinil.
- **Implementation**: Web scraping selectors untuk penulis, integrasi SQLAlchemy dan schema mapping, prefill nama penulis orisinil di modal ekspor EPUB/TXT, zero-padded formatting untuk penomoran bab yang rapi, dan transisi pengaturan mode soft/hard load (ADR-023, ADR-024, ADR-025).
- **Status**: Finished.

## Phase 14: Batch Reliability & Global Progress UX (COMPLETE)
- **Goal**: Membuat batch translation lebih jujur, tahan terhadap empty stream/provider safety block, dan progress-nya tetap terlihat global saat user berpindah halaman.
- **Implementation**: Validasi hasil akhir batch agar chapter kosong tidak pernah ditandai `done`, fallback non-streaming saat stream Gemini kosong, resolver provider-aware untuk model/base URL, `BulkStatusCenter` global di `App.tsx`, dan tab Library dipertahankan saat kembali dari Reader (ADR-034).
- **Status**: Finished.

## Phase 15: Configurable Chapter Token Safety Cap (COMPLETE)
- **Goal**: Mengurangi hallucination drift dan token burn pada terjemahan chapter panjang tanpa mengunci user ke satu batas keras.
- **Implementation**: Tambah global toggle chapter token safety cap, preset `7K/15K/22K/30K`, default `22K`, mode uncapped saat toggle dimatikan, wiring backend `max_tokens` ke jalur translate chapter, update Settings UI, dan sinkronisasi ADR-035.
- **Status**: Finished.

## Phase 16: Hallucination Audit, Context Expansion & Target Language Enforcement (COMPLETE)
- **Goal**: Mendeteksi dan membersihkan output LLM yang terdistorsi, memperluas kapasitas Lorebook, dan memastikan semua catatan AI ditulis dalam bahasa target.
- **Implementation**: Automated hallucination pattern detection (ADR-036), thread-level TXT cleaning pipeline dengan preview modal (ADR-037), Markdown formatting support untuk bold/italic (ADR-038), penggantian native alert/confirm dengan sonner toasts dan Radix UI AlertDialog (ADR-039), ekspansi kapasitas Lorebook hingga 1000 entri dengan visualisasi graf hubungan karakter (ADR-040), dan injeksi `target_language` ke semua prompt ekstraksi AI (ADR-041).
- **Status**: Finished.

## Phase 17: Quality/Fast Mode, Auto-Continue, Cleanup Hardening & Batch Reliability (COMPLETE)
- **Goal**: Mengoptimalkan konfigurasi terjemahan per provider, menangani truncation otomatis, mengeraskan logika cleanup, dan meningkatkan keandalan batch worker.
- **Implementation**: Konsolidasi UI library (ADR-042), centralized settings state (ADR-043), dekomposisi komponen besar (ADR-044), ekspansi suite test formal (ADR-045), auto-continue pada truncation dengan deteksi `finish_reason` dan continuation loop (ADR-046), Quality/Fast translation mode toggle dengan parameter otomatis per provider (ADR-047), perbaikan cleanup logic untuk ad detection, hallucination stripper, dan preview endpoint (ADR-048), serta batch worker reliability dengan retry exponential backoff dan infinite loop prevention (ADR-049). Tambahan: delete chapter button, TOC page detection & skip, Gemini thinking mode compatibility, dan multiple API keys dengan rotation.
- **Status**: Finished.

## Phase 18: Mobile Screen Sleep Recovery, Gemini Catalog Refresh & Garbage Glossary Filtering (COMPLETE)
- **Goal**: Menjamin ketahanan pembaca saat layar HP mati/terkunci, memutakhirkan katalog model Gemini/Gemma teks, dan menyaring istilah glosarium ampas.
- **Implementation**: Sinkronisasi `displayMode` ke `localStorage` dan pemulihan layar mati mobile via `sessionStorage` cache & `visibilitychange` listener (ADR-085), pembaruan katalog model terjemahan Gemini & Gemma dengan pengaturan RPM/RPD terbaru (ADR-086), serta penyaringan otomatis istilah ampas via `ContextEngine.is_garbage_lorebook_entry()` (ADR-087).
- **Status**: Finished.

## Phase 19: Translation Notes Prompt Alignment & Glossary Sanitization (COMPLETE)
- **Goal**: Mencegah AI task hijacking/confusion yang menyebabkan hanya catatan penerjemah yang dihasilkan alih-alih isi bab, serta menyaring istilah majemuk bergaris miring di Lorebook.
- **Implementation**: Penyelarasan instruksi prompt di `prompt_templates.py`, pembersihan otomatis istilah majemuk bergaris miring di `auto_save_glossary()`, pengerasan `strip_translator_notes()` dan `clean_final_translation()` di `context_engine.py`, migrasi sanitasi database `app.db`, serta re-translasi bab terdampak (ADR-091).
- **Status**: Finished.

## Phase 20: Punctuation False-Positive Elimination & Chained Bulk Crawler (COMPLETE)
- **Goal**: Mengeliminasi peringatan false-positive pada verifikasi fidelity tanda baca akhir dan menyediakan mekanisme crawling bab web secara berantai (chained) dengan progress real-time.
- **Implementation**: Pengecekan karakter penutup fleksibel termasuk tanda kutip/kurung/ellipsis pada `fidelity_checker.py` (ADR-092), dan implementasi crawler berantai berbasis SSE/streaming di backend dan modal `BulkFetchModal.tsx` di frontend (ADR-093).
- **Status**: Finished.

## Phase 21: Fidelity Management Hub & Selective Repair System (COMPLETE)
- **Goal**: Memberikan visibilitas terpusat dan kontrol granular terhadap bab-bab yang memiliki peringatan kualitas/pemotongan (fidelity issues), memungkinkan dismiss massal untuk variasi ringan (0.8–0.9), serta aksi perbaikan terjemahan ulang satu-klik.
- **Implementation**: Pembuatan endpoint analitik dan batch action di `backend/routers/threads.py` (`fidelity-issues`, `dismiss`, `retranslate`), pembuatan komponen modal interaktif `FidelityManagementModal.tsx` dengan checklist grid dan tab filter keparahan, integrasi tombol kontrol di `ChapterListControls.tsx`, penyematan quick-action di banner pembaca `ChapterReader.tsx`, dan penulisan test suite `test_fidelity_management.py` (ADR-094).
- **Status**: Finished.

## Phase 22: Universal Bi-Directional Load Mode Synchronization (COMPLETE)
- **Goal**: Menjamin konsistensi pemilihan mode muat terjemahan (Hard Load / Soft Load) secara real-time dan bi-direksional di seluruh komponen aplikasi tanpa kembali ke setting global secara sepihak.
- **Implementation**: Pembuatan modul state sinkronisasi `src/lib/settingsSync.ts` dengan custom event emitter, sinkronisasi state di `BulkTranslateModal`, `SettingsOverlay`, `ReaderPage`, `LibraryPage`, `SettingsPage`, dan `backend/routers/batch.py` (ADR-102).
- **Status**: Finished.

## Phase 23: Novel Thread Image Caching, Reader Proxy & Visual Gallery (COMPLETE)
- **Goal**: Menyediakan kemampuan caching gambar novel secara lokal untuk pembacaan offline instan, konfigurasi kapasitas cache di halaman pengaturan, serta tab filter `Images` dengan galeri visual novel terpadu dan interactive lightbox.
- **Implementation**: Pembuatan service `backend/services/image_cacher.py` dan router `backend/routers/images.py` (`/api/images/proxy`, `/api/threads/{id}/cache-images`, `/api/cache/images/stats`, `/api/threads/{id}/images`), pembaruan `renderMarkdown` untuk me-route gambar via proxy, penambahan tombol unduh gambar di `ChapterListControls.tsx`, kartu pengaturan cache di `SettingsPage.tsx`, serta komponen galeri visual interaktif `ThreadImageGallery.tsx` dengan tab `Images` di `ChapterListControls.tsx` dan `ReaderPage.tsx` (ADR-103, ADR-104).
- **Status**: Finished.

## Phase 24: Resilient Image Proxy, Cache Invalidation & Interactive Refresh (COMPLETE)
- **Goal**: Menghilangkan kendala gambar yang gagal dimuat atau macet/stuck dengan menyediakan sistem retry interaktif, tombol refresh 1-klik, dan mekanisme bypass cache (`force=true`) baik di tampilan pembaca bab maupun di galeri visual novel.
- **Implementation**: Penambahan parameter `force: bool` dan resolusi referer dinamis di `backend/routers/images.py`, pembuatan komponen `<SafeReaderImage>` di `src/components/reader/SafeReaderImage.tsx` yang diintegrasikan ke dalam `renderMarkdown` (`src/lib/utils.ts`), penambahan kartu kegagalan dengan tombol refresh pada thumbnail kartu dan toolbar modal Lightbox di `src/components/reader/ThreadImageGallery.tsx`, serta tombol batch "Retry Failed" pada header galeri (ADR-105).
- **Status**: Finished.

## Phase 25: Glossary Hard-Locking, Gender-Aware Consistency & Visual Controls (COMPLETE)
- **Goal**: Mengeliminasi ketidakkonsistenan istilah terjemahan, kebocoran Pinyin/Hanzi mentah, kesalahan pronoun (`he/she`), serta menyediakan kontrol visual dan sanitasi entitas non-manusia.
- **Implementation**:
  - Arsitektur hybrid glossary hard-locking dengan ekstraksi Pinyin otomatis dan post-processing deterministik (ADR-106).
  - Safety net penguncian glosarium saat ekspor EPUB/TXT dan sinkronisasi instan 0-token di pembaca (ADR-107).
  - Algoritma *single-pass non-overlapping span replacement* yang 100% idempoten tanpa duplikasi beruntun (*runaway cascading*) (ADR-108).
  - Skema database `LorebookEntry.gender`, parsing token `MALE/FEMALE`, backfill otomatis, dan injeksi aturan pronoun wajib ke prompt terjemahan (ADR-109).
  - Heuristik klasifikasi entitas non-manusia (`is_non_human_term`), emblem badge gender (`♂`/`♀`), filter segmentasi glosarium, siklus toggle 1-klik, dan aturan anti-jiplak prompt (ADR-110).
- **Status**: Finished.

## Phase 26: Adaptive Source Language Prompt Engine & Direct Korean Translation (COMPLETE)
- **Goal**: Menghilangkan bias Mandarin dan risiko double-translation ketika memproses teks sumber asli Korea (Hangul) atau Jepang (Kana), memastikan terjemahan langsung (*direct translation*) dengan honorifik dan tata bahasa asli yang presisi.
- **Implementation**:
  - Klasifikasi script otomatis `detect_source_language` untuk mendeteksi teks Hangul, Hanzi, atau Kana.
  - Penyesuaian pedoman terjemahan inti (`build_core_translation_guidelines`): instruksi khusus web novel Korea, honorifik (`형/Hyung`, `누나/Noona`, `오빠/Oppa`, `선배/Sunbae`), mitigasi *zero anaphora* / pelacakan pronoun, konvensi hunter/system/dungeon, dan larangan mutlak menerjemahkan lewat bahasa Mandarin.
  - Format judul bab Korea (`clean_and_format_chapter_title`): pembersihan otomatis awalan `제X화`, `X화`, `EP.X`, `Episode X`.
  - Ekstraksi glosarium Korea: contoh istilah K-novel dan pembuktian gender berbasis pronomina Korea (`그/그녀`) atau istilah kekerabatan (`형/누나/오빠/언니`).
  - Penguncian istilah glosarium (`glossary_lock.py`): perlindungan istilah Hangul mentah yang bocor di teks hasil terjemahan.
  - Dokumentasi resmi keputusan di ADR-111.
- **Status**: Finished.

## Phase 27: Authenticated Scrapers, Media Pipeline, & Security Hardening (COMPLETE)
- **Goal**: Integrasi scraper novel canggih (Novalpie & SFACG), proteksi SSRF berlapis (Defense-in-Depth), isolasi total basis data ganda (*Dual-DB*), serta sistem caching ilustrasi bab otomatis.
- **Implementation**:
  - Scraper Novalpie Mode Ganda (Akun & Tamu) dengan integrasi sesi Playwright dan token parsing (ADR-112, ADR-114).
  - Media Gate & Illustration Pipeline server-side untuk parsing dan proxy gambar bab terenkripsi (ADR-113).
  - Proteksi SSRF berlapis dengan hook validasi redirect HTTP asinkron, pemblokiran IP non-global, isolasi memori Dual-DB `(workspace, id)`, dan rekonsiliasi masking secret multi-kunci (ADR-115, ADR-116).
  - Scraper murni HTTP performa tinggi untuk SFACG TOC & Chapters (<0.5s/bab) tanpa overhead Playwright (ADR-116).
- **Status**: Finished.

## Phase 28: Full-Stack Remediation, Glossary Collision Mitigation, & Mobile Geometry Hardening (COMPLETE)
- **Goal**: Memperbaiki secara komprehensif 6 issue terbuka di GitHub (#2, #3, #4, #5, #6, #7): crash asyncio semaphore, celah SSRF redirect, isolasi Dual-DB, overwrite gambar EPUB, collision pinyin 1 suku kata, prioritas istilah terkunci, dan geometri viewport mobile serta navigasi hash.
- **Implementation**:
  - Konversi asinkron endpoint `get_chapter` dan semaphore sadar event loop (ADR-117).
  - Validasi SSRF `validate_external_url` dan `create_safe_async_client` pada seluruh endpoint scraping (ADR-117).
  - Isolasi total registry in-memory dengan compound key `(workspace, id)` dan penghapusan penghentian batch global (ADR-117).
  - Penormalan path gambar EPUB unik dan ekstraksi metadata sinopsis (ADR-117).
  - Wajib case-sensitive untuk pinyin 1 suku kata dan ekspansi stopwords collision (ADR-117).
  - Perbaikan klasifikasi non-human untuk deskripsi yang memuat kata peran dan prioritas pengurutan `is_locked` (ADR-117).
  - Pengaktifan kembali pinch-to-zoom di `index.html`, kompensasi safe-area `BottomNav.tsx`, penanganan PIN fleksibel di `SettingsPage.tsx`, popover responsif di `ChapterListControls.tsx`, kartu relasi karakter interaktif di `RelationshipGraph.tsx`, dan navigasi hash di `App.tsx` (ADR-117).
- **Status**: Finished.

## Phase 29: Ghost Cache Isolation, SSE Queue Tenancy, & Scraper Router Workspace Hardening (COMPLETE)
- **Goal**: Menyelesaikan 6 bug edge-case terakhir (Issue #10, ADR-118) terkait isolasi cache Ghost Mode di sisi frontend, penghapusan integer key pada antrean SSE `translation_queues`, propagasi workspace pada NovalpieAdapter, proteksi SSRF redirect di Novalpie API, deteksi URL TOC SFACG, dan isolasi pembersihan cache gambar.
- **Implementation**:
  - Pelingkupan kunci session storage & local storage dengan `getActiveWorkspace()` pada `App.tsx`, `LibraryPage.tsx`, `ReaderPage.tsx`, dan `BookmarksPage.tsx`, serta pembersihan `sessionStorage.clear()` saat berpindah workspace di `Sidebar.tsx` dan `SettingsPage.tsx` (ADR-118).
  - Penghapusan integer key pada antrean streaming SSE `translation_queues` di `translate.py` dan `background_translator.py` (ADR-118).
  - Meneruskan `workspace=ws` pada seluruh instansiasi `NovalpieAdapter` di `scrape.py`, `toc.py`, dan `threads.py`, serta integrasi `create_safe_async_client` pada `scrape_metadata` dan `scrape_toc` (ADR-118).
  - Penambahan regex `TOC_ROOT_URL_PATTERN` di `scrape.py` dan penyelarasan regex SFACG TOC di `TranslatePage.tsx` (ADR-118).
  - Pelingkupan pembersihan `ACTIVE_IMAGE_JOBS` per workspace aktif pada endpoint `clear_image_cache` (ADR-118).
- **Status**: Finished.

---

## 🏛️ 3.1 Categorized Architectural Decision Records (ADR Index)

Untuk mempermudah navigasi keputusan teknis, berikut pengelompokan seluruh ADR berdasarkan pilar arsitektur:

### 1. Ingestion, Scrapers & Anti-Bot Protection
- **ADR-002**: Web Scraping Architecture via Crawl4AI.
- **ADR-098 & ADR-099**: Novalpie Scraper, Cloudflare Bypass & Headless Fallback.
- **ADR-112 & ADR-114**: Novalpie Dual-Mode (Guest vs Account Cookie Authentication).
- **ADR-113**: Media Gate & Chapter Illustration Proxy Pipeline.
- **ADR-115 & ADR-116**: SSRF Multi-Layer Prevention (`validate_external_url`, `create_safe_async_client`) & Pure HTTP SFACG Scraper.
- **ADR-117 (Scrapers)**: 3-Tier Scraper Hierarchy & `StealthyNovelAdapter` (`stealth_base.py`).

### 2. Batch Translation, Pacing & Concurrency
- **ADR-007 & ADR-011**: Asynchronous Batch Title Translation, 50-chunking & timeout guards.
- **ADR-013**: Server-Side Prefetch Range (1-5 chapters) & Visual Indicators.
- **ADR-015**: Batch Studio Workspace (Easy vs Advanced) & Status Center.
- **ADR-025 & ADR-034**: Soft vs Hard Engine Load Modes & Honest Chapter Failure Handling.
- **ADR-035**: Configurable Chapter Token Safety Cap (Default 22K).
- **ADR-102**: Cross-Component State Synchronization (`settingsSync.ts`).
- **ADR-117 & ADR-118**: Compound Key `(workspace, id)` Tenancy on In-Memory Registries.

### 3. Context Engine, Lorebook & Quality Control
- **ADR-004 & ADR-005**: Dynamic Lorebook Injection to Local LLMs.
- **ADR-009 & ADR-010**: Automated Term Discovery & Quick Lorebook Add.
- **ADR-036**: Automated Hallucination Pattern Detection (10x Repetition).
- **ADR-040**: Lorebook Context Expansion (1000 terms) & Character Relationship Visualizer.
- **ADR-071 & ADR-074**: Genre-Aware Dynamic Prompting & Centralized Prompt Templates.
- **ADR-072 & ADR-094**: Post-Translation Fidelity Check & Fidelity Management Hub.
- **ADR-106, ADR-107 & ADR-108**: Hybrid Glossary Hard-Locking, Idempotent Single-Pass Span Replacement.
- **ADR-109 & ADR-110**: Gender Pronoun Consistency (`MALE/FEMALE`), Non-Human Classification.
- **ADR-111**: Adaptive Multi-Language Source Detection (CJK, Korean, Japanese).

### 4. Reader UX, Scroll Geometry & Mobile Layout
- **ADR-019**: Dynamic Client-Side Cover Engine & Canvas Compression.
- **ADR-038**: Lightweight Markdown Formatting for Reader & EPUB Exporter.
- **ADR-039**: Mobile-Friendly Notification & Modal Dialog System (`sonner` + Radix UI).
- **ADR-085**: Mobile Screen-Lock Resilience via `sessionStorage` & `visibilitychange`.
- **ADR-096 & ADR-117**: Mobile Viewport Geometry, Pinch-to-Zoom & Safe-Area Inset Handling.
- **ADR-105**: Safe Reader Image Component (`<SafeReaderImage>`) with Inline Retry.

### 5. Multi-Tenancy & Ghost Mode Dual-Database
- **ADR-006 & ADR-008**: Server-Side `GlobalSetting` Configuration Storage.
- **ADR-029**: Multi-Provider Cloud LLM Swapping (Gemini, OpenAI, OpenRouter).
- **ADR-115, ADR-117 & ADR-118**: Ghost Mode Dual-DB Isolation (`app.db` vs `ghost.db`), In-Memory Compound Key Tenancy (`make_workspace_key`), and Client-Side Storage Scoping (`getWorkspaceStorageKey`).

---

## 4. Testing

- **Automated Unit Tests**: Unit test suites `backend/tests/` berjalan secara otomatis untuk memvalidasi AI provider factory, settings management, dan service logic menggunakan in-memory SQLite (`conftest.py`).
- **API test:** Semua endpoint via FastAPI Swagger UI (`/docs`).
- **UI test:** Chrome DevTools — viewport 375px (mobile), 1280px (desktop).
- **Linter test**: Enforced `npm run lint` dan compiler verification untuk build 100% bersih.
- **Flicker test**: Rapid navigation check via ReaderPage.

---

## 5. Deployment

- Self-hosted di mesin lokal (atau Docker).
- LM Studio harus berjalan di port `1234` sebelum backend distart.
- Akses mobile via LAN IP (contoh: `192.168.1.x:5173`).

---

## Catatan Developer

- Frontend ada di `/src`, jalankan dengan `npm run dev`.
- Backend ada di `/backend`, jalankan dengan `py -m uvicorn main:app --reload --host 0.0.0.0`.
- **Penting**: Konfigurasi LM Studio kini disimpan di **Server-Side Database** (table `global_settings`), bukan lagi localStorage.
