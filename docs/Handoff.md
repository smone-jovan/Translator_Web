# handoff — status proyek terakhir
> **update:** 17 Mei 2026 | **status:** Phase 10 — Batch Translation Studio & Smart Extraction (Complete)

---

## overview singkat
Kita telah berhasil membangun web app untuk membaca novel dengan translasi AI lokal (LM Studio). Pengalaman membaca terinspirasi oleh **ReadOmni** dengan fokus pada keamanan privasi lokal. Proyek saat ini telah menyelesaikan Phase 10 dengan sistem Batch Translation Studio, Lorebook Engine, prefetching cerdas, dan Premium Book Builder (Export System) yang berjalan stabil baik di perangkat Desktop maupun Mobile (iOS/Android).

---

## struktur folder
Kalau mau nyari file, ini peta singkatnya:
- `backend/`: Jeroan Python FastAPI.
  - `services/`: Tempat logika berat kayak `context_engine.py` (buat bikin prompt) dan `background_translator.py`.
  - `routers/`: Endpoint API buat scraping, epub, dsb.
- `src/`: Frontend React (Vite + Tailwind). 
  - `pages/`: Halaman reader, library, dan setting.
  - `index.css`: Semua variabel warna dan desain glassmorphism ada di sini.
- `docs/`: Catatan rencana kerja (`implementation_plan.md`) dan catatan keputusan desain (`decisions/`).

---

## status terakhir (apa yang sudah jalan?)

Sejauh ini, sistem translasinya sudah lumayan "pinter":
- **Context engine**: AI gak asal nerjemahin. Dia sudah dikasih instruksi etika (kayak jangan nerjemahin nama orang, jaga honorifik, dsb).
- **AI Glossary Extraction**: Added Dual-Mode (Easy/Advanced) configuration.
  - **Easy Mode**: Presets for Quick (5 ch), Normal (15 ch), and Deep (25 ch) scans.
  - **Advanced Mode**: Granular control over chapter count and character sample size.
  - **Token Estimation**: Real-time input token estimation (chars/4) to manage context limits.
  - **Smart Scoping**: Extraction starts from the `last_read` chapter position automatically.
- **Glossary CRUD**: Full Update (PUT) support implemented for terminology management.
- **Auto-save glossary**: Kalau AI ngasih catatan di akhir bab, sistem otomatis nangkap istilah itu dan simpan ke database. Gak perlu input manual lagi.
- **Background task**: Translasi jalan di belakang layar pakai FastAPI BackgroundTasks. Jadi kamu bisa tutup tab atau pindah halaman tanpa ngerusak prosesnya.
- **Advanced Prefetch System**:
  - **Configurable Range**: User can set background translation range (1-5 chapters ahead).
  - **Persistence**: Settings are stored server-side in `GlobalSetting` table for multi-device sync.
  - **Dynamic UI**: Slider controls available in both main Settings and Reader settings overlay.
  - **Smart Sequential Execution**: Background translator processes the next N chapters sequentially to avoid overloading the local LLM.
- **Bulk title translator**: Buat novel yang babnya ribuan, kita sudah bikin sistem chunking (50 bab sekali jalan) biar gak error pas nerjemahin judul.
- **Premium Book Builder (Export System)**:
  - **Multi-format**: Mendukung ekspor ke **EPUB** (reflowable) dan **TXT**.
  - **Custom Metadata**: User bisa atur Judul dan Nama Author secara manual sebelum ekspor.
  - **Custom Cover**: Mendukung upload gambar cover dari PC untuk disisipkan ke file EPUB.
  - **Selective Export**: Bisa pilih bab mana saja yang mau diekspor lewat checklist UI (Select All / Select Translated Only).
- **Batch Translation Studio**: 
  - **Sequential Processing**: Logic to handle bulk translations without overloading VRAM.
  - **Soft Load**: Sequential 1-by-1 processing for maximum stability and focus.
  - **Hard Load**: Adjustable bulk processing (3-20+ chapters) for rapid updates.
  - **Mandatory Overwrite**: Ensures terminology consistency across all processed chapters.
  - **Context-Aware Extraction**: Integrated AI extraction toggle (Recommended for batches).
  - **Status Center**: Real-time progress visualization for bulk tasks.

### perubahan arsitektur penting:
1. **Pindah ke background task**: 
- 🧠 **Smart Context**: AI scans up to 50 chapters ahead from your last read position to build a consistent glossary.
- ⚙️ **Configurable Extraction**: Dual-mode (Easy/Advanced) settings for extraction depth and token management.
- 📚 **Thread Isolation**: Separate lorebooks and AI suggestions for every novel thread.
2. **Auto-migration**: Database sekarang bisa update kolom sendiri kalau ada perubahan skema (gak perlu hapus DB manual lagi).
3. **Usage tracking**: Sekarang tiap istilah di lorebook punya `usage_count` dan `last_used_at`.
4. **Mobile Bottom Nav**: Navigasi utama sekarang pakai *bottom bar* yang ergonomis di HP (Slice 2 beres).

---

## apa yang harus dikerjakan selanjutnya? (Ide Pengembangan Masa Depan)

1. **AI Character Relationship Clustering & Visualizer**: Mendeteksi hubungan antar tokoh utama secara otomatis dari hasil pemindaian teks bab novel, kemudian memvisualisasikannya ke dalam grafik hubungan interaktif (dynamic network graph) di panel Lorebook.
2. **Offline Translation Model Cache & Optimizations**: Mendukung pengunduhan dan caching template gaya penerjemahan novel berbasis GGUF model lokal untuk memaksimalkan efisiensi memori GPU dan VRAM.
3. **Dynamic CSS Typography Drawer**: Menyediakan antarmuka kustomisasi jenis huruf (font family upload), spasi antar baris (line height), dan layout bacaan yang sepenuhnya dipersonalisasi di dalam panel samping reader drawer.

---

## tech stack & dependencies

- **frontend**: React 19, Vite, Tailwind v4.
- **backend**: Python 3.11, FastAPI, SQLAlchemy (SQLite).
- **eksternal**: LM Studio (Local AI), Crawl4AI (Scraper), EbookLib (EPUB).
