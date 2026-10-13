# ADR-109: Gender-Aware Glossary — Extraction Token, Backfill, dan Pronoun Injection

## Status
Accepted (2026-10-03)

## Context
Dalam penerjemahan web novel China, nama tokoh sering kali ambigu secara gender — nama yang terdengar feminim dimiliki karakter pria (dan sebaliknya). Model AI penerjemah menebak gender dari *bentuk nama*, menghasilkan pronoun yang salah pada output bahasa Inggris (`he/she` tertukar) — terutama merugikan pembaca utama yang membaca terjemahan Indonesia/Inggris. Kesalahan ini sering terjadi dan tidak tertangkap oleh fidelity checker yang ada.

Ide awal (V1 dari sesi idea-refine, `docs/ideas/gender-aware-glossary.md`) menuntut sistem glossary mengetahui gender setiap karakter. Tiga asumsi kunci divalidasi sebelum implementasi: (1) extraction pass (25 chapter pertama) cukup berisi bukti pronoun `他/她`; (2) injeksi gender ke prompt mengurangi error he/she; (3) penambahan gender tidak mengubah perilaku glossary lock/export.

Keterbatasan sistem lama: `LorebookEntry` tidak memiliki field gender, extraction prompt hanya mewajibkan konteks deskriptif tanpa gender eksplisit, dan jalur `if not exists` di `auto_save_glossary` tidak pernah memperbarui entri yang sudah ada (backfill mustahil).

## Decision

1. **Skema: kolom `gender` pada `LorebookEntry` (`backend/database.py`)**
   - `gender: Mapped[Optional[str]] = mapped_column(String(10))` — nilai kanonik `MALE` / `FEMALE` / `NULL` (unknown), nullable tanpa default (row lama tak terpengaruh).
   - Auto-migration kondisional di `init_db()`: `if 'gender' not in columns_lb:` → `ALTER TABLE lorebook_entries ADD COLUMN gender VARCHAR(10)`, mengikuti pola `fidelity_warning`/`is_locked` yang sudah terbukti, berjalan per-engine (app.db & ghost.db) tanpa state global.

2. **Extraction prompt: Rule 5 GENDER TOKEN (`backend/services/prompt_templates.py`)**
   - Setiap entry PERSON wajib menempatkan token persis `MALE — ` / `FEMALE — ` (kata, spasi, em-dash U+2014, spasi) di awal parenthetical, **hanya bila teks sumber memberi bukti eksplisit** (`他/她`, `师兄/小姐`); bila ragu → omit (gender tetap unknown); dilarang menebak dari morfologi nama; entry non-person dilarang membawa token.
   - Klausula eksplicit: token **selalu** kata bahasa Inggris huruf besar — tidak pernah diterjemahkan/dilokalkan meski `target_lang` bukan Inggris (mencegah drift `PRIA —` yang mematahkan parser).

3. **Parser & backfill (`ContextEngine.auto_save_glossary`, `backend/services/context_engine.py`)**
   - Regex toleran case & dash: `re.match(r"\s*(MALE|FEMALE)\s*[—–-]\s*", ctx, re.IGNORECASE)` → `.upper()`; tanpa match → `NULL`.
   - Entri baru menyimpan `gender`; entri existing di-backfill **hanya bila `gender IS NULL`** (`elif gender and exists.gender is None`) — gender yang sudah terisi tidak pernah ditimpa (keputusan user/AI sebelumnya menang), field lain tidak disentuh.
   - Gate commit diperluas ke `if new_entries or gender_updates`; `enforce_context_limit` tetap hanya untuk entri baru (terverifikasi test invarian).

4. **Injeksi prompt terjemahan (`build_translation_prompt` + `build_core_translation_guidelines`)**
   - **Whitelist-only render**: nilai kolom mentah tidak pernah diinterpolasi — hanya `("MALE", "FEMALE")` yang dirender (gender berasal dari output LLM → data tak terpercaya).
   - Baris glossary: gender disuntikkan ke parenthetical hanya bila catatan belum memuat token (tanpa duplikasi); gender `NULL` → format baris identik byte dengan format lama (nol regresi untuk prompt test eksak).
   - Blok `[PRONOUN / GENDER RULES - MANDATORY]` (he/him/his, she/her/hers, jangan infer gender dari nama) ditambahkan **hanya jika ≥1 entri ber-gender ter-inject** pada prompt tersebut.
   - Satu kalimat statis autoritas gender pada core guidelines — diterima masuk ke mode Quality **dan** Fast (builder mode-agnostic; ~30 token, 0.3% dari cap Fast 10K).

5. **Verification gate**
   - 24 test baru (migrasi, prompt, parser, injeksi) + suite penuh: **213 passed**, `tsc -b --noEmit` 0 error, `eslint .` 0 temuan — dijalankan dan diverifikasi independen oleh stage validasi akhir.

## Consequences

- **Positive**:
  - Glossary kini menjadi sumber kebenaran gender karakter; pronoun `he/she` diikuti deklarasi glossary, bukan tebakan morfologi nama.
  - Entri legacy (11.847 row saat audit) otomatis ter-backfill pada extract/translate ulang berikutnya tanpa intervensi manual.
  - Injection gagal-aman: nilai gender korup/tak dikenal → render legacy + tanpa blok pronoun (mustahil menyuntik konten tak ter-whitelist ke prompt).
  - Nol perubahan kontrak API/publish; format prompt untuk entri tanpa-gender tidak berubah (test lock/export eksak tetap hijau tanpa modifikasi).
  - 100% gate lulus: 213 unit test backend, typecheck strict, lint bersih.

- **Negative / Trade-offs**:
  - Kualitas gender bergantung pada kualitas sample extraction (25 chapter pertama, 1000 char) — bila bukti `他/她` belum muncul, gender tetap `NULL` (diamanatkan: lebih baik unknown daripada salah percaya diri).
  - Token gender kadangkala tidak diparse LLM (drift format) → gagal diaman-ke-`NULL`, fitur melewatkan kasus tersebut tanpa error.
  - Belum ada override manual UI, validator statistik `他/她`, maupun auditor pasca-terjemahan (disengaja, lihat "Not Doing" di `docs/ideas/gender-aware-glossary.md`).
  - Kolom `String(10)` tanpa `CHECK` — SQLite tidak membatasi nilai >10 char (terpotong diam-diam); parser/prompt hanya memakai literal aman sehingga risiko terkendali.

## Related
- Plan & asumsi: `docs/ideas/gender-aware-glossary.md`
- Pola migrasi: ADR-051 (Core Architecture), `fidelity_warning` (plan R4/R5)
- Glossary lock terkait: ADR-106, ADR-107, ADR-108
- Penyempurnaan filter non-manusia, UI badge, & kontrol halusinasi: ADR-110 (`ADR-110-Non-Human-Entity-Sanitization-Visual-Gender-Indicators-and-Anti-Hallucination-Controls.md`)
