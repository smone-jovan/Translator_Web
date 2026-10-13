# Glossary Hard-Locking & Deterministic Aliasing Engine

## Problem Statement
Bagaimana cara menjamin kepatuhan istilah glosarium hingga 100% (misalnya mengunci karakter Mandarin `罗毅` atau pinyin `Luo Yi` menjadi `Rahmat`) tanpa bergantung pada kepatuhan prompt model AI (Gemini) dan tanpa merusak pemahaman gender atau keluwesan tata bahasa cerita?

## Recommended Direction
Menerapkan arsitektur **Hybrid 3-Layer (Semantic Prompt + Auto-Pinyin Aliasing + Deterministic Post-Processing Safety Net)**:

1. **Semantic Prompt Hint**: Prompt tetap menyertakan Hanzi asli dan terjemahan target agar Gemini memahami konteks karakter, gender (pria/wanita), dan relasi cerita tanpa kebingungan semantik.
2. **Automatic Pinyin Aliasing**: Backend secara otomatis mengekstrak pinyin dari karakter Hanzi (misal `罗毅` → `Luo Yi` dan `Luoyi`) saat istilah disimpan di Lorebook atau saat context prompt dibangun.
3. **Deterministic Post-Processing Safety Net**: Di fungsi sentral `ContextEngine.clean_final_translation()`, backend melakukan pemindaian regex berbatas kata (*whole-word boundary check*). Jika Gemini tetap mengeluarkan nama lama (baik dalam Hanzi maupun Pinyin), backend langsung menimpanya secara deterministik dengan istilah target (`Rahmat`).
4. **Retroactive 1-Click Sync**: Menambahkan tombol/endpoint cepat untuk menerapkan ulang glosarium yang baru diubah pada bab yang sudah ada tanpa memanggil API LLM (0 biaya token, eksekusi instan dalam hitungan milidetik).

## Key Assumptions to Validate
- [ ] Regex boundary matching `\bLuo\s+Yi\b` aman dan tidak menabrak kata umum bahasa Indonesia (terutama untuk pinyin pendek 2-3 huruf).
- [ ] Auto-generasi pinyin dari Hanzi akurat untuk nama karakter Chinese Xianxia/Wuxia tanpa dependensi berat.
- [ ] Pengguna merasa puas melihat nama terkunci 100% tanpa ada lagi nama Mandarin/Pinyin yang "bocor" di bab terjemahan.

## MVP Scope
- **[Backend]** Helper utilitas untuk mengekstrak Pinyin/Alias dari entri Hanzi (misal `罗毅` → `Luo Yi`, `Luoyi`).
- **[Backend]** Modifikasi `ContextEngine.clean_final_translation()` untuk menerima daftar active glossary & aliases dari thread, lalu menjalankan *whole-word boundary substitution* pasca-terjemahan.
- **[Backend]** Endpoint `POST /api/threads/{thread_id}/chapters/{chapter_id}/reapply-glossary` untuk me-resync bab yang sudah tersimpan saat glossary diubah tanpa memanggil AI.
- **[Frontend]** Indikator informatif "Aliases Terkunci" di tabel/kartu `ContextLibraryPage.tsx`.
- **[Frontend]** Tombol aksi cepat *"Terapkan Ulang Glosarium"* di menu pembaca (`ChapterReader.tsx`) jika pengguna baru saja mengedit istilah glosarium.

## Not Doing (and Why)
- **Pre-Translation Token Masking (`❖NAME_x❖`)** — Ditolak karena merusak pemahaman gender karakter oleh Gemini, mengacaukan kata ganti ("dia"), dan merusak keluwesan hukum D-M tata bahasa Indonesia.
- **Full NLP Grammar Lemmatization Engine** — Ditolak untuk MVP demi kesederhanaan dan performa; regex word-boundary sudah lebih dari cukup untuk 98% kasus nama tokoh dan ranah jurus.
- **Automatic Global Re-translate on Glossary Change** — Ditolak; tidak akan memanggil ulang API Gemini secara massal demi mencegah lonjakan tagihan token atau *rate-limit* API pengguna. Re-sync hanya dilakukan di layer teks tersimpan secara deterministik.

## Open Questions
- Apakah sistem perlu menyimpan daftar Pinyin di kolom baru tabel database `LorebookEntry` (misal kolom `aliases`), atau cukup di-generate on-the-fly saat membersihkan terjemahan?
- Apakah pencarian Pinyin harus *case-insensitive* (`luo yi`, `Luo Yi`, `LUO YI`)? (Rekomendasi: Ya, case-insensitive dengan menjaga kapitalisasi kata target).
