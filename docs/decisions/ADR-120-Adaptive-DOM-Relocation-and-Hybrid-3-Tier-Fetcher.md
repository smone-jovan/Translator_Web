# ADR-120: Adaptive DOM Relocation, Playwright Stealth Hardening & Hybrid 3-Tier Fetcher

## Status
Accepted (diimplementasikan pada commit `ccdb5c0`, Issue #20; ADR ditulis retroaktif pada audit 2026-10-16)

## Date
2026-10-15

## Context
Commit `0bbadc4` (Issue #9) menetapkan hierarki scraper 3 tingkat di CLAUDE.md (bagian "Scraper Architecture Tiering") dan menambahkan `StealthyNovelAdapter` (`stealth_base.py`) yang menyarankan Scrapling (`StealthyFetcher`) untuk situs baru yang dilindungi Cloudflare. Masalah yang tersisa:

1. **Selector rapuh**: parser Novalpie, URL generik, dan TOC bergantung pada selector CSS tetap (`#chapter-…`, `.reader-content`). Saat situs mengganti struktur HTML/kelas CSS, ekstraksi gagal total sampai kode diperbarui.
2. **Ketergantungan pada paket opsional**: `StealthyNovelAdapter` melempar `RuntimeError("Scrapling belum terinstal…")` bila `scrapling` tidak terpasang, padahal penambahan dependensi butuh persetujuan pengguna (CLAUDE.md).
3. **Playwright pasif terhadap Cloudflare**: loop polling hanya menunggu challenge selesai sendiri; font/media/tracker ikut dimuat; konten bab yang dikirim lewat XHR/JSON tidak dimanfaatkan.
4. **URL generik & TOC** hanya memakai satu jalur HTTP; halaman SPA kosong atau challenge Cloudflare langsung gagal.

---

## Decisions

### 1. Adaptive DOM Relocation Engine (`backend/services/scrapers/adaptive_dom.py`)
- `AdaptiveDOM.select_one(soup, selectors, domain=…, key=…, role=…, adaptive=True, auto_save=True)` mencoba selector biasa terlebih dahulu. Saat cocok, *signature* elemen (tag, token kelas/id, nama atribut, pola anak, kepadatan teks) disimpan per `domain`/`key` ke `backend/data/adaptive_selectors.json`. Signature juga disimpan saat kontainer hasil **heuristik** yang menang (`adaptive_dom.py:346-349`), sehingga tebakan yang salah bisa menjadi signature acuan berikutnya.
- Bila semua selector gagal, elemen direlokasi dengan `compute_similarity()` (gabungan berbobot kemiripan Jaccard) terhadap signature tersimpan; ambang minimum skor `0.42`.
- Fallback terakhir untuk `role="content"`: `find_best_content_container()` (skor kepadatan prosa); untuk `role="title"`: `find_best_title_element()`.
- Tanpa dependensi baru: hanya BeautifulSoup yang sudah ada. API meniru `adaptive=True` / `auto_save=True` milik Scrapling agar migrasi ke Scrapling kelak mudah.

### 2. Playwright Hardening di `novalpie.py` (Tier 2)
- `_inject_scrapling_stealth_scripts(context, block_webrtc=True, hide_canvas=True)` dipasang pada setiap `browser.new_context()`.
- `_install_resource_shield(page)` memblokir tipe resource `font`, `media`, `websocket`, `manifest`, `texttrack`, `eventsource` dan domain tracker (Google Analytics, GTM, DoubleClick, Clarity, Baidu, CNZZ, Hotjar). Gambar ilustrasi tetap dimuat.
- `_try_solve_cloudflare_turnstile(page)` mencari iframe `challenges.cloudflare.com`/turnstile dan mengklik checkbox secara aktif di dalam loop polling, tidak lagi hanya menunggu pasif.
- `_attach_xhr_chapter_capture(page, chapter_id)` menangkap respons JSON bab sebagai sumber cadangan bila DOM hasil dekripsi kosong.
- Arsitektur `_get_thread_browser()` dan *Adaptive State Polling 400ms* (anti *Premature Ready Bug* `正在准备内容`) tetap dipertahankan sesuai CLAUDE.md.

### 3. Native Fallback di `StealthyNovelAdapter` (`stealth_base.py`, Tier 3)
- Bila `HAS_SCRAPLING == False`, `fetch_stealth_page()` memakai Playwright/Patchright bawaan dengan skrip stealth, resource shield, dan solver yang sama, alih-alih melempar `RuntimeError`.

### 4. Hybrid 3-Tier Fetcher `fetch_html_adaptive()` (`backend/routers/scrape.py`, dipakai juga oleh `toc.py`)
1. **Tier 1a**: `create_safe_async_client` (validasi SSRF + hook redirect).
2. **Tier 1b**: `curl_cffi` dengan impersonasi `chrome120`, dipakai saat Tier 1a mendapat 403/429/503, HTML kosong, atau halaman challenge. Redirect diikuti manual lewat `follow_redirects_safely`, dan setiap hop divalidasi sebelum diminta (ADR-126).
3. **Tier 3**: `StealthyNovelAdapter.fetch_stealth_page(solve_cloudflare=True, disable_resources=True)` dengan `workspace` eksplisit, dipakai saat masih challenge atau halaman SPA kosong (probe markdown kurang dari 50 karakter).
- `html_to_markdown()` memilih kontainer konten via `AdaptiveDOM.select_one(...)`.

### 5. Tes
- `backend/tests/test_services/test_adaptive_playwright_scrapling.py`: relokasi DOM setelah redesign, parser Novalpie adaptif, resource shield (blokir font/tracker tetapi bukan gambar), solver Turnstile, eskalasi SSRF + Playwright pada `fetch_html_adaptive`.

---

## Consequences

### Positive
- Scraper tahan terhadap perubahan struktur HTML tanpa perubahan kode, selama elemen masih mirip secara struktural.
- Situs ber-Cloudflare dapat ditangani tanpa memasang Scrapling; nol dependensi baru.
- Halaman lebih cepat dimuat karena font, media, dan tracker diblokir.

### Negative / Trade-offs
- `adaptive_selectors.json` ditulis saat runtime (`auto_save=True`), padahal file ini dilacak git. Akibatnya working tree terlihat berubah setelah scraping. **Tindak lanjut yang disarankan:** pindahkan penyimpanan runtime ke file yang di-ignore (mis. `backend/data/adaptive_selectors.local.json`) dan jadikan file yang dilacak sebagai seed baca-saja.
- Relokasi berbasis kemiripan bisa memilih elemen yang salah pada redesign besar; ambang `0.42` dan `min_text_len` membatasi risiko ini.
- Solver Turnstile berbasis klik bersifat *best effort* dan bisa berhenti bekerja bila Cloudflare mengubah widget-nya.

### Residual Risks (terverifikasi council 2026-10-17, belum diperbaiki)
- ~~**SSRF via hop redirect (Tier 1b & Tier 3)**~~ — **ditutup di ADR-126.** Tier 1b kini mengikuti redirect secara manual dan memvalidasi tiap hop sebelum diminta. Tier 3 dilindungi egress proxy lokal yang memvalidasi IP setiap koneksi browser, ditambah guard CDP `Fetch`. Rencana awal "validasi lewat `page.route`" terbukti tidak cukup karena `page.route` tidak dipanggil untuk hop redirect.
- **Store signature global & dilacak git**: `adaptive_selectors.json` satu file untuk seluruh proses, tidak dipisah per workspace. Domain yang di-scrape dari workspace `ghost` ikut tercatat di file yang sama dengan `main` (lihat `docs/ghost-mode-security.md`). Tindak lanjut sama dengan poin `.local.json` di atas, ditambah pemisahan per workspace.
