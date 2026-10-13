# Gender-Aware Glossary

## Problem Statement
How might we membuat sistem glossary tahu gender setiap karakter, supaya AI
tidak salah menangkap karakter ber nama feminim tapi cowo (dan sebaliknya)
saat menerjemah chapter?

## Recommended Direction
V1 — Gender tag wajib di extraction pass + kolom `gender` di lorebook_entries.
Extraction prompt mewajibkan penanda gender untuk setiap person entry, parser
auto_save_glossary menyimpannya ke kolom baru, dan context engine meng-inject
gender ke dalam blok STRICT GLOSSARY sebagai instruksi pronoun eksplisit
("MALE → always he/him"). Extraction hanya menandai gender bila teks asli
memberi bukti (pronoun 他/她); selain itu di-skip → `unknown`.

## Key Assumptions to Validate
- [ ] Sample extraction (25 chapter pertama) cukup berisi bukti 他/她 untuk
      inferensi gender yang benar — test: jalankan extraction pada 3 novel,
      bandingkan hasil dengan pembacaan manual
- [ ] Gender injection mengurangi error he/she — test: translate chapter yang
      pernah salah, bandingkan sebelum/sesudah
- [ ] Gender di blok glossary tidak mengubah perilaku glossary lock / export
      / garbage filter — test: pytest existing suite tetap hijau

## Implementation Steps

### Step 1 — Tambah kolom `gender` + auto-migration
Tambah kolom `gender: Mapped[Optional[str]]` di `LorebookEntry`
(backend/database.py) dan conditional ALTER TABLE di `init_db()` mengikuti
pola `fidelity_warning` yang sudah terbukti.

### Step 2 — Rule gender di extraction prompt
Ubah `build_glossary_extraction_prompt` (backend/services/prompt_templates.py):
setiap PERSON entry wajib menyertakan gender (MALE/FEMALE) berbasis bukti teks
asli (他/她); bila tidak jelas → omit; non-person tidak boleh diberi gender.

### Step 3 — Parse gender di auto_save_glossary + update existing NULL
Update `ContextEngine.auto_save_glossary` (backend/services/context_engine.py):
parse tag gender dari parenthetical, simpan ke `LorebookEntry.gender`, dan
update entry existing bila `gender` masih NULL (path `if not exists` sekarang
melewati update total).

### Step 4 — Inject gender ke prompt terjemahan
Inject gender ke baris glossary di `build_context_prompt`
(context_engine.py) dan tambahkan frasa instruksi pronoun
(MALE → he/him, FEMALE → she/her) pada prompt terjemahan Quality mode
(prompt_templates.py).

### Step 5 — Verification gate
Jalankan quality gate proyek: `py -m pytest tests/ -v` (backend),
`npm run typecheck`, dan `npm run lint` (root). Semua harus hijau.

## MVP Scope
IN: langkah 1–5 di atas.
OUT: lihat "Not Doing".

## Not Doing (and Why)
- Manual override UI (V5) — biaya UI besar, mayoritas kasus cukup auto-fill;
  tambah nanti kalau ternyata AI sering salah
- Validator 他/她 deterministik (V3) — bagus tapi cross-check kedua; buktikan
  dulu V1 cukup
- Post-translation pronoun auditor (V4) — safety net, bukan pencegahan;
  scope creep
- Gender untuk non-person terms — sect/pedang bukan orang, bikin noise
- Character sheet penuh (V7) — terlalu besar, gender dulu yang paling sakit

## Open Questions
- Gender di kolom sendiri atau cukup prefix di `notes`? (kolom sudah di-
  approved, tapi prefix notes = zero migration — keputusan final: kolom, sudah
  user-approve)
- Kalau extraction pertama gagal (sample tanpa pronoun), kapan retry? Ada
  extract_chapter_count limit — apakah perlu re-extract trigger?
