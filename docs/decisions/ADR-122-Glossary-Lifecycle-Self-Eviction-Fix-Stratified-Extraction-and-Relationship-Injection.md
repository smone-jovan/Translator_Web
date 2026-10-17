# ADR-122: Glossary Lifecycle — Self-Eviction Fix, Stratified Extraction & Relationship Injection

## Status
Accepted (diimplementasikan pada commit `ccdb5c0`, Issue #23; Issue #22 ditutup sebagai duplikat #23; ADR ditulis retroaktif pada audit 2026-10-16)

## Date
2026-10-15

## Context
Audit lanjutan #20/#21 pada alur ekstraksi glosarium, auto-extract sebelum translasi, seleksi lorebook, dan prompt translasi menemukan 7 akar masalah:

1. **Self-Eviction Paradox**: istilah baru (auto-extract maupun manual) dibuat dengan `usage_count = 0`, lalu `enforce_context_limit()` mengurutkan `(usage_count ASC, timestamp ASC, id ASC)`. Begitu thread mencapai `max_context_terms`, istilah yang **baru saja** ditambahkan langsung diarsipkan lagi, dan `entry.notes` ikut dihapus. Akibatnya glosarium membeku setelah kuota pertama terisi.
2. **Auto-extract "buta"**: `extract_glossary_pass()` hanya membaca awal bab sebanyak `extract_sample_size` karakter (default 1.000), sehingga sebagian besar isi bab tidak terbaca, dan tidak diberi tahu glosarium yang sudah ada, sehingga istilah diekstrak ulang dan kuota terbuang.
3. **Parsing `### TRANSLATOR NOTES:` rapuh**: header bisa tersangkut di dalam blok `<think>` atau dialog cerita; `strip_translator_notes()` memotong paragraf yang diawali "Notes…"; istilah dari bab berjalan belum ikut terkunci karena `auto_save_glossary()` berjalan **setelah** `enforce_glossary_locking()`.
4. **Gender tergeser** pada regex fallback `extract_thread_context`: `"gender": null` (tanpa tanda kutip) dilewati sehingga indeks gender bergeser ke karakter lain.
5. **Catatan translasi tanpa prefix gender**: instruksi in-translation tidak meminta `MALE —`/`FEMALE —`, sehingga karakter baru tersimpan dengan `gender = None`.
6. **Relasi karakter tidak dipakai**: tabel `CharacterRelationship` diekstrak tetapi tidak pernah disuntikkan ke prompt; `_term_matches_text()` salah memecah entri `罗毅 (Luo Yi / Luoyi)`.
7. **Cloud provider tertimpa URL lokal**: `ContextLibraryPage.tsx` selalu mengirim `lm_url = http://localhost:1234`, dan `resolve_active_base_url()` mendahulukan URL tersebut di atas `gs.llm_provider`. Menerima 30 saran AI juga memicu 30 request berurutan.

---

## Decisions

### 1. Siklus Hidup Istilah Tanpa Self-Eviction (`backend/services/context_engine.py`, `backend/routers/lorebook.py`)
- Istilah baru atau yang dipulihkan dibuat dengan `usage_count = 1` dan `last_used_at = now()`. Ini berlaku di semua jalur pembuatan: auto-save, create tunggal & `/lorebook/bulk`, serta — sejak perbaikan council 2026-10-17 — **bulk-action `import`** (`lorebook.py`) dan **preset genre tanpa kunci** (`genre_presets.apply_preset`, `lock_entries=False`), yang sebelumnya masih memakai default ORM `0` sehingga paradoksnya tetap terjadi di sana. Tes: `backend/tests/test_routers/test_glossary_new_terms_not_evicted.py`.
- `ContextEngine.enforce_context_limit(db, thread_id, protected_ids=…)`: istilah yang baru disimpan/dipulihkan pada operasi yang sama dilindungi dari eviction; istilah `is_locked` tidak pernah dievict.
- Pengarsipan tidak lagi menghapus `entry.notes`. `reactivate_referenced_archived_terms()` memakai `_term_matches_text()` dan menaikkan `usage_count`.

### 2. Ekstraksi Bersampel & Sadar Glosarium
- `extract_glossary_pass()` (auto-extract sebelum translasi) membaca hingga `max(sample_size * 6, 6000)` karakter per bab dengan sampel Head 45% + Middle 25% + Tail 30% (`context_engine.py:872-874`).
- Ekstraksi manual dari Context Library memakai `_sample_chapter_text()` (`backend/routers/context.py`) dengan *stratified sampling* Head 40% + Middle 30% + Tail 30%, dibatasi `extract_sample_size`.
- Prompt ekstraksi menyertakan blok `[EXISTING GLOSSARY — DO NOT RE-EXTRACT…]`; blok `<think>` dibersihkan sebelum parsing.

### 3. Parsing Catatan Translator yang Kokoh
- `auto_save_glossary()` memanggil `strip_thinking_blocks()` lebih dulu, menjangkarkan header ke baris mandiri, dan mengambil kecocokan terakhir.
- `normalize_original_term()` menormalkan istilah sumber; `pinyin_pattern` mendukung 1–3 suku kata dan tanda hubung.
- `auto_save_glossary()` dijalankan **sebelum** `enforce_glossary_locking()`, sehingga istilah baru langsung ikut dikunci di bab yang sama.

### 4. Gender & Relasi dalam Prompt
- Fallback regex `extract_thread_context` mem-parsing per objek `{…}`, sehingga indeks gender tidak bisa bergeser; awal array dicari dengan `\[\s*\{`.
- `build_translator_notes_instruction()` mewajibkan prefix `MALE —`/`FEMALE —` untuk karakter manusia, menulis catatan dalam bahasa target, dan mendukung `source_lang` dinamis.
- Mode Quality menyuntikkan `[CHARACTER RELATIONSHIPS & HIERARCHY]` dari `CharacterRelationship`. Entri yang cocok diurutkan `(is_locked, panjang istilah, usage_count, id)`; entri arsip menjadi fallback di `enforce_glossary_locking()`.

### 5. Resolusi Provider yang Benar
- `resolve_active_base_url(gs, requested_url)` melindungi provider cloud dari URL lokal: URL `localhost` yang diminta klien tidak boleh menimpa provider `gemini`/`openai`/`openrouter`.
- Penerimaan saran AI massal memakai satu endpoint bulk (lihat ADR-123).

---

## Consequences

### Positive
- Glosarium tetap tumbuh dan istilah lama yang muncul lagi kembali aktif dengan catatannya utuh.
- Ekstraksi melihat seluruh bab, tidak hanya pembukaannya, dan tidak membuang kuota untuk istilah yang sudah ada.
- Konsistensi panggilan antar-karakter dan gender naik karena relasi dan gender masuk ke prompt.

### Negative / Trade-offs
- Prompt mode Quality bertambah panjang karena blok relasi; mode Fast sengaja tidak menyertakannya (lihat ADR-123, banner mode Fast).
- Logika batas kuota kini ada di dua tempat: `ContextEngine.enforce_context_limit` (satu arah, dengan `protected_ids`) dan `routers/lorebook.enforce_context_limit` (dua arah, juga menerima `protected_ids`; dipakai semua route lorebook create/update/delete/bulk/preset dan Settings). Fallback batasnya disamakan ke 150 pada perbaikan council 2026-10-17 (sebelumnya `ContextEngine` jatuh ke 50). **Tindak lanjut yang disarankan:** satukan ke satu fungsi agar aturan prioritasnya tidak menyimpang.
- `last_used_at` memakai `onupdate=now()`, sehingga edit atau pengarsipan apa pun ikut menyegarkannya; urutan eviction lebih tepat dibaca sebagai "terakhir disentuh", bukan "terakhir dipakai di prompt".

### Residual Risk (terverifikasi council 2026-10-17, di luar lingkup perbaikan)
- ~~**Kebocoran API key ke URL pilihan klien**~~ — **ditutup di ADR-126**: allowlist hostname per provider (hasil parse, bukan substring) di `resolve_active_base_url`, `AIProviderFactory`, dan `translate.get_lm_url`. Cakupan aslinya lebih luas dari catatan ini: `/translate` meneruskan `lm_url` mentah, dan factory berganti provider berdasarkan substring URL. Tersisa: `PUT /settings` masih bisa mengubah `gs.openai_url` (model ancaman tanpa autentikasi).
