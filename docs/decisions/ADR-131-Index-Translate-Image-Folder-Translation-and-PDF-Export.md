# ADR-131: Terjemahan Folder Gambar dan Ekspor PDF

## Status
Accepted (2026-10-24). Hanya diuji dengan tes unit/router dan provider tiruan; belum dicoba dengan satu bab manga nyata di LM Studio.

## Context
ADR-130 menambah terjemahan PDF. Pengguna juga ingin menerjemahkan satu folder gambar (bab manga hasil scan) dan mendapat PDF. Index-Translate tidak mengeluarkan koordinat teks, sehingga teks tidak bisa ditimpa langsung pada gambar tanpa OCR terpisah.

## Decision
- `POST /api/translate/images` (multipart `files[]`, `model`, `target_lang`, `lm_url`) di `backend/routers/image_batch_translate.py`: aliran NDJSON dengan event yang sama seperti rute PDF (`start`, `page`, `page_error`, `done`), urutan = urutan unggah, satu gambar per langkah.
- `POST /api/translate/images/export-pdf` (multipart `files[]` + `translations` berupa JSON array string): membangun PDF dengan satu halaman gambar diikuti halaman teks terjemahan (teks panjang menyambung ke halaman berikutnya). Klien mengunggah ulang file yang sama; server tidak menyimpan apa pun.
- `backend/services/image_batch.py`: hanya PNG dan JPEG (cek magic bytes lalu decode MuPDF), sisi terpanjang dijepit ke 2048 px (panduan resmi Index-Translate), CMYK dikonversi ke RGB. WebP/GIF ditolak. Tanpa dependensi baru (PyMuPDF dari ADR-130; Pillow tidak dipakai).
- Batas: 200 gambar (413; semula 60, dinaikkan karena bab webtoon sering 100+ potongan), 10 MB per gambar, 100 MB total (413), dibaca bertahap. Nama file unggahan tidak pernah dipakai sebagai path. Gambar rusak jadi `page_error`, sisanya tetap jalan. Pesan galat provider dibersihkan seperti rute lain.
- Frontend: `ImageFolderTranslatePanel` (pemilih folder `webkitdirectory` atau multi-gambar), urutan nama alami (`page2` sebelum `page10`), tombol Unduh PDF dan Salin teks. Hasil tidak disimpan dan tidak memakai localStorage.

## Consequences / Residual
- Bukan overlay: PDF memuat gambar asli dan teks terjemahan terpisah. Overlay butuh deteksi kotak teks (OCR/detektor) dan dependensi baru, di luar cakupan.
- Gambar webtoon sangat panjang diperkecil ke 2048 px sisi terpanjang, jadi teks kecil bisa tak terbaca; pemotongan per segmen belum dibuat.
- Halaman teks PDF memakai font bawaan (Latin) dan font CJK bawaan untuk karakter di luar Latin; tipografi sederhana.
- Ekspor mengunggah ulang gambar (hingga 100 MB di mesin lokal).

## Files
`backend/routers/image_batch_translate.py`, `backend/services/image_batch.py`, `backend/main.py`, `src/lib/pdfTranslate.ts`, `src/components/ImageFolderTranslatePanel.tsx`, `src/pages/TranslatePage.tsx`. Tes: `tests/test_services/test_image_batch.py`, `tests/test_routers/test_translate_images.py`.
