# ADR-126: Outbound Request Hardening — Provider Key Allowlist & SSRF Egress Proxy

## Status
Accepted (diimplementasikan di commit yang menambahkan ADR ini, 2026-10-17). Menutup risiko sisa SSRF hop redirect (ADR-120) dan kebocoran API key (ADR-122) yang dicatat di ADR-125.

## Date
2026-10-17

## Context
ADR-125 mencatat dua risiko sisa dari council kedua:

1. **API key terkirim ke URL pilihan klien.** Request AI membawa API key sebagai `Bearer`. Untuk provider `openai`, `lm_url` dari request menimpa `gs.openai_url`. Provider lain dicek dengan substring (`"gemini" in url`, `"openrouter.ai" in url`). Saat implementasi ternyata cakupannya lebih luas dari yang dicatat:
   - `routers/translate.get_lm_url` meneruskan `lm_url` mentah tanpa resolver.
   - `AIProviderFactory` bahkan **berganti provider** berdasarkan substring URL, misalnya `https://evil.example/gemini` memilih Gemini.
   - Akibatnya key Gemini/OpenAI/OpenRouter bisa dikirim ke host mana pun lewat `/translate` dan `/translate/stream`.
2. **SSRF lewat hop redirect di Tier 1b/Tier 3** (`fetch_html_adaptive`).

Temuan empiris selama pengerjaan:

- `page.route` Playwright **tidak dipanggil untuk hop redirect**. Rencana di ADR-120 ("validasi per-request lewat `page.route`") tidak cukup: hop ke `localhost` tetap diminta.
- CDP `Fetch` (requestStage=Request) menjeda setiap hop. Namun reviewer independen menunjukkan bahwa guard berbasis CDP pada satu target **masih bisa ditembus**. Jalur yang terbukti bocor:
  - `window.open`;
  - form `target=_blank` (POST);
  - WebSocket di Worker;
  - `WebSocketStream`;
  - speculation rules;
  - SharedWorker;
  - iframe lintas situs (proses terpisah).
- Reviewer yang sama menemukan **SSRF reflektif lama** di `NovelUpdatesAdapter`. Judul berisi `novelupdates.com/series/` diambil apa adanya dengan curl_cffi, tanpa validasi dan dengan redirect diikuti. Isinya dikembalikan lewat API, misalnya `http://169.254.169.254/...?novelupdates.com/series/x`.

---

## Decisions

### 1. Allowlist host untuk API key (`services/ai/settings.py`)
- `is_trusted_provider_url(provider, url, gs)` mencocokkan **hostname hasil parse**, bukan substring:
  - Gemini: `generativelanguage.googleapis.com`.
  - OpenRouter: `openrouter.ai`.
  - OpenAI: `api.openai.com`.
  - Syaratnya https, port standar, dan tanpa userinfo.
  - Untuk OpenAI, URL yang sama persis dengan `gs.openai_url` (endpoint kompatibel pilihan pemilik) juga diterima.
- Fungsi ini dipakai di tiga tempat:
  - `resolve_active_base_url`: URL request yang tidak tepercaya diabaikan dan diganti URL resmi atau `gs.openai_url`.
  - `AIProviderFactory`: pergantian provider dan pemakaian `base_url` hanya terjadi bila URL tepercaya.
  - `translate.get_lm_url`: kini selalu lewat resolver.
- LM Studio tetap menerima URL LAN apa pun karena tidak membawa key.

### 2. Tier 1b: redirect manual tervalidasi (`services/security.follow_redirects_safely`)
- curl_cffi dijalankan dengan `allow_redirects=False`.
- Setiap `Location` di-resolve dengan `urljoin` dan divalidasi **sebelum** diminta, maksimal 5 hop.
- Bila batas hop terlampaui, `TooManyRedirects` dilempar dan fetch naik ke tier berikutnya.

### 3. Tier 3: egress proxy yang memvalidasi (`services/egress_proxy.py`) sebagai lapisan utama
- Proxy forward lokal: `127.0.0.1`, port acak, thread daemon, asyncio, satu instance per proses.
- Untuk setiap `CONNECT` (https/wss) dan request http absolut, proxy:
  1. me-resolve host sendiri;
  2. menolak bila **ada** alamat non-publik (403 bertanda `X-SSRF-Blocked`);
  3. lalu menyambung ke **IP yang sudah divalidasi**, yang sekaligus menutup DNS rebinding pada Tier 3.
- HTTP biasa ditulis ulang ke origin-form dengan header hop-by-hop dibuang dan `Connection: close`.
- `StealthyNovelAdapter._fetch_playwright_sync` membuat context dengan `proxy={"server": ..., "bypass": "<-loopback>"}`. Tanpa `<-loopback>`, Chromium mem-bypass proxy untuk localhost.
- **Fail closed**: bila navigasi berhasil tetapi proxy tidak menangani satu koneksi pun (konfigurasi proxy per-context diabaikan), halaman ditolak dengan `RuntimeError`.
- Penolakan proxy pada navigasi utama dipetakan ke `HTTPException(400)`.
- `fetch_stealth_page(strict_ssrf=True)` memaksa jalur native ini, bukan Scrapling, karena Scrapling tidak punya hook per-request. `fetch_html_adaptive` (URL pengguna) memakai `strict_ssrf=True`.
- `service_workers="block"` dipasang pada context.

### 4. Tier 3: guard CDP `Fetch` sebagai lapisan kedua (`stealth_base._install_ssrf_guard`)
- Menjeda dokumen, hop redirect, subresource, fetch/XHR, dan request Worker di target halaman, lalu menggagalkan host yang gagal `validate_external_url`.
- Gunanya kegagalan cepat dan pesan 400 yang jelas.
- Error validator apa pun dianggap tolak, dan request yang tidak diteruskan selalu digagalkan, sehingga tidak ada hang 45 detik.
- `blocked_document` hanya dihitung untuk frame utama.
- Bila guard gagal dipasang, fetch gagal (fail closed).

### 5. Novel Updates (`services/scrapers/novel_updates.py`)
- `normalize_novelupdates_series_url` mensyaratkan:
  - host `novelupdates.com` / `www.novelupdates.com`;
  - path `/series/`;
  - http/https tanpa userinfo, port standar;
  - keluarannya dipaksa https.
- URL tanpa skema yang biasa ditempel pengguna tetap diterima.
- `_fetch_series_page` dipakai oleh `_enhance_metadata` dan `_scrape_detail_page`, dengan `follow_redirects_safely`.

### 6. Validator
`validate_external_url` / `resolve_public_ip`:
- `UnicodeError` IDNA dan nama tak ter-resolve menjadi 400 (sebelumnya 500).
- Alamat hasil resolve yang tidak bisa diklasifikasi diperlakukan sebagai terlarang.

---

## Verification
- **TDD**: semua tes ditulis dan terbukti merah sebelum perbaikan. Berkas tesnya:
  - `test_ai_provider_url_allowlist.py` (39 tes): termasuk factory × 4 provider × 6 URL jahat;
  - `test_ssrf_redirect_hops.py` (33 tes): helper redirect, Tier 1b dengan curl_cffi palsu, unit proxy, guard CDP, dan browser sungguhan;
  - `test_novel_updates_ssrf.py` (7 tes).
- **Browser sungguhan** (dilewati bila Chromium tidak tersedia): 12 vektor serangan dari halaman penyerang, yaitu fetch, Worker fetch, Worker WebSocket, WebSocket, WebSocketStream, SharedWorker, popup, form `_blank`, speculation prefetch, link prefetch, beacon, dan iframe lintas situs. Hasilnya: tidak satu pun request mencapai host internal.
  - Hop redirect dan subresource privat juga diblokir.
  - Proxy tetap memblokir navigasi privat walau guard CDP dimatikan.
- **Uji mutasi**: dengan resolver proxy dibuat permisif, 7 vektor browser gagal. Artinya tes benar-benar membuktikan peran proxy.
- **Probe tepi proxy** dengan resolver asli, semuanya 403/400 dan tidak ada hit ke server internal:
  - userinfo, IPv6 `[::1]`, IPv4-mapped, titik di akhir, huruf besar, IP desimal, `0.0.0.0`;
  - port 0/besar/non-numerik, origin-form, garbage;
  - dengan 50 koneksi idle, proxy tetap responsif.
- **Hasil akhir**: pytest 471 lulus, termasuk tes browser.
- **Review independen**: putaran pertama menghasilkan temuan di Context. Putaran kedua **tidak selesai**: reviewer dihentikan filter keamanan saat membaca kode proxy dan tidak memverifikasi apa pun. Verifikasi putaran kedua dilakukan penulis dengan menjalankan ulang skrip repro reviewer: SSRF Novel Updates tidak lagi memukul server, dan hang guard berubah dari 8,2 s timeout menjadi 400 dalam 0,2 s. Ditambah probe tepi di atas.

---

## Consequences

### Positive
- API key provider cloud hanya pernah dikirim ke host resmi atau ke `gs.openai_url` yang dipilih pemilik.
- Semua koneksi browser Tier 3 lewat satu titik kontrol yang memvalidasi IP sesungguhnya, termasuk jalur yang tidak terlihat oleh `page.route` atau CDP.
- SSRF reflektif Novel Updates tertutup.

### Negative / Residual Risks
- `PUT /settings` masih bisa mengubah `gs.openai_url`, sehingga siapa pun yang bisa memanggil API dapat mengarahkan key OpenAI. Ini sesuai model ancaman tanpa autentikasi (`docs/ghost-mode-security.md`). Key Gemini dan OpenRouter tidak bisa dialihkan dengan cara ini.
- URL LM Studio tetap bebas (per desain, tanpa key), jadi backend bisa diminta menghubungi host LAN apa pun lewat provider `lm_studio`.
- DNS rebinding masih mungkin di Tier 1a (httpx) dan Tier 1b (curl_cffi): validasi lalu klien me-resolve ulang. Proxy hanya menutupnya untuk Tier 3.
- Jalur yang tidak memakai proxy, dengan domain tetap atau tanpa input URL pengguna:
  - Scrapling (`strict_ssrf=False`, `fetch_stealth_batch`);
  - Playwright Novalpie (dipatok ke `novalpie.cc`);
  - curl_cffi SFACG (dipatok ke `book.sfacg.com`, redirect masih diikuti).
- Pada jalur http biasa, koneksi keep-alive yang dipakai ulang Chromium untuk host lain diteruskan ke IP yang sudah divalidasi pertama kali. Ini bukan SSRF, tetapi `Host` bisa tidak cocok.
- Proxy per-context butuh versi Playwright yang mendukungnya di Windows. Bila tidak didukung, pemeriksaan fail-closed membuat Tier 3 gagal (lalu jatuh ke hasil tier sebelumnya), bukan bocor diam-diam.
- Patchright (opsional) belum diuji dengan proxy/guard ini.
- Tes browser dilewati di mesin tanpa Chromium yang bisa dijalankan. Variabel `PW_CHROMIUM_EXECUTABLE` tersedia untuk menunjuk executable.
