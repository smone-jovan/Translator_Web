# handoff — status proyek terakhir
> **update:** 17 Mei 2026 | **status:** phase 8 (context engine beres)

---

## overview singkat
Kita lagi bikin web app buat baca novel yang translasinya pakai AI lokal (LM Studio). Intinya, kita mau pengalaman baca kayak **ReadOmni** tapi data tetap di laptop sendiri. Sekarang sistem sudah punya "otak" buat jaga konsistensi istilah (lorebook) dan aturan etika translasi yang ketat. UI-nya pakai gaya glassmorphism dan sudah nyaman buat dibaca di HP.

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
- **Glossary optimizer**: Biar AI gak pusing, kita cuma kirim 50 istilah paling relevan ke prompt. Kita pakai hitungan `usage_count` buat nentuin mana istilah yang paling sering muncul.
- **Auto-save glossary**: Kalau AI ngasih catatan di akhir bab, sistem otomatis nangkap istilah itu dan simpan ke database. Gak perlu input manual lagi.
- **Background task**: Translasi jalan di belakang layar pakai FastAPI BackgroundTasks. Jadi kamu bisa tutup tab atau pindah halaman tanpa ngerusak prosesnya.
- **Bulk title translator**: Buat novel yang babnya ribuan, kita sudah bikin sistem chunking (50 bab sekali jalan) biar gak error pas nerjemahin judul.

### perubahan arsitektur penting:
1. **Pindah ke background task**: Dulu pakai `asyncio.create_task`, sekarang pakai cara FastAPI yang lebih stabil buat long-running process.
2. **Auto-migration**: Database sekarang bisa update kolom sendiri kalau ada perubahan skema (gak perlu hapus DB manual lagi).
3. **Usage tracking**: Sekarang tiap istilah di lorebook punya `usage_count` dan `last_used_at`.

---

## apa yang harus dikerjakan selanjutnya?

1. **Error recovery UI**: Kasih tombol buat stop paksa proses background kalau misal macet (stuck).
2. **Epub export**: Biar novel yang sudah diterjemahin bisa didownload lagi jadi file .epub bersih.
3. **Character clustering**: Ide buat deteksi otomatis hubungan antar karakter dari teks biar lorebook-nya makin mantap.

---

## tech stack & dependencies

- **frontend**: React 19, Vite, Tailwind v4.
- **backend**: Python 3.11, FastAPI, SQLAlchemy (SQLite).
- **eksternal**: LM Studio (Local AI), Crawl4AI (Scraper), EbookLib (EPUB).
