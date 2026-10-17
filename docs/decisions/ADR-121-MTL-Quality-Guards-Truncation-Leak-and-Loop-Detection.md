# ADR-121: MTL Quality Guards — Truncated-Output Preservation, Source-Script Leak & Phrase-Loop Detection

## Status
Accepted (diimplementasikan pada commit `ccdb5c0`, Issue #21; ADR ditulis retroaktif pada audit 2026-10-16)

## Date
2026-10-15

## Context
Audit pipeline AI provider, Fidelity Checker, Hallucination Detector, Glossary Lock, dan Prompt Engine pasca-commit `917dcff` menemukan 7 celah kualitas MTL (2 Critical, 4 High, 1 Medium):

1. **Teks parsial hilang** (*Critical*): bila Gemini berhenti karena batas token (`finish_reason == "length"`), `GeminiAdapter.chat_completion()` langsung mengembalikan `TRUNCATED_MARKER`, sehingga seluruh teks yang sudah dihasilkan dibuang dan mekanisme auto-continue (ADR-046) tidak punya bahan untuk dilanjutkan.
2. **Kebocoran aksara sumber tidak terdeteksi** (*Critical*): `verify_translation_fidelity()` meloloskan terjemahan yang masih memuat Hanzi/Hangul/Kana mentah, pengulangan frasa, dan meta-komentar AI.
3. **Loop frasa** (*High*): `HallucinationDetector` hanya memangkas pengulangan satu kata (`\b(\w+)(?:\s+\1){7,}\b`), tidak menangani frasa multi-kata yang berulang.
4. **Prompt bias Inggris** (*High*): `build_core_translation_guidelines()` meng-hardcode `"into English"` dan contoh honorifik Inggris, meski bahasa target Indonesia; sumber Jepang tidak punya panduan.
5. **Glossary Lock merusak URL** (*High*): `apply_glossary_lock()` dapat mengganti istilah di dalam URL gambar Markdown, tautan, atau tag HTML, dan tidak mengenali akhiran klitik Indonesia (`-nya`, `-mu`, `-ku`).
6. **`POST /api/translate` tidak sejalan** (*High*): tidak menormalkan deret simbol, tidak meneruskan `translation_mode`, dan tidak menjalankan pembersihan yang sama dengan pipeline batch.
7. **Reapply glossary tanpa fidelity** (*Medium*): endpoint `reapply-glossary` memperbarui teks tanpa mengevaluasi ulang peringatan fidelity.

---

## Decisions

### 1. Preservasi Teks Parsial (`backend/services/ai/gemini.py`)
- Helper `_chat_completion_with_status()` mengembalikan `(content, is_truncated, is_prohibited)`.
- `chat_completion()` hanya mengembalikan `TRUNCATED_MARKER` bila terpotong **dan** kontennya kosong; selain itu konten parsial dikembalikan.
- `stream_chat()` selalu mengirim konten lebih dulu, baru kemudian `TRUNCATED_MARKER`, sehingga auto-continue menerima teks yang sudah ada.

### 2. Guard Fidelity Baru (`backend/services/fidelity_checker.py`)
- `count_untranslated_script_chars()` menghitung aksara CJK/Hangul/Kana di terjemahan. Untuk sumber CJK, peringatan muncul bila jumlahnya ≥ 15 karakter, atau ≥ 6 karakter dengan rasio ≥ 2%. Simbol yang memang dipertahankan prompt (mis. `囧`, `凸`) dikecualikan lewat `ALLOWED_KAOMOJI_CHARS` (`fidelity_checker.py:15`), bukan lewat ambang; ambang hanya memberi toleransi untuk sisa kecil yang lain.
- Deteksi loop frasa (`HallucinationDetector.detect_repeated_phrases(threshold=4)`, frasa 2–8 kata) dan meta-komentar/sentinel AI (`META_LEAKAGE_RE`). Catatan: deteksi melihat frasa 2–8 kata, sedangkan pembersih (§3) memangkas 2–10 token.
- Peringatan ditampilkan di `FidelityManagementModal.tsx`.

### 3. Pembersih Loop & Wrapper
- `PHRASE_LOOP_RE` + `strip_phrase_repetition_loops()` memangkas frasa 2–10 token yang berulang ≥ 4 kali; dipanggil di akhir `strip_repetitive_character_loops()`.
- `ContextEngine.strip_ai_conversational_wrappers()` dan `strip_inline_bilingual_notes()` dipanggil di `clean_final_translation()`.

### 4. Prompt Sadar Bahasa (`backend/services/prompt_templates.py`)
- Aturan dan contoh honorifik mengikuti bahasa target; dukungan `source_lang == "Japanese"` dengan aturan honorifik Jepang (`-san`, `-kun`, `-sama`, …).

### 5. Glossary Lock Aman URL & Klitik (`backend/services/glossary_lock.py`)
- Span yang dilindungi (tidak pernah diganti): gambar Markdown `![…](…)`, tautan `[…](http…)`, tag HTML `<…>`, URL telanjang, dan placeholder gambar `❖IMAGE_n❖` / `❖GAMBAR_n❖`.
- Batas kanan klitik `(?=(?:-?(?:nya|mu|ku))?\b)` sehingga `Rahmatnya` tetap dikenali.

### 6. Penyelarasan `POST /api/translate` & Reapply Glossary
- `/api/translate` menormalkan deret simbol (`□■•…` maksimal 3), meneruskan `translation_mode` dari `GlobalSetting`, dan memakai pembersihan yang sama.
- `reapply-glossary` (per bab maupun per thread) menghitung ulang `verify_translation_fidelity()`.

---

## Consequences

### Positive
- Bab panjang yang terpotong tidak kehilangan teks. Pada jalur **streaming** (`stream_chat`), auto-continue dapat melanjutkan dari teks yang ada.
- Terjemahan setengah jadi (aksara sumber bocor, loop, meta-komentar) terdeteksi otomatis dan bisa diperbaiki selektif lewat Fidelity Hub.
- Glosarium tidak lagi merusak tautan dan gambar.

### Negative / Trade-offs
- Ambang deteksi adalah heuristik: terjemahan yang sengaja mempertahankan banyak istilah CJK bisa memicu peringatan palsu, dan loop pendek (< 4 kali) lolos.
- `PHRASE_LOOP_RE` hanya mencakup aksara Latin; loop di dalam teks CJK yang tidak diterjemahkan ditangani oleh guard kebocoran aksara.
- **Pemanggil non-streaming kehilangan sinyal "terpotong"** (terverifikasi council 2026-10-17): `chat_completion()` kini mengembalikan teks parsial tanpa penanda bila terpotong. Pemanggil seperti `POST /api/translate` (`translate.py:138`), fallback non-stream di `background_translator.py:531`, ekstraksi glosarium (`context_engine.py:907`, `:943`), dan polish judul menerima teks yang mungkin terpotong tanpa tahu. Guard fidelity (§2) dan "Fix Truncated" (`is_truncated_mid_sentence`) tetap bisa menandainya setelahnya. Tindak lanjut yang disarankan: kembalikan status terpotong ke pemanggil non-stream (mis. lewat `_chat_completion_with_status`).
