# Penanda Chapter Berilustrasi (Illustrated Chapter Badge & Filter)

## Problem Statement
Bagaimana kita memudahkan pembaca novel mengetahui chapter mana saja yang memuat ilustrasi gambar (beserta jumlahnya) secara instan pada daftar chapter tanpa membuka isi chapter satu per satu dan tanpa mengorbankan performa load daftar chapter?

## Recommended Direction
Menggunakan pendekatan **Stored Column + Auto-Detection**:
1. Menambahkan kolom `image_count: int` (default `0`) pada model database `Chapter`.
2. Mendeteksi dan menghitung jumlah gambar secara otomatis saat penyimpanan/pembaruan konten chapter (`content_original` / `content_translated`) melalui regex tag Markdown `![alt](url)` dan HTML `<img ...>`.
3. Menjalankan migrasi/backfill ringan pada database (`backend/app.db`) untuk chapter-chapter yang sudah ada.
4. Menampilkan badge visual ringkas (ikon gambar + counter, misal: `🖼️ 2`) pada kartu chapter di `ChapterGrid.tsx`.
5. Menambahkan filter tab `Illustrated` pada `ChapterListControls.tsx` di samping opsi `All` dan `Translated`.

Pendekatan ini dipilih karena menjaga kecepatan pemanggilan endpoint `GET /api/threads/{id}` tetap instan (O(1) per row tanpa perlu parsing teks megabyte di memori saat runtime).

## Key Assumptions to Validate
- [x] **Format Gambar**: Gambar dalam konten tersimpan dalam format Markdown `![alt](url)` atau HTML `<img src="..." />` (terkonfirmasi di scraper & epub importer).
- [x] **Skema SQLite**: Penambahan kolom integer default 0 di SQLite aman dan non-destructive melalui `ALTER TABLE chapters ADD COLUMN image_count INTEGER DEFAULT 0`.
- [x] **Kompatibilitas Frontend**: Badge ilustrasi dapat disisipkan rapi di sebelah elemen `word_count` tanpa merusak tata letak kartu chapter yang responsif.

## MVP Scope
- **Database Schema**: Menambahkan kolom `image_count` pada model `Chapter` di `backend/database.py` dan auto-migration pada `init_db()`.
- **Image Counter Utility**: Fungsi utilitas regex cepat untuk menghitung tag gambar dari teks.
- **Auto-Sync Hook / Updater**: Memastikan penyimpanan/update konten chapter menghitung `image_count`.
- **Backfill Script**: Skrip/fungsi satu kali jalan untuk mengisi `image_count` pada chapter-chapter yang sudah tersimpan di database.
- **Backend API**: Mengirimkan field `image_count` di `ChapterOut` pada `backend/routers/threads.py`.
- **Frontend Types**: Menambahkan `image_count?: number` ke antarmuka `Chapter` di `src/components/reader/types.ts`.
- **Frontend UI Badge**: Menampilkan badge ikon Lucide `Image` + counter di `src/components/reader/ChapterGrid.tsx`.
- **Frontend Filter**: Menambahkan opsi filter `'illustrated'` di `src/pages/ReaderPage.tsx`, `ChapterListControls.tsx`, dan `ChapterGrid.tsx`.

## Not Doing (and Why)
- **Gallery Grid Global**: Tidak membuat halaman/tab galeri tersendiri yang mengumpulkan semua gambar novel — fokus MVP adalah navigasi chapter.
- **Hover Image Preview Popover**: Tidak memuat thumbnail gambar saat hover badge — untuk menjaga kuota bandwidth dan mencegah lonjakan download gambar saat membuka daftar chapter.
- **Active HTTP Link Ping**: Tidak mengecek status HTTP 200/404 pada URL gambar eksternal — agar komputasi tetap cepat tanpa latensi jaringan.

## Open Questions
- Tidak ada pertanyaan pemblokir saat ini; arah implementasi sudah disetujui pengguna.
