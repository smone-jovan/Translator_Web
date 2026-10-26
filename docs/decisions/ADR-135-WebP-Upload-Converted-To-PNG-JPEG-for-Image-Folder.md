# ADR-135: Unggahan WebP Dikonversi ke PNG/JPEG untuk Terjemahan Folder Gambar

## Status
Accepted (2026-10-24). Diuji dengan tes unit/router (WebP dibuat dengan Pillow); belum dicoba dengan WebP asli dari HP atau sumber manga.

## Context
Banyak sumber manga/webtoon berformat WebP, sedangkan alur folder gambar (model vision, mode overlay, detektor teks, ekspor PDF via MuPDF) hanya mengenal PNG dan JPEG.

## Decision
- Satu fungsi murni `normalize_image(data)` di `backend/services/image_normalize.py`, dipanggil di titik masuk bersama `_read_images` (unggahan biasa dan entri ZIP). Seluruh alur sesudahnya hanya melihat PNG/JPEG; tidak ada alur lain yang diubah.
- PNG/JPEG dan format lain (GIF, BMP, dll.) dilewatkan apa adanya; format selain PNG/JPEG/WebP tetap ditolak oleh `prepare_image_data_url`.
- WebP dikenali dari magic bytes `RIFF....WEBP`. Tanpa alpha menjadi JPEG kualitas 92. Beralpha menjadi PNG; bila PNG melebihi `MAX_IMAGE_BYTES`, menjadi JPEG dengan alpha dikomposit ke putih. JPEG yang masih terlalu besar dicoba kualitas 80 lalu 65 sebelum ditolak sebagai terlalu besar. WebP animasi memakai frame pertama.
- Anti bomb dekompresi: ukuran piksel dibaca dari header dan dibandingkan dengan `MAX_PIXELS` (50 juta, sama dengan `open_rgb`) sebelum decode penuh. Unggahan sudah dibatasi 10 MB per gambar dan 100 MB total.
- Konversi deterministik (Pillow, parameter tetap), sehingga ekspor PDF yang mengunggah ulang berkas yang sama menghasilkan urutan dan isi yang sejajar dengan `translations`/`boxes`.
- Nama tampilan mengikuti hasil konversi (`p1.webp` menjadi `p1.jpg` atau `p1.png`) agar konsisten dengan event `start.names`.
- WebP rusak atau terlalu banyak piksel tidak menggagalkan satu batch: byte aslinya dipertahankan dan dilaporkan sebagai `page_error` (terjemahan) atau 400 (ekspor) dengan pesan "WebP image could not be converted (corrupt or too many pixels)".
- `image_zip._is_wanted` menerima `.webp`. Frontend: `sortImageFiles`, `accept` pada input gambar, dan teks bantuan menyebut PNG/JPG/WebP.
- Tidak ada dependensi baru (Pillow sudah ada; dukungan WebP aktif diperiksa dengan `PIL.features.check("webp")`).

## Consequences / Residual
- Konversi WebP lossy ke JPEG menambah satu generasi kompresi (kualitas 92, cukup untuk OCR vision).
- WebP beralpha yang menjadi PNG tetap diratakan ke RGB oleh `open_rgb` pada mode overlay.
- Build Pillow tanpa dukungan WebP akan membuat semua WebP dilaporkan tidak terbaca.

## Files
`backend/services/image_normalize.py`, `backend/services/image_batch.py`, `backend/services/image_zip.py`, `backend/routers/image_batch_translate.py`, `src/lib/pdfTranslate.ts`, `src/components/ImageFolderTranslatePanel.tsx`, `src/components/PdfTranslatePanel.tsx`. Tes: `tests/test_services/test_image_normalize.py`, `tests/test_services/test_image_zip.py`, `tests/test_routers/test_translate_images.py`.
