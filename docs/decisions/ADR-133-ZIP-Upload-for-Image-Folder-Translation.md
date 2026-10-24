# ADR-133: Unggah ZIP untuk Terjemahan Folder Gambar

## Status
Accepted (2026-10-24). Diuji dengan tes unit/router; belum dicoba dengan ZIP buatan HP asli.

## Context
Browser HP tidak punya pemilih folder, sehingga satu bab manga harus dipilih gambar demi gambar. HP bisa membuat ZIP dari folder lewat aplikasi Files.

## Decision
- `POST /api/translate/images` dan `.../export-pdf` menerima **satu** berkas ZIP di field `files` (deteksi lewat magic bytes `PK`). Campuran ZIP dan gambar, atau lebih dari satu ZIP, ditolak 400.
- Pembukaan ZIP dilakukan **di server, di memori**, dengan `zipfile` dari stdlib (`backend/services/image_zip.py`); tidak ada dependensi baru dan tidak ada unzip di klien.
- Zip bomb: ukuran dan rasio kompresi yang dideklarasikan tidak dipercaya; setiap entri dibaca bertahap dan berhenti di 10 MB per gambar dan 100 MB total; rasio deklarasi > 200 ditolak; maksimal 1000 entri dipindai dan 200 gambar (413); ZIP bersarang tidak dibuka.
- Path traversal: tidak ada ekstraksi ke disk; nama entri tidak pernah menjadi path. Nama tampilan = komponen terakhir, karakter kontrol dibuang, maksimal 120 karakter. Direktori, `__MACOSX`, berkas titik, symlink/berkas non-reguler, dan ekstensi selain PNG/JPG dilewati; ZIP terenkripsi atau korup ditolak 400.
- Urutan halaman: natural sort pada path penuh (`p2` sebelum `p10`), deterministik sehingga ekspor yang mengirim ulang ZIP yang sama tetap sejajar dengan `translations`/`boxes`.
- Event `start` kini membawa `names` (nama tampilan per halaman) untuk unggahan ZIP maupun gambar biasa.
- Frontend: input "ZIP berisi gambar" di `ImageFolderTranslatePanel`; jumlah dan nama halaman diambil dari event `start`.

## Consequences / Residual
- Seluruh isi ZIP berada di memori (hingga 100 MB); wajar untuk penggunaan lokal, perlu ditinjau bila dipublikasikan.
- Entri ZIP yang tumpang tindih dibatasi oleh batas per entri dan total.
- Nama dengan encoding non-UTF-8 hanya memengaruhi tampilan.
- Isi entri yang bukan PNG/JPEG asli tetap lolos ekstraksi dan dilaporkan sebagai `page_error` oleh validasi gambar.

## Files
`backend/services/image_zip.py`, `backend/routers/image_batch_translate.py`, `src/lib/pdfTranslate.ts`, `src/components/ImageFolderTranslatePanel.tsx`. Tes: `tests/test_services/test_image_zip.py`, `tests/test_routers/test_translate_images.py`.
