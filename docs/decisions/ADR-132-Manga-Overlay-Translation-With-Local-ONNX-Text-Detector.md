# ADR-132: Terjemahan Overlay Manga dengan Detektor Teks ONNX Lokal

## Status
Accepted (2026-10-24). Diuji dengan tes unit/router dan satu halaman sintetis; **belum diuji pada halaman manga/webtoon nyata** di LM Studio.

## Context
ADR-131 menghasilkan PDF berisi gambar dan teks terjemahan terpisah. Index-Translate tidak mengeluarkan koordinat teks (README, `docs/image_translate.md`, `inference/llm/translate.py`), jadi teks tidak bisa ditimpa ke gambar tanpa detektor kotak teks terpisah. VRAM 4 GB sudah dipakai LM Studio (~3 GB).

## Decision
- Detektor: `ogkalu/comic-text-and-bubble-detector` (Apache-2.0, RT-DETR-v2; kelas 0 `bubble`, 1 `text_bubble`, 2 `text_free`), berkas ONNX int8, dijalankan dengan `onnxruntime` **di CPU**.
- Hasil spike (2026-10-24, halaman sintetis 500x800, CPU): ONNX sudah memuat pascaproses. Input `images` (1x3x640x640, RGB, 0..1, tanpa mean/std) dan `orig_target_sizes` berurutan **[lebar, tinggi]**; output `labels`, `boxes` (xyxy piksel asli), `scores`. `detector-v4-s_int8.onnx` (11,1 MB): ±0,13 dtk/panggilan; `detector_int8.onnx` (43,8 MB): ±0,47 dtk. Keduanya menemukan semua gelembung dan teks bebas sintetis. Default: v4-s; ganti dengan env `MANGA_DETECTOR_MODEL`.
- Berkas model tidak masuk git (`backend/models/*.onnx`) dan **tidak diunduh server saat runtime**. Pengguna menjalankan `py -m scripts.fetch_detector_model` (HTTPS, SHA-256 terpin, berkas hanya disimpan bila cocok). Tanpa model, `overlay=true` ditolak 400 dengan pesan jelas; tanpa `overlay` semua perilaku lama tidak berubah.
- `services/manga_detector.py`: seleksi kelas teks, ambang skor 0,4, jepit koordinat, dedup IoU 0,5, maks 25 kotak, urutan baca (baris atas-bawah, kanan-ke-kiri), webtoon tinggi (> 2x lebar) dipecah menjadi ubin bertumpang tindih (maks 30 ubin).
- `services/manga_pipeline.py`: tiap kotak dipotong (margin 6 px, sisi terpanjang dijepit 512–2048 px) dan dikirim ke `translate_image_data_url` secara berurutan. Gagal satu kotak: kotak itu tanpa teks; 3 gagal beruntun tanpa satu pun berhasil: error halaman. Tanpa kotak/terjemahan: fallback terjemahan seluruh gambar.
- `services/manga_overlay.py`: hapus teks dengan warna median tepi kotak (numpy), tulis terjemahan dengan Pillow (ukuran font 8–40 via pencarian biner, pembungkusan kata, elipsis bila tetap tak muat). Font bawaan Pillow; `MANGA_OVERLAY_FONT` opsional menunjuk berkas TTF.
- API tetap stateless: `POST /api/translate/images` menerima `overlay=true` dan menambah `boxes` pada event `page` (mode `overlay`). `POST /api/translate/images/export-pdf` menerima `boxes` dan `include_text_pages`; gambar overlay dirender saat ekspor dari file yang diunggah ulang. `boxes` dari klien divalidasi ketat (tipe int, 0..100000, maks 100 per halaman, teks maks 2000 karakter, jumlah halaman cocok).
- Dependensi baru: `onnxruntime`, `pillow`, `numpy` (sudah terpasang; ditulis eksplisit karena diimpor langsung). `opencv-python-headless` (disetujui) **ditunda**: MVP memakai isi warna rata, OpenCV baru perlu untuk inpainting latar rumit.

## Consequences / Residual
- Akurasi pada manga/webtoon/SFX nyata belum terbukti; isi warna rata merusak gelembung berlatar gradien atau teks tanpa gelembung.
- Satu permintaan per gelembung: sekitar 15 kotak x 3 dtk = 45 dtk/halaman; fitur opt-in, maks 25 kotak/halaman.
- Kotak kecil tanpa konteks halaman bisa menghasilkan terjemahan buruk; belum ada penggabungan kotak satu gelembung atau konteks percakapan.
- Lisensi dataset pelatihan detektor belum diverifikasi.
- Ekspor mengunggah ulang gambar (hingga 100 MB di mesin lokal).

## Files
`backend/services/manga_detector.py`, `manga_pipeline.py`, `manga_overlay.py`, `image_batch.py` (PDF dengan overlay), `backend/routers/image_batch_translate.py`, `backend/scripts/fetch_detector_model.py`, `backend/requirements.txt`, `.gitignore`, `src/lib/pdfTranslate.ts`, `src/components/ImageFolderTranslatePanel.tsx`. Tes: `test_manga_detector.py`, `test_manga_pipeline.py`, `test_manga_overlay.py`, `test_image_batch.py`, `test_fetch_detector_model.py`, `test_routers/test_translate_images.py`.
