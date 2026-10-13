# ADR-111: Adaptive Source Language Prompt Engine and Direct Korean Translation

## Status
Accepted (2026-10-06)

## Context
Sebelum ADR ini, seluruh sistem prompt ReadOmni AI mengasumsikan teks sumber berasal dari web novel China (*Chinese web novels*):
- Instruksi sistem menyatakan secara statis: *"Translate the text from Chinese to natural {lang_name}"*, *"No Chinese characters or pinyin allowed"*, dan *"Add the gender token ONLY when the source Chinese text makes it clear"*.
- Ekstraksi glosarium hanya menyimpan istilah jika mengandung Hanzi atau Pinyin (`[\u4e00-\u9fff]`), membuang istilah Hangul (Korea) atau Kana (Jepang).
- Penguncian glosarium (`apply_glossary_lock`) hanya mengunci istilah Hanzi dan Pinyin.
- Pembersihan judul (`clean_and_format_chapter_title`) hanya mengenali penomoran bab Mandarin (`第X章`), mengabaikan format Korea (`제X화`, `X화`, `EP.X`).

Masalah ini menjadi kritis ketika pengguna membaca novel Korea:
Banyak novel Korea di agregator seperti Novalpie di-rip dari Novelpia Korea lalu di-MTL ke Mandarin, atau pengguna mengimpor berkas asli Hangul (Korea). Ketika teks sumber adalah bahasa Korea asli (Hangul), prompt yang mengasumsikan bahasa Mandarin menyebabkan LLM kebingungan, memicu bias terjemahan bahasa Mandarin, kehilangan honorifik khas Korea (*Hyung, Noona, Oppa, Sunbae, -ssi*), serta mengacaukan pemahaman gender akibat fenomena *zero anaphora* (penghilangan subjek/pronomina) pada tata bahasa Korea.

## Decision

1. **Deteksi Bahasa Sumber Dinamis (`detect_source_language`)**:
   - Dibuat fungsi klasifikasi script di `backend/services/prompt_templates.py`:
     - Menghitung rasio karakter Hangul (`[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]`), Kana Jepang (`[\u3040-\u309f\u30a0-\u30ff]`), dan Hanzi Mandarin (`[\u4e00-\u9fff]`).
     - Mengembalikan `'Korean'`, `'Japanese'`, atau `'Chinese'` (default fallback).

2. **Adaptasi Prompt Panduan Terjemahan Utama (`build_core_translation_guidelines`)**:
   - Menerima parameter `source_lang: str = "Chinese"`.
   - Ketika `source_lang == "Korean"`:
     - Target role: *"expert translator of Korean web novels (K-novels / Webtoons)"*.
     - Instruksi anti double-translate: *"Translate ALL story text to {lang_name}. Do NOT output Korean Hangul, and DO NOT translate through Chinese (translate directly from Korean to {lang_name})"*.
     - Honorifik Korea: memelihara/menerjemahkan secara akurat kata sapaan seperti `형/Hyung`, `누나/Noona`, `오빠/Oppa`, `언니/Unnie`, `선배/Sunbae`, `후배/Hoobae`, `아저씨/Ahjussi`, `작가님/Author-nim`, `대표님/CEO-nim`, `-ssi/-nim`.
     - Konvensi System/Hunter/LitRPG Korea: `헌터 = Hunter`, `각성자 = Awakener`, `게이트 = Gate`, `상태창 = Status Window`, `성좌 = Constellation`.
     - Penanganan *Zero Anaphora*: panduan pelacakan gender karakter saat subjek/pronomina dihilangkan di teks Korea.
   - Ketika `source_lang == "Chinese"`: mempertahankan 100% instruksi lama dan kompatibilitas mundur.

3. **Adaptasi Prompt Ekstraksi Glosarium & Judul**:
   - `build_title_translation_prompt`: melarang karakter Hangul pada output jika sumber adalah Korea.
   - `clean_and_format_chapter_title`: otomatis membersihkan prefix bab Korea `제X화`, `제 X 화`, `X화`, `EP.X`, `Episode X`.
   - `build_glossary_extraction_prompt`: contoh istilah Korea (`성진우 → Sung Jin-woo`, `차해인 → Cha Hae-in`, `헌터 협회`) dan aturan pembuktian gender berbasis pronomina Korea (`그/그녀`) atau sebutan kekerabatan (`형/누나/오빠/언니`).

4. **Ekspansi Glosarium & Glossary Lock (`auto_save_glossary`, `glossary_lock.py`)**:
   - Pola script Asia Timur diperluas ke `EAST_ASIAN_CHAR_PATTERN` (mencakup Hanzi, Hangul, dan Kana).
   - Istilah Hangul kini dapat disimpan otomatis ke database tanpa tertolak filter script.
   - Istilah Hangul mentah yang bocor ke output terjemahan secara otomatis dikunci dan diganti ke istilah target glosarium.

## Consequences

- **Positive**:
  - Teks Korea asli (Hangul) kini diterjemahkan langsung ke Bahasa Indonesia/Inggris tanpa bias atau distorsi bahasa Mandarin.
  - Penomoran bab Korea terformat rapi menjadi format zero-padded (`01. Judul`, `15. Judul`).
  - Honorifik dan istilah hunter/dungeon khas web novel Korea diterjemahkan sesuai standar literatur K-novel.
  - Glosarium dan penguncian istilah bekerja mulus untuk aksara Korea, Mandarin, dan Jepang.
  - Kompatibilitas mundur 100% terjaga (seluruh 259 unit test backend lulus).
- **Negative / Trade-offs**:
  - Untuk novel dari Novalpie.cc yang *di servernya sendiri* memang sudah tersimpan dalam wujud teks Mandarin hasil MTL, sistem tetap membaca teks Mandarin tersebut (karena Novalpie tidak menyediakan teks Korea). Namun jika pengguna mengimpor berkas asli Korea (EPUB/TXT), sistem kini 100% memprosesnya secara langsung dari bahasa Korea asli.

## Related
- Penegakan konsistensi gender: ADR-109, ADR-110
- Centralized Prompt Templates: ADR-074
- Glossary Locking Engine: ADR-106, ADR-108
