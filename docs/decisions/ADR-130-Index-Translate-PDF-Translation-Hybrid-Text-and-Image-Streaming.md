# ADR-130: Terjemahan PDF dengan Index-Translate (Hibrid Teks/Gambar, Streaming NDJSON)

## Status
Accepted (2026-10-24). Belum diuji live dengan PDF nyata (komik, scan buku); hanya tes unit/router dengan provider tiruan.

## Context
`POST /api/translate/image` (ADR-129) hanya menerima satu gambar. Pengguna ingin mengirim PDF dan mendapat terjemahan isinya memakai `index-translate-2b` lokal (RTX 3050 4 GB, sekitar 3 detik per halaman).

## Decision
- `POST /api/translate/pdf` (multipart: `file`, `model`, `target_lang`, `lm_url`) di `backend/routers/pdf_translate.py`. Hanya model Index-Translate (400 selain itu).
- Per halaman: lapisan teks >= 20 karakter non-spasi diterjemahkan lewat prompt teks (dipecah `split_into_chunks`, 2500 karakter); selain itu halaman dirender ke PNG dan dikirim lewat prompt gambar (helper bersama `translate_image_data_url`, `max_tokens=1024`, suhu provider).
- Render mengikuti panduan resmi `docs/image_translate.md`: 150 dpi, sisi terpanjang dijepit ke 512–2048 px.
- Respons `application/x-ndjson`: `start`, `page`/`page_error`, `done`. Halaman diproses berurutan (VRAM 4 GB), satu halaman gagal tidak menghentikan sisanya, koneksi putus menghentikan loop.
- Tidak ada penyimpanan di server dan tidak ada registry in-memory baru, jadi tidak ada kunci workspace baru; workspace tetap lewat `get_db`.
- Dependensi baru: `pymupdf>=1.24` (disetujui pengguna). Catatan: lisensi AGPL-3.0 (atau komersial Artifex); perlu ditinjau bila proyek didistribusikan.
- Batas: 20 MB (dibaca bertahap, 413 saat terlampaui), 50 halaman (413), bukan PDF/korup/terenkripsi/tanpa halaman (400). PDF dibuka dari bytes di memori, tanpa path, tanpa mengunduh URL.
- Frontend: `src/lib/pdfTranslate.ts` (pembaca NDJSON) dan `PdfTranslatePanel` di `TranslatePage`; hasil digabung di klien, salin/unduh .txt, tanpa localStorage.

## Alternatives
- pypdfium2+pypdf (permisif, dua paket) dan pdf.js di frontend: ditolak pengguna demi PyMuPDF.
- Selalu gambar: lebih lambat dan kurang akurat untuk PDF teks.
- Simpan ke Thread/DB: skema dan isolasi workspace lebih besar, di luar MVP.

## Consequences / Residual
- Bukan penerjemah manga dengan overlay: keluaran hanya teks per halaman, tanpa menimpa teks pada gambar.
- Risiko parser native PDF (PDF berbahaya) berjalan di proses server; dimitigasi batas ukuran/halaman/piksel dan penolakan PDF terenkripsi. Tidak ada timeout per halaman selain timeout provider.
- Satu halaman teks sangat padat bisa terpotong 1024 token pada mode gambar; mode teks tidak dibatasi token.
- Asumsi belum divalidasi: keterbacaan 150 dpi oleh 2B, ambang 20 karakter pada scan ber-OCR-layer buruk.

## Files
`backend/routers/pdf_translate.py`, `backend/services/pdf_pages.py`, `backend/routers/image_translate.py` (helper diekstrak), `backend/main.py`, `backend/requirements.txt`, `src/lib/pdfTranslate.ts`, `src/components/PdfTranslatePanel.tsx`, `src/pages/TranslatePage.tsx`. Tes: `tests/test_services/test_pdf_pages.py`, `tests/test_routers/test_translate_pdf.py`.
