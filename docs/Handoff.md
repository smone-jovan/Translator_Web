# handoff — status proyek terakhir
> **update:** 17 Mei 2026 | **status:** Phase 14 — Stateful Volume Transition & Resilient Batch Polish System (Complete)

---

## overview singkat
Kita telah berhasil membangun web app untuk membaca novel dengan translasi AI lokal (LM Studio). Pengalaman membaca terinspirasi oleh **ReadOmni** dengan fokus pada keamanan privasi lokal. Proyek saat ini telah menyelesaikan Phase 13 dengan sistem pengaturan "Soft/Hard Load" bagi Infinite Title Polish, pembersihan judul original novel otomatis (ADR-020), penerjemahan sinopsis buku mandiri ke bahasa tujuan, sistem kustomisasi cover buku premium (Base64 local compressor, link URL langsung, dan dynamic seeded fallbacks), TDD backend, mitigasi encoding Windows, serta linter frontend/backend yang berjalan 100% sempurna dengan 0 error dan 0 warning.

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
- **Hidden Translator Notes & Real-time Streaming Filter**:
  - **Real-time Filter**: Pendeteksian pola catatan penerjemah secara instan selama streaming AI berjalan. Begitu AI mulai mengeluarkan catatan penerjemah, sisa streaming tidak akan diteruskan ke antrean pembaca agar tampilan tetap bersih.
  - **Automatic Stripping**: Secara otomatis memotong `Translator Notes` atau `Notes` sebelum terjemahan disimpan ke database (`Chapter.content_translated`) pada proses background translator, penyimpanan manual, maupun respon API sekali jalan (single-shot).
  - **AI Glossary Learning Maintained**: Catatan penerjemah yang disembunyikan tersebut tetap diproses sepenuhnya oleh sistem context engine (`ContextEngine.auto_save_glossary`) untuk memperkaya glosarium/lorebook novel secara otomatis sebelum dibuang dari teks cerita pembaca.
- **TDD Test Suite & Linter Quality Enforcement**:
  - **Isolated Backend Unit Tests**: Menyediakan file unit test di `backend/scratch/test_context_engine.py` untuk menguji parser catatan penerjemah dan aturan penyaringan istilah otomatis secara aman menggunakan database in-memory SQLite.
  - **Windows Unicode Safeguards**: Menambahkan penanganan encoding input/output terminal (`sys.stdout.reconfigure(encoding='utf-8')`) di `main.py` guna menghindari crash saat logging karakter non-ASCII di Windows.
  - **Clean Build Integration**: Membersihkan dan memperbaiki seluruh peringatan compilation serta React hook warnings, menghasilkan status linter yang 100% bebas dari warning dan error (`0 errors, 0 warnings`).
- **Custom Book Cover Personalization System**:
  - **Client-Side Compressor**: Upload gambar dari file local dikompresi di browser via HTML5 Canvas (resolusi 300x400, aspect ratio 3:4, format JPEG, target ukuran <100KB) untuk efisiensi penyimpanan DB dan kelancaran sinkronisasi LAN.
  - **Dynamic Seeded Gradients**: Hash otomatis berdasarkan judul novel untuk menciptakan cover linear gradient HSL yang modern dan minimalis lengkap dengan inisial glassmorphic bagi novel yang belum memiliki gambar kustom.
  - **Uniform Sync**: Integrasi visual rak buku (Bookshelf) dan riwayat bacaan (Continue Reading Carousel) dengan hover-scaling premium.
  - **Direct Image Link**: Dukungan input link URL langsung yang disimpan bersih di database SQLite.
- **Infinite Title Polish & Dynamic Actions System**:
  - **Soft/Hard Load Selectors**: Menyediakan pilihan mode polish (Soft Load 50-150 judul bab, atau Hard Load tak terbatas) untuk stabilitas memori GPU.
  - **Clean Original Title**: Secara otomatis mendeteksi dan mengekstrak judul inti Mandarin orisinil dari tag-tag deskriptif bersiku atau tanda kurung pada database (`thread.original_title`) demi kepatuhan penuh terhadap ADR-020.
  - **Automated Synopsis Translation**: Secara pintar mendeteksi deskripsi/sinopsis novel dalam bahasa Mandarin, dan menerjemahkannya secara asinkron ke bahasa tujuan (Indonesian/English) saat polish dijalankan.
  - **Polish Remaining Progression**: Menyediakan aksi dinamis "Polish Remaining" untuk melanjutkan antrean pemolesan bab berikutnya (100 bab per batch di soft load) tanpa mengulang batch pertama yang sudah selesai.
  - **Decoupled Reset All**: Aksi hapus dan ulang pemolesan total dari awal ("Reset & Re-polish All") diletakkan secara terisolasi di popover pengaturan agar tidak tertekan secara tidak sengaja.
  - **Stateful Volume Transitions**: Volume transition manager kini dilindungi dengan double-increment guard (`volume_just_incremented`) untuk mencegah lonjakan volume ganda pada bab setelah prologue atau boundary reset, serta parsing prolog yang dinamis.

### perubahan arsitektur penting:
1. **Pindah ke background task**: 
- 🧠 **Smart Context**: AI scans up to 50 chapters ahead from your last read position to build a consistent glossary.
- ⚙️ **Configurable Extraction**: Dual-mode (Easy/Advanced) settings for extraction depth and token management.
- 📚 **Thread Isolation**: Separate lorebooks and AI suggestions for every novel thread.
2. **Auto-migration**: Database sekarang bisa update kolom sendiri kalau ada perubahan skema (kolom `polish_mode` dan `polish_soft_limit` dimasukkan ke tabel `global_settings` secara dinamis saat start).
3. **Usage tracking**: Sekarang tiap istilah di lorebook punya `usage_count` dan `last_used_at`.
4. **Mobile Bottom Nav**: Navigasi utama sekarang pakai *bottom bar* yang ergonomis di HP (Slice 2 beres).
5. **Hidden Translator Notes & Auto-Stripping**: Sistem secara dinamis memisahkan teks cerita bersih untuk pembaca dari catatan penerjemah yang diperuntukkan bagi kecerdasan buatan, lengkap dengan migrasi database historis (34 bab lama dibersihkan secara otomatis).
6. **Isolated Testing & Windows Safe Shell**: Logika inti dari pembersihan teks kini terisolasi dari status database utama dengan pengujian otomatis instan yang melindungi sistem dari regresi fungsional di masa depan.
7. **Cover Image Auto-Migration**: Penambahan otomatis kolom `cover_image TEXT` pada skema basis data SQLite saat inisiasi aplikasi tanpa mengganggu data lama.
8. **Pipeline Polish & Sanitasi Metadata**: API `/threads/{thread_id}/translate-titles` sekarang merangkap sebagai pintu gerbang pembersihan metadata novel (original title dan sinopsis) secara asinkron sebelum memproses batch judul bab.
9. **Soft Load Continuation Engine**: Menghindari perulangan tak terhingga di frontend pada soft load dengan merombak alur re-polish (ADR-026).
10. **Stateful Volume Transition & Prologue Boundary**: Menghadirkan guards khusus di backend (`threads.py`) untuk melindungi navigasi multi-volume dari tabrakan sequence reset (ADR-027).

---

## apa yang harus dikerjakan selanjutnya? (Ide Pengembangan Masa Depan)

1. **AI Character Relationship Clustering & Visualizer**: Mendeteksi hubungan antar tokoh utama secara otomatis dari hasil pemindaian teks bab novel, kemudian memvisualisasikannya ke dalam grafik hubungan interaktif (dynamic network graph) di panel Lorebook.
2. **Offline Translation Model Cache & Optimizations**: Mendukung pengunduhan dan caching template gaya penerjemahan novel berbasis GGUF model lokal untuk memaksimalkan efisiensi memori GPU dan VRAM.
3. **Dynamic CSS Typography Drawer**: Menyediakan antarmuka kustomisasi jenis huruf (font family upload), spasi antar baris (line height), dan layout bacaan yang sepenuhnya dipersonalisasi di dalam panel samping reader drawer.

---

## tech stack & dependencies

- **frontend**: React 19, Vite, Tailwind v4.
- **backend**: Python 3.11, FastAPI, SQLAlchemy (SQLite), Unittest.
- **eksternal**: LM Studio (Local AI), Crawl4AI (Scraper), EbookLib (EPUB).
