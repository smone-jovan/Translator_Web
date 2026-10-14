# Ide & Telaah Arsitektur: Isolasi Cache Ghost Mode & Orkestrasi Sentral GlobalSetting

Dokumen ini mendokumentasikan hasil analisis penelusuran *Knowledge Graph* (Graphify) dan audit forensik terhadap sistem isolasi basis data ganda (*Dual-Database Architecture*), manajemen antrean SSE, dan peranan sentral model `GlobalSetting`.

---

## 1. Masalah Utama yang Ditemukan (Root Causes)

### A. Kebocoran Cache Frontend Ghost Mode (`main` ↔ `ghost`)
- **Gejala:** Saat berpindah workspace menggunakan PIN di modal (`Sidebar.tsx` / `SettingsPage.tsx`), data novel rahasia dari workspace `ghost` sempat berkedip tampil di workspace `main` pasca `window.location.reload()`.
- **Akar Masalah:**
  1. `sessionStorage` tidak otomatis dibersihkan saat browser melakukan reload halaman.
  2. Kunci penyimpanan (`APP_SESSION_KEY`, `LIBRARY_CACHE_KEY`, `readomni_reader_session_${id}`, dan `bookmarksCacheStore`) bersifat statis dan tidak menyertakan identitas workspace aktif (`getActiveWorkspace()`).
- **Solusi:**
  - Pelingkupan dinamis seluruh kunci penyimpanan lokal/sesi dengan awalan/akhiran workspace: `readomni_library_cache_v1_${getActiveWorkspace()}`, dsb.
  - Pemanggilan eksplisit `sessionStorage.clear()` sesaat sebelum `window.location.reload()`.

### B. Kebocoran Tenancy pada Antrean SSE `translation_queues`
- **Gejala:** Jika dua chapter memiliki integer ID yang sama pada workspace berbeda (`app.db` vs `ghost.db`), streaming SSE di satu workspace dapat mendengarkan atau menerima potongan terjemahan dari workspace lain.
- **Akar Masalah:** `translation_queues` masih mendaftarkan listener ke alias integer mentah `translation_queues[chapter_id]` selain `(ws, chapter_id)`.
- **Solusi:** Hapus seluruh registrasi integer mentah. Jadikan `translation_queues` murni menggunakan compound key `(ws, chapter_id)`.

### C. Desinkronisasi Parameter Workspace pada Scraper Adapters
- **Gejala:** Pengaturan konkurensi scraping dan autentikasi sesi cookie Novalpie membaca workspace global alih-alih workspace request pemanggil.
- **Akar Masalah:** Instansiasi `NovalpieAdapter()` di router `scrape.py`, `toc.py`, dan `threads.py` tidak meneruskan parameter `workspace=ws`.
- **Solusi:** Teruskan parameter `workspace` dari dependensi database `get_db_workspace(db)` ke `NovalpieAdapter(workspace=ws)`.

---

## 2. Peran Sentral GlobalSetting sebagai "God Node"

Berdasarkan analisis graf pengetahuan (betweenness centrality: 0.082 dengan 104 edges), entitas `GlobalSetting` adalah jantung orkestrasi yang mengikat empat pilar aplikasi:

```text
                        ┌────────────────────────┐
                        │     GlobalSetting      │
                        │  (backend/database.py) │
                        └───────────┬────────────┘
         ┌───────────────────┬──────┴─────────────┬───────────────────┐
         │                   │                    │                   │
         ▼                   ▼                    ▼                   ▼
┌─────────────────┐ ┌──────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│Batch Translation│ │ Novalpie Scraper │ │ Settings State  │ │   Ghost Mode    │
│ & Worker Queue  │ │ & Stealth Engine │ │  & Key Manager  │ │& Workspace Iso  │
└─────────────────┘ └──────────────────┘ └─────────────────┘ └─────────────────┘
```

1. **Batch Translation:** Memasok `translation_mode` (Quality vs Fast), `prefetch_mode` (Soft vs Hard), serta daftar kunci API multi-provider untuk rotasi RPM bebas limit 429.
2. **Novalpie Scraper:** Mengatur batas konkurensi browser headless (`scraper_concurrency` 1–5), aktivasi mode otentikasi (`novalpie_auth_enabled`), dan token sesi (`novalpie_cookie`).
3. **Settings State & Secrets:** Menjadi sumber kebenaran tunggal untuk preferensi antarmuka pengguna, dengan pemisahan kredensial sensitif ke `.env` dan perlindungan nilai terselubung (*masked secret integrity*).
4. **Ghost Mode Isolation:** Menyimpan `ghost_pin` unik di masing-masing basis data (`app.db` dan `ghost.db`) sehingga konfigurasi, riwayat baca, dan token kunci kedua ruang kerja terpisah secara fisik.

---

## 3. Rekomendasi Pemeliharaan Masa Depan

1. **Prinsip Immutability Workspace:** Setiap modul backend baru yang mengakses database atau memori in-memory WAJIB selalu mengikat kuncinya ke tuple `(workspace, id)`.
2. **Hindari State Global Proses:** Jangan pernah mengandalkan variabel modul global untuk menyimpan identitas klien atau sesi request aktif.
3. **Pembersihan Cache Berlapis:** Pastikan setiap penambahan fitur penyimpanan sisi klien di frontend React selalu menyertakan identitas workspace aktif melalui `getActiveWorkspace()`.
