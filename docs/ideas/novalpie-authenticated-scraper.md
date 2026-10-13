# Idea Refine: Novalpie Dual-Mode Authenticated Scraper (720h & 60d Account Access)

## Problem Statement
**How Might We** menyediakan pilihan antara mode "Tanpa Akun" (Guest) dan "Pakai Akun" (Authenticated) di Translator_Web sehingga perayap Playwright dapat mengakses buku dengan batasan usia akun (720 jam / 30 hari) serta mengekstrak media ilustrasi (60 hari) lalu menyimpannya ke cache lokal secara otomatis untuk bulk crawl ratusan bab?

---

## Hasil Investigasi Teknis & Uji "Bypass Artifisial"

Kami telah melakukan pengujian mendalam terhadap bundel Nuxt 3 dan arsitektur proteksi `novalpie.cc`:

1. **Mekanisme Otentikasi (`BDyTnbGc.js` & `Yn.get()`):**
   - Otentikasi Novalpie menggunakan Bearer Token (`auth_token`).
   - Token ini disimpan di `document.cookie` (`auth_token=...`) atau `localStorage.getItem("auth_token")`.
   - Setiap permintaan konten ke `/api/reader/session-key` dan `/api/chapters/{id}/content` menyertakan header `Authorization: Bearer <auth_token>` serta tanda tangan kriptografi `x-client-signature`.

2. **Enkripsi Konten Bab (`BOp3s4R4.js`):**
   - Konten bab dikirim dari server dalam bentuk terenkripsi AES-GCM (`content`, `iv`, `tag`, `encrypted: true`).
   - Kunci sesi didekripsi di dalam browser oleh modul Webpack/Vite `BOp3s4R4.js` sebelum dirender ke elemen `<article class="reader-content">`.

3. **Temuan Uji Bypass Artifisial (Tanpa Akun Asli):**
   - **Kesimpulan: Bypass artifisial di sisi klien tidak memungkinkan.**
   - **Penyebab**: Validasi batas umur akun (720 jam dan 60 hari) dievaluasi langsung oleh backend server (Laravel) dengan membaca kolom `created_at` milik akun di database server.
   - Token `auth_token` ditandatangani secara kriptografis (HMAC/JWT) dengan secret server; pemalsuan token di sisi klien ditolak dengan `401 Unauthorized` / `Invalid Signature`.
   - **Solusi Sah & Pasti Berhasil**: Menyediakan sesi akun asli pengguna yang sudah memenuhi syarat usia akun melalui injeksi `auth_token` ke konteks Playwright.

---

## Recommended Direction: Dual-Mode Toggle & Injeksi Sesi

### 1. Pilihan Mode di Pengaturan & UI
- Pengguna diberikan tombol toggle jelas:
  - **Mode Tanpa Akun (Guest)**: Berjalan default tanpa cookie (ringan, untuk novel publik).
  - **Mode Pakai Akun (Authenticated)**: Mengaktifkan injeksi token sesi Novalpie untuk novel 720h dan gambar 60d.
- Input token/cookie `novalpie_auth_token` di tab Settings dan di pop-up `BulkFetchModal.tsx`.

### 2. Injeksi Otomatis ke Playwright & HTTPX
- Saat mode akun aktif:
  - Playwright: Menyuntikkan cookie `auth_token` via `context.add_cookies(...)` dan `localStorage.setItem("auth_token", token)`.
  - HTTPX: Menyertakan header `Cookie: auth_token=...` dan `Authorization: Bearer ...` pada pengambilan metadata & TOC.

### 3. Auto-Caching Media Ilustrasi
- Gambar dari `images.novelpia.com` yang dirender di DOM bab langsung diekstraksi ke sintaks Markdown `![插图](url)`.
- Diintegrasikan dengan sistem proksi & cacher lokal (ADR-103 & ADR-105) agar file gambar biner langsung diunduh ke folder cache lokal proyek, siap dibaca offline dan diintegrasikan ke ekspor EPUB.

---

## Key Assumptions to Validate
- [x] Token otentikasi menggunakan nama `auth_token` baik di cookie maupun di localStorage. *(Tervalidasi via reverse engineering `BDyTnbGc.js`)*
- [x] CDN gambar `images.novelpia.com` dapat diunduh biner aslinya tanpa proteksi referer ketat setelah URL ilustrasi terbuka. *(Tervalidasi 200 OK)*
- [ ] Token sesi pengguna bertahan stabil selama sesi bulk crawl ratusan bab tanpa sering kadaluarsa.

---

## MVP Scope
1. **Database Migration (`backend/database.py`)**:
   - Kolom `novalpie_auth_enabled: Mapped[int] = mapped_column(default=0)` (0 = guest, 1 = auth).
   - Kolom `novalpie_cookie: Mapped[Optional[str]] = mapped_column(Text, default="")`.
2. **Backend Engine (`backend/services/scrapers/novalpie.py`)**:
   - Fungsi `_inject_auth_session(context, page)` untuk memasang cookie dan localStorage sebelum navigasi `page.goto()`.
   - Integrasi token ke `httpx.AsyncClient` jika `novalpie_auth_enabled` bernilai 1.
3. **Frontend Settings UI (`src/pages/SettingsPage.tsx` & `src/components/BulkFetchModal.tsx`)**:
   - Toggle switch "Gunakan Akun Novalpie".
   - Input textarea/password untuk menempelkan `auth_token` atau string cookie.
4. **Unit Tests (`backend/tests/test_services/test_novalpie_scraper.py`)**:
   - Pengujian pemanggilan dengan sesi dan tanpa sesi (mocking token).

---

## Not Doing (Out of Scope)
- Mengembangkan brute-force token atau eksploitasi server pihak ketiga.
- Menyimpan password login mentah pengguna (hanya menyimpan token sesi sementara).

---

## Open Questions
- Apakah token yang Anda miliki didapat dari cookie peramban dengan nama `auth_token`? (Bisa dicek di Developer Tools -> Application -> Cookies -> `https://novalpie.cc`).
