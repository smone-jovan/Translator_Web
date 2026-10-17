# Register Risiko Sisa (Residual Risks)

Status per 2026-10-17. Aturan pemeliharaan register ini ada di ADR-127.

Satu tempat untuk semua risiko yang **sudah diketahui tetapi belum diperbaiki**, yang sebelumnya tersebar di bagian "Negative / Residual Risks" ADR-119–126 dan `docs/ghost-mode-security.md`. ADR asal tetap menjadi sumber detail teknis; register ini menjadi sumber status dan prioritas.

**Prioritas**
- **P1**: dampak keamanan/privasi atau kehilangan data; dikerjakan lebih dulu.
- **P2**: perilaku salah yang terlihat pengguna, atau utang yang membuat bug berikutnya mudah muncul.
- **P3**: kosmetik, kenyamanan, atau batasan yang disengaja.

**Status**
- **Terbuka**: belum dikerjakan.
- **Diterima**: batasan yang disengaja, tidak direncanakan diperbaiki.

---

## A. Keamanan & privasi

Akar bersama R-01..R-06: backend berjalan di `0.0.0.0` tanpa autentikasi. Siapa pun yang bisa mengirim request ke port 8000 di jaringan yang sama dianggap tepercaya.

| ID | Risiko | Dampak | Prio | Asal | Status | Arah perbaikan |
| --- | --- | --- | --- | --- | --- | --- |
| R-01 | API tidak punya autentikasi; workspace dipilih dari header `X-Workspace` / cookie yang tidak ditandatangani | Perangkat lain di Wi-Fi yang sama bisa membaca dan mengubah data, termasuk `ghost.db` tanpa PIN | P1 | ghost-mode-security.md | Terbuka | Token sesi `httponly` bertanda tangan (HMAC) yang diterbitkan setelah PIN/sandi; `resolve_workspace()` hanya menerima `ghost` dengan token valid. Menutup sebagian besar R-02..R-06 |
| R-02 | `PUT /settings` bisa mengubah `gs.openai_url` | Pemanggil API bisa mengarahkan API key OpenAI ke host miliknya (key Gemini/OpenRouter sudah terkunci ke host resmi) | P1 | ADR-126 | Terbuka | Ikut tertutup oleh R-01; alternatif sementara: wajib PIN untuk mengubah `openai_url` |
| R-03 | URL LM Studio bebas (per desain, tanpa key) | Backend bisa diminta menghubungi host LAN mana pun lewat provider `lm_studio` (SSRF terbatas, respons dikembalikan) | P2 | ADR-126 | Terbuka | Ikut tertutup oleh R-01; opsional: allowlist host LAN yang diset di Settings |
| R-04 | PIN Ghost: bisa diganti tanpa PIN lama, default `03697`, tanpa rate-limit, disimpan polos di SQLite dan `localStorage` (`ghost_pin`) | Siapa pun yang memegang perangkat atau jaringan bisa menebak/mengganti PIN | P2 | ghost-mode-security.md, ADR-083 | Diterima (sementara) | Wajib PIN lama, rate-limit, hash PIN, hapus `ghost_pin` dari `localStorage` |
| R-05 | `mask_secret` memperlihatkan 4+4 karakter PIN/secret panjang | PIN 8–12 karakter hampir terbaca dari `GET /settings` | P2 | ADR-125 | Terbuka | Mask penuh untuk PIN; 4 karakter terakhir saja untuk API key |
| R-06 | Cookie workspace `httponly=False`, umur 30 hari | Perangkat yang ditinggal dalam mode `ghost` langsung terbuka di `ghost` | P3 | ghost-mode-security.md | Diterima | Ikut R-01 (token terpisah dari penanda UI); perpendek umur cookie `ghost` |
| R-07 | DNS rebinding di Tier 1a (httpx) dan Tier 1b (curl_cffi): validasi lalu klien me-resolve ulang | Blind SSRF ke host internal lewat domain ber-TTL pendek | P2 | ADR-126 | Terbuka | Sambungkan ke IP hasil validasi (transport httpx kustom / opsi `resolve` curl), atau arahkan kedua tier lewat egress proxy yang sama |
| R-08 | Jalur scraper tanpa egress proxy: Scrapling (`strict_ssrf=False`, `fetch_stealth_batch`), Playwright Novalpie, curl_cffi SFACG (redirect masih diikuti) | Domain-domain ini dipatok ke situs tetap, jadi butuh open redirect di situs itu agar bisa disalahgunakan | P3 | ADR-126 | Terbuka | Default `strict_ssrf=True`; SFACG pakai `follow_redirects_safely` |
| R-09 | Proxy per-context di Windows bergantung pada versi Playwright; Patchright belum diuji | Bila tidak didukung, Tier 3 gagal (fail closed), bukan bocor; fitur scrape situs Cloudflare berat bisa berhenti | P2 | ADR-126 | Terbuka | Uji sekali di mesin Windows pengguna; bila gagal, proxy di level launch untuk browser khusus scrape URL bebas |
| R-10 | Keep-alive http biasa di egress proxy diteruskan ke IP pertama | Bukan SSRF (IP sudah divalidasi), tetapi request ke host lain bisa salah alamat | P3 | ADR-126 | Terbuka | Parse per request atau tutup koneksi setelah satu respons |
| R-11 | Cookie login Novalpie global (`backend/.env`) dipakai kedua workspace | Scraping dari `ghost` memakai akun yang sama dengan `main` | P3 | ghost-mode-security.md | Diterima | Prioritaskan cookie per workspace di atas `.env` |
| R-12 | `adaptive_selectors.json` satu file untuk kedua workspace, dilacak git, ditulis saat runtime | Jejak domain `ghost` tercatat di file bersama dan bisa ikut ter-commit | P2 | ADR-120, ghost-mode-security.md | Terbuka | Simpan runtime ke `backend/data/adaptive_selectors.<workspace>.local.json` (di-ignore); file yang dilacak jadi seed baca-saja |

## B. Data & kebenaran fungsional

| ID | Risiko | Dampak | Prio | Asal | Status | Arah perbaikan |
| --- | --- | --- | --- | --- | --- | --- |
| R-13 | Kolom `auto_extracted` fantom di `LorebookEntry` | Filter/badge "auto" di Glossary Studio tidak pernah cocok; statistik selalu 0 | P2 | ADR-123 | Terbuka | Kolom + migrasi `app.db`/`ghost.db`, isi di `auto_save_glossary()`; sementara sembunyikan filter |
| R-14 | Pemanggil non-stream kehilangan sinyal "terpotong" (`POST /translate`, fallback non-stream, ekstraksi glosarium, polish judul) | Teks terpotong tersimpan tanpa tanda; baru tertangkap guard fidelity / "Fix Truncated" | P2 | ADR-121 | Terbuka | Kembalikan status terpotong lewat `_chat_completion_with_status` |
| R-15 | Batas kuota glosarium ada di dua fungsi (`ContextEngine` vs `routers/lorebook`) | Aturan prioritas bisa menyimpang lagi (pernah terjadi: fallback 50 vs 150) | P2 | ADR-122, ADR-123 | Terbuka | Satukan ke satu fungsi |
| R-16 | `last_used_at` bercampur zona waktu (lokal / `func.now()` / UTC) dan disegarkan oleh edit apa pun | Di UTC+7 istilah manual/import tampak ±7 jam "lebih baru"; urutan eviction = "terakhir disentuh" | P2 | ADR-122, ADR-125 | Terbuka | Seragamkan ke UTC; pisahkan `last_used_in_prompt_at` dari `updated_at` |
| R-17 | Rebalancing kuota semua thread berjalan sinkron di request Settings | Perpustakaan besar membuat simpan Settings lambat | P3 | ADR-123 | Terbuka | Jalankan sebagai job latar |
| R-18 | Guard MTL berbasis heuristik (ambang CJK, loop < 4 kali lolos, `PHRASE_LOOP_RE` hanya Latin) | Peringatan palsu / loop pendek tidak terdeteksi | P3 | ADR-121 | Diterima | Kalibrasi ambang dengan data nyata |
| R-19 | Relokasi AdaptiveDOM bisa memilih elemen salah pada redesign besar; solver Turnstile *best effort* | Scrape menghasilkan konten salah atau gagal saat Cloudflare berubah | P3 | ADR-120 | Diterima | Ambang `0.42` + `min_text_len` membatasi; pantau |

## C. Pocket Offline Cache (HP)

| ID | Risiko | Dampak | Prio | Asal | Status | Arah perbaikan |
| --- | --- | --- | --- | --- | --- | --- |
| R-20 | Salinan bab tidak dicek identitasnya (bab dihapus/di-reset, ID dipakai ulang) | Teks lama atau bab lain bisa tampil saat offline | P2 | ADR-124 | Terbuka | Simpan judul/urutan/hash; tolak salinan yang tidak cocok dengan snapshot thread |
| R-21 | Menghapus novel di server tidak menghapus salinan offline di HP lain | Data (termasuk `ghost`) tetap ada di HP | P2 | ghost-mode-security.md | Terbuka | Sinkronkan daftar thread saat online dan buang yang hilang |
| R-22 | Tanpa Service Worker; penyimpanan tidak persisten di HTTP | Offline hanya selama tab terbuka; Safari bisa menghapus cache | P3 | ADR-124 | Diterima | Butuh HTTPS di LAN (sertifikat lokal) |
| R-23 | Gambar ilustrasi tidak ikut disimpan | Gambar rusak saat offline | P3 | ADR-124 | Terbuka | Simpan blob gambar per bab (dengan batas ukuran) |
| R-24 | Statistik Settings memuat semua isi bab (`getAll()`); cache tanpa batas total | Settings berat dengan ratusan bab | P3 | ADR-124 | Terbuka | Simpan ukuran per entri, gunakan cursor; batas total + LRU |
| R-25 | Celah kecil: `selectedChapterIdx` bisa bergeser, baca-tulis `refresh*IfCached` beda transaksi, status `busy` per instance panel | Hapus cache bisa terbatalkan; unduhan ganda | P3 | ADR-124 | Terbuka | Satu transaksi; status unduhan global |
| R-26 | Fallback 5 detik: server lambat tapi sehat tetap memunculkan Offline; buka-dingin di jaringan menggantung ±11 detik; polling thread menunda fallback | Badge/toast Offline sesaat yang tidak perlu; tunggu lama | P3 | ADR-124 | Diterima (sebagian) | Langsung coba salinan bab begitu snapshot thread dipakai |
| R-27 | Handler pemulihan layar memanggil `fetchThread` di setiap focus/visibility; bab gagal tetap terpilih di sesi offline | Request menumpuk; toast yang sama berulang | P3 | ADR-124 | Terbuka | Guard in-flight seperti retry offline; reset pilihan bab |

## D. UX, aksesibilitas, multi-tab

| ID | Risiko | Dampak | Prio | Asal | Status | Arah perbaikan |
| --- | --- | --- | --- | --- | --- | --- |
| R-28 | Pindah workspace me-reload tab lain walau ada isian belum disimpan / stream terjemahan berjalan | Input hilang | P2 | ADR-124, ADR-125 | Terbuka | Tunda reload sampai tab idle, atau tampilkan banner "workspace berubah — muat ulang" |
| R-29 | Kontras: ring fokus `ring-ring/50` < 3:1 di tema white; tombol konfirmasi putih di red-500 (3,8:1); toggle HIDE 3,2:1 | Sulit dilihat pengguna low-vision | P3 | ADR-125 | Terbuka | Naikkan token warna |
| R-30 | Tombol dialog konfirmasi 36 px; fokus tidak kembali ke tombol gear setelah overlay ditutup; badge Offline tak terlihat di mode imersif | Target sentuh kecil; navigasi keyboard putus | P3 | ADR-124, ADR-125 | Terbuka | 44 px; kembalikan fokus ke pemicu |
| R-31 | Error startup Control Hub tidak tampil di konsol; fitur visual khusus Windows | Pengguna harus membuka Live Logs / `launcher.log` | P3 | ADR-119 | Diterima | — |

## E. Pengujian & tooling

| ID | Risiko | Dampak | Prio | Asal | Status | Arah perbaikan |
| --- | --- | --- | --- | --- | --- | --- |
| R-32 | Tidak ada runner E2E frontend di repo; verifikasi UI dijalankan agent dengan skrip di luar repo | Regresi UI tidak tertangkap otomatis | P2 | ADR-125 | Terbuka | Tambah Playwright E2E (butuh persetujuan dependensi) |
| R-33 | `test_graceful_cancellation` meninggalkan batch aktif; tanpa timeout per tes | `test_sequential_processing_transition` menggantung bila urutan berubah | P3 | ADR-125 | Terbuka | Bersihkan registry batch di fixture; timeout per tes |
| R-34 | `TestClient(app)` menjalankan `init_db` terhadap `./app.db` di direktori kerja | pytest harus dijalankan dari root repo | P3 | ADR-125 | Terbuka | Override `DATABASE_URL` ke tmp di conftest |
| R-35 | Tes browser SSRF dilewati bila Chromium tidak bisa dijalankan | Lapisan proxy tidak teruji di mesin tanpa browser | P3 | ADR-126 | Diterima | `PW_CHROMIUM_EXECUTABLE` untuk menunjuk executable |
| R-36 | Review independen putaran kedua ADR-126 tidak selesai (reviewer dihentikan filter keamanan) | Verifikasi putaran kedua hanya oleh penulis | P2 | ADR-126 | Terbuka | Review ulang egress proxy oleh reviewer lain / manusia |
| R-37 | "Zero bug" tidak bisa dibuktikan mutlak | — | — | ADR-125 | Diterima | Register ini sebagai daftar yang jujur |

---

## Urutan pengerjaan yang disarankan

1. **R-01** (autentikasi API + token workspace). Satu perubahan ini menutup atau mengecilkan R-02..R-06 dan membuat sebagian besar model ancaman LAN aman.
2. **R-12, R-07, R-36**: privasi jejak `ghost`, rebinding di tier HTTP, dan review ulang proxy.
3. **R-13..R-16, R-20, R-21, R-28**: kebenaran data dan perilaku yang terlihat pengguna.
4. Sisanya (P3) dikerjakan bila menyentuh area yang sama.
