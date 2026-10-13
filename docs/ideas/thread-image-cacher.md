# Idea: One-Click Thread Image Cacher & Reader Proxy

## Problem Statement
How Might We allow readers to cache all remote illustrations across a web novel in a single background operation so images render instantly in the web reader without hotlink failure or latency?

## Recommended Direction
1. **Interactive Trigger**:
   - Di sebelah tab filter `Illustrated (N)` pada `ChapterListControls.tsx`, sediakan tombol action:
     `[Download/Cloud] Cache Images` (atau menampilkan badge centang `Cached` jika semua gambar sudah ada di disk).
2. **Non-Blocking Background Caching (`POST /api/threads/{id}/cache-images`)**:
   - Backend memindai seluruh URL gambar unik di seluruh bab thread (menggunakan regex `IMAGE_TAG_PATTERN` yang sudah ada).
   - Menjalankan `prefetch_remote_images` secara asinkron (concurrency 10, connect timeout 3s, aman DNS/URL mati).
   - Menyimpan ke disk cache `uploads/cache/images/{hash}.{ext}`.
3. **Live Non-Intrusive Progress**:
   - Status polling ringan via toast/progress bar non-blocking: *"Caching images: 42 / 308 (14%)..."*.
   - Pembaca tetap bebas membaca atau membuka bab lain tanpa modal yang menghalangi layar.
4. **Seamless Reader Image Proxy (`GET /api/images/proxy?url=...`)**:
   - Di `src/lib/utils.ts` (`renderMarkdown`), gambar remote dilewatkan melalui `/api/images/proxy?url={encoded}`.
   - Endpoint backend langsung menyajikan file cache dari disk (kecepatan <5ms) jika sudah terunduh, atau mengunduh dan menyimpannya secara transparan jika belum.

## Key Assumptions to Validate
- [x] Endpoint proxy `/api/images/proxy` bekerja mulus tanpa melanggar header keamanan CSP browser.
- [x] Disk cache yang dipakai berbagi struktur 100% dengan cache EPUB Exporter (`uploads/cache/images/`), sehingga sekali cache menguntungkan web reader dan export sekaligus.

## MVP Scope
- **In-Scope**:
  - Tombol `Cache Images` di samping tab filter `Illustrated` di halaman bab.
  - Endpoint `POST /api/threads/{id}/cache-images` & `GET /api/threads/{id}/cache-images/status`.
  - Endpoint `GET /api/images/proxy` dengan header Cache-Control efisien dan perlindungan path traversal.
  - Live progress feedback di frontend.
- **Not Doing (and Why)**:
  - *Belum membuat Galeri Foto Masonry terpisah*: Fokus utama saat ini adalah kelancaran membaca bab, bukan browsing galeri foto.
  - *Tidak menulis ulang URL di SQLite DB (`content_original`)*: Menulis ulang database mentah berbahaya jika ingin re-scrape atau sinkronisasi sumber asli. Pendekatan proxy jauh lebih bersih dan non-destruktif.

## Open Questions
- Estimasi ukuran dan jumlah gambar ditampilkan dalam tooltip atau teks kecil pada tombol.
