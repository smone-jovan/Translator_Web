# ADR-123: Settings ↔ Lorebook Synchronization & Glossary Studio Overhaul

## Status
Accepted (diimplementasikan pada commit `ccdb5c0`, Issue #24; ADR ditulis retroaktif pada audit 2026-10-16)

## Date
2026-10-15

## Context
Audit lanjutan #20, #21, dan #23 menemukan 8 bug sinkronisasi antara Settings, Lorebook, dan halaman Glossary (`ContextLibraryPage.tsx`):

1. **BUG-01 (Critical)**: default `max_context_terms` tidak konsisten (ORM `150`, migrasi/fallback `50`, pemilih UI tanpa opsi `150`), dan pengarsipan hanya berjalan satu arah. Menaikkan kuota tidak pernah memulihkan istilah arsip.
2. **BUG-02 (Critical)**: `GET /api/threads/{id}/lorebook` selalu memfilter istilah arsip, sehingga istilah yang diarsipkan otomatis hilang total dari UI; `LorebookOut` juga tidak menyertakan `auto_extracted`/`usage_count`.
3. **BUG-03 (Critical)**: `get_thread()` tidak mengembalikan `style_guide`, sehingga kotak Style Guide di reader selalu kosong walau sudah tersimpan.
4. **BUG-04 (High)**: preset genre (`xianxia`, `wuxia`, `xuanhuan`, `imperial`) hanya berbahasa Inggris dan selalu mengunci semua entri.
5. **BUG-05 (High)**: halaman Glossary tidak tahu `translation_mode`. Di mode Fast hanya 10 istilah per bab yang disuntikkan, tanpa penjelasan di UI.
6. **BUG-06 (High)**: `SettingsPage.tsx` tidak menyimpan `display_mode` ke server; mount awal menimpa `target_language`; `prefetchMode` tidak tersinkron.
7. **BUG-07 (High)**: `PUT …/translation` meng-hardcode `always_hide_thoughts=True` dan melewati glossary lock; `reapply-glossary` tidak menyentuh judul bab.
8. **BUG-08 (High)**: CRUD `CharacterRelationship` tidak lengkap dan beberapa tombol di UI hanya mockup.

---

## Decisions

### 1. Satu Default & Rebalancing Dua Arah
- Default `max_context_terms = 150` di ORM, Settings API, dan UI (opsi `150` ditambahkan ke pemilih). Commit `ccdb5c0` belum menuntaskan semuanya: migrasi kolom masih `DEFAULT 50` dan `ContextEngine` masih jatuh ke `50` (`context_engine.py:277`, `:444`). Keduanya disamakan ke 150 pada perbaikan council 2026-10-17 (tes: `backend/tests/test_services/test_context_limit_fallback.py`).
- `routers/lorebook.enforce_context_limit(thread_id, db)` bekerja dua arah. Di atas kuota: arsipkan. Di bawah kuota: pulihkan entri arsip berprioritas tertinggi (`is_locked`, `usage_count`, waktu terakhir disentuh). Catatan entri tidak dihapus.
- `POST /api/settings` menjalankan rebalancing untuk semua thread setiap kali request membawa field `max_context_terms` (`settings.py:195`), bukan hanya saat nilainya berubah. Hasilnya sama karena operasinya idempoten; biayanya dibahas di Consequences.

### 2. API Lorebook yang Lengkap (`backend/routers/lorebook.py`)
- `GET /api/threads/{id}/lorebook?include_archived=true`, `GET /api/threads/{id}/lorebook/stats`, arsip/pulihkan per entri, dan `POST /api/threads/{id}/lorebook/bulk` untuk menerima banyak saran AI dalam satu request.
- `LorebookOut` menyertakan `auto_extracted`, `usage_count`, `last_used_at`, dan `created_at`. **Catatan:** model `LorebookEntry` tidak punya kolom `auto_extracted`, sehingga field ini selalu `false` (lihat Residual Risks).

### 3. Konteks Thread Utuh
- `get_thread()` (`GET /api/threads/{id}`) mengembalikan `style_guide` dan `thread_context`.
- Tab Style Guide menampilkan tiga lapis konteks secara terpisah: Novel Style Guide, Novel Lore Summary, dan Global Translation Instructions.

### 4. Preset Dwibahasa
- `genre_presets.py` menyediakan kamus Indonesia & Inggris yang mengikuti `GlobalSetting.target_language`, dengan opsi `lock_entries`. Pemanggilan tanpa argumen bahasa tetap kompatibel mundur.

### 5. Glossary Studio Sadar Mode
- `ContextLibraryPage.tsx` membaca `/api/settings` (`translation_mode`, `max_context_terms`, `target_language`), menampilkan meter kapasitas, dan banner peringatan mode Fast dengan tombol satu klik untuk beralih ke Quality.

### 6. Konsistensi Settings & Endpoint Teks
- `display_mode` disimpan ke server; `target_language` tidak lagi tertimpa saat mount (penyimpanannya lewat `useEffect` yang dijaga `isSettingsLoadedRef`, `SettingsPage.tsx`); `prefetchMode` memakai `syncEngineLoadMode` (ADR-102).
- `update_chapter_translation` membaca `always_hide_thoughts` dari `GlobalSetting`, menjalankan `enforce_glossary_locking()`, dan menandai status `done`. Kedua endpoint `reapply-glossary` menerapkan lock ke isi **dan** judul bab.

### 7. Relasi Karakter Lengkap
- `backend/routers/relationships.py`: `POST`, `PUT /api/relationships/{id}`, dan `DELETE`. UI `RelationshipGraph.tsx` mendapat mode graf + tabel + form. Kartu mockup diganti template aturan yang bisa disisipkan.

---

## Consequences

### Positive
- Pengaturan kuota glosarium konsisten di seluruh aplikasi dan dapat dibalik (menaikkan kuota memulihkan istilah).
- Istilah arsip tetap terlihat dan bisa dipulihkan; menerima banyak saran AI cukup satu request.
- Pengguna mengerti mengapa mode Fast memakai lebih sedikit istilah.

### Negative / Trade-offs
- Rebalancing semua thread saat kuota berubah bersifat O(jumlah entri) dan berjalan sinkron di request Settings; perpustakaan yang sangat besar dapat membuat request ini lambat.
- Logika batas kuota terduplikasi dengan `ContextEngine.enforce_context_limit` (lihat ADR-122, tindak lanjut).
- Diverifikasi oleh `backend/tests/test_routers/test_settings_and_glossary_redesign.py`.

### Residual Risks (terverifikasi council 2026-10-17, belum diperbaiki)
- **`auto_extracted` fantom (bagian BUG-02 belum tuntas)**: tidak ada kolom `auto_extracted` di `LorebookEntry` (`database.py`), sehingga `LorebookOut.auto_extracted` selalu `false`, `stats.auto_extracted_count` selalu `0`, dan filter/badge "auto" di Glossary Studio (`ContextLibraryPage.tsx`) tidak pernah cocok. Perbaikannya butuh kolom baru + migrasi di `app.db` dan `ghost.db`, lalu mengisinya di `auto_save_glossary()`; sementara itu filter "auto" sebaiknya disembunyikan.
