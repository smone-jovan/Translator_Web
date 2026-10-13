# ADR-110: Non-Human Entity Sanitization, Visual Gender Indicators, and Anti-Hallucination Controls

## Status
Accepted (2026-10-03)

## Context
Menyusul implementasi ADR-109 (penambahan skema DB `LorebookEntry.gender`, parser token ekstraksi, dan injeksi mandat pronoun ke prompt terjemahan), pengujian pada utas novel nyata (Thread 112: *Do Not Install Mods Randomly*) mengungkap tiga masalah mendasar:

1. **Polusi Gender pada Entitas Non-Manusia**:
   Nama kota (Beijing, Chang'an), sekte (Heavenly Cloud Sect), artefak, pil, jurus, formasi, atau benda genderless lainnya (misalnya "B Cup", "Status Window") berisiko diberi atribut gender jika output LLM tidak tertib, yang pada akhirnya memicu blok aturan pronoun salah (`he/she`) untuk entitas non-manusia.
2. **Halusinasi Jiplak Contoh Prompt (*Example Copycat Trap*)**:
   Contoh format *few-shot* pada template ekstraksi (`- 宁凡 → Ning Fan (MALE — Protagonist, a reincarnated cultivator who was formerly a mortal scholar)`) dijiplak mentah-mentah oleh model LLM tertentu ke karakter lain yang sama sekali berbeda, sehingga tokoh protagonis wanita (Ties) dan teman perempuannya (Bluebell) tertulis dengan catatan *"MALE — Protagonist, a reincarnated cultivator who was formerly a mortal scholar"* dan berstatus MALE secara keliru.
3. **Ketiadaan Visibilitas & Interaktivitas UI**:
   - Schema Pydantic `LorebookOut`, `LorebookCreate`, dan `ExtractedTerm` tidak mengekspos field `gender`, sehingga frontend sama sekali tidak menerima informasi gender dari basis data.
   - Tidak ada indikator visual di Context Library untuk membedakan tokoh pria, wanita, atau istilah netral.
   - Pengguna tidak memiliki mekanisme koreksi cepat jika terjadi salah deteksi gender selain melalui query SQL langsung.

## Decision

1. **Klasifikasi Heuristik Entitas Non-Manusia (`ContextEngine.is_non_human_term`)**:
   - Dibuat detektor pola di `backend/services/context_engine.py` untuk mengidentifikasi lokasi/wilayah (kota, benua, gunung, danau), sekte/organisasi (klan, perkumpulan), dan benda/jurus/item (pedang, pil, formasi, teknik).
   - Memeriksa sufiks karakter Hanzi (城, 镇, 宗, 门, 剑, 丹, 诀, 派, 界, dsb.), kata kunci terjemahan bahasa Inggris/Indonesia, dan deskripsi notes.
   - **Guardrail Tiga Titik**:
     - *Parsing Ekstraksi*: Token gender dibatalkan jika entitas tergolong non-manusia.
     - *Penyimpanan API (`_resolve_gender`)*: Request penyimpanan istilah menolak gender pada entitas non-manusia.
     - *Injeksi Context Prompt*: Entitas non-manusia yang sudah terlanjur ber-gender di database disaring agar tidak pernah menyuntikkan token gender maupun memicu blok mandat pronoun.

2. **Aturan Anti-Jiplak Contoh pada Prompt Ekstraksi (`prompt_templates.py`)**:
   - Ditambahkan Aturan 6 (*DO NOT COPY EXAMPLES*): melarang keras LLM menyalin deskripsi dari contoh few-shot (*reincarnated cultivator*, *mortal scholar*) ke entitas teks yang sedang dianalisis.

3. **Eksposur Schema API Lengkap (`backend/routers/lorebook.py`, `backend/routers/context.py`)**:
   - Field `gender: str | None` diekspos pada `LorebookOut`, `LorebookCreate`, dan `ExtractedTerm`.
   - Pembaruan endpoint `POST` & `PUT` lorebook mendukung perubahan atribut gender secara langsung.

4. **Visualisasi & Kontrol Interaktif di UI (`src/pages/ContextLibraryPage.tsx`)**:
   - **Emblem Avatar Unik**:
     - Tokoh Laki-laki: Border avatar biru + emblem badge `♂` di sudut avatar + pill `♂ Male` pada judul.
     - Tokoh Perempuan: Border avatar pink + emblem badge `♀` di sudut avatar + pill `♀ Female` pada judul.
     - Entitas Netral/Genderless: Avatar polos tanpa badge gender.
   - **Aksi Cepat Siklus 1-Klik**:
     - Klik avatar atau tombol badge pada kartu istilah memicu siklus instan: `♂ Male` ⇄ `♀ Female` ⇄ `Netral/Benda` melalui API `PUT /api/lorebook/{id}` tanpa perlu membuka modal formulir.
   - **Filter Segmentasi Gender**:
     - Tombol tab filter di atas grid istilah: `All`, `♂ Male`, `♀ Female`, dan `Benda/Netral` lengkap dengan hitungan jumlah entri masing-masing.
   - **Formulir Tambah / Edit Istilah**:
     - Dropdown pemilihan gender tokoh manusia dilengkapi peringatan agar tidak digunakan pada nama tempat, sekte, atau benda.

5. **Remediasi Data Korup**:
   - Database dibersihkan dari entri contoh halusinasi dan entri karakter wanita yang tertukar gender akibat halusinasi prompt sebelumnya dikembalikan ke `FEMALE`.

## Alternatives Considered

1. **Hanya Mengandalkan Deteksi Nama AI**:
   - *Ditolak*: Model AI sering berhalusinasi menyamakan nama feminin/maskulin lintas bahasa (terutama nama Korea/China/Jepang) dan rentan meniru pola contoh prompt.
2. **Modal Konfirmasi Tambahan untuk Setiap Ganti Gender**:
   - *Ditolak*: Menghambat efisiensi pengguna saat mengoreksi daftar glosarium yang berisi puluhan karakter; siklus 1-klik langsung dengan toast notification jauh lebih cepat dan ergonomis.

## Consequences

- **Positive**:
  - Pengguna dapat langsung melihat gender karakter secara visual dari kartu istilah tanpa membaca teks catatan.
  - Entitas netral (kota, sekte, jurus, artefak) dijamin 100% bebas dari atribut gender dan tidak memicu kesalahan kata ganti (*he/she*) pada terjemahan.
  - Koreksi gender dapat dilakukan dalam 1 kali klik langsung di kartu.
  - Filter glosarium memudahkan peninjauan karakter berdasarkan jenis kelamin.
- **Negative / Trade-offs**:
  - Heuristik regex non-manusia memerlukan pemeliharaan jika terdapat kosa kata fiksi yang sangat unik, namun fallback manual pengguna selalu tersedia untuk mengoreksinya kapan saja.

## Related
- Fondasi & skema awal: ADR-109 (`docs/decisions/ADR-109-Gender-Aware-Glossary-Extraction-and-Pronoun-Consistency.md`)
- Proposal awal: `docs/ideas/gender-aware-glossary.md`
- Hard-locking glosarium: ADR-106, ADR-107, ADR-108
