# Chinese Visual Expressions, Emoticons & Character Gestures Handling

## Problem Statement
Bagaimana kita melatih dan menginstruksikan AI agar mengenali dan mempertahankan karakter visual ekspresi wajah (`囧`, `凸`, `Orz`) serta kaomoji (`(⊙_⊙)`, `(*/ω＼*)`), sekaligus menerjemahkan gestur reaksi karakter dalam tanda kurung (`(汗)`, `(摊手)`) ke dalam bahasa target secara alami tanpa menghapusnya atau merusak tata bacaan?

## Recommended Direction
Kebijakan penanganan ekspresi visual dan gestur reaksi karakter novel web:

1. **Simbol Visual & Kaomoji Murni (Diizinkan Lolos Apa Adanya):**
   - Karakter simbolik visual internet seperti `囧` (wajah melongo/canggung), `凸` (gestur kesal/acungan jari tengah), `Orz` (bersujud pasrah), serta kaomoji ASCII/Unicode (`(⊙_⊙)`, `(*/ω＼*)`, `(눈_눈)`, `╮(╯▽╰)╭`) **diizinkan dipertahankan apa adanya di alur cerita**.
   - AI dilarang keras menghapus kaomoji atau menerjemahkan `囧` / `凸` ke arti kamus kuno harfiah (seperti *"jendela terang"* atau *"pola"*).

2. **Reaksi & Gestur Karakter dalam Tanda Kurung (Diterjemahkan ke Bahasa Target):**
   - Gestur reaksi atau aksi panggung yang ditulis dalam tanda kurung oleh penulis asli **wajib diterjemahkan maknanya ke bahasa target** dalam tanda kurung yang rapi:
     - `(汗)` atau `(冷汗)` → `(keringat dingin)` / `(sweatdrop)`
     - `(翻白眼)` → `(memutar bola mata)` / `(rolls eyes)`
     - `(摊手)` → `(mengangkat bahu)` / `(shrugs)`
     - `(抓狂)` → `(frustrasi)` / `(goes crazy)`
     - `(默)` → `(terdiam)` / `(silence)`
   - AI dilarang menganggap tanda kurung reaksi ini sebagai "anotasi kamus terlarang" yang harus dihapus.

3. **Pembaruan Core Prompt (`backend/services/prompt_templates.py`):**
   - Memperjelas klausul *Chinese Text Handling*: Melarang kebocoran teks kalimat Mandarin biasa, namun **memberikan pengecualian eksplisit untuk Kaomoji/simbol visual (tetap apa adanya) dan mewajibkan penerjemahan tanda kurung reaksi gestur ke bahasa target**.

## Key Assumptions to Validate
- [ ] Model (Gemini, Local LM Studio, OpenRouter) dapat membedakan dengan akurat antara huruf Mandarin narasi biasa (wajib diterjemahkan) vs simbol ekspresi `囧`/`凸` (dipertahankan) vs tanda kurung reaksi `(汗)` (diterjemahkan isinya).
- [ ] Reader frontend merender kaomoji dan simbol Unicode dengan baik tanpa *font cutoff* di berbagai perangkat (desktop & mobile).

## MVP Scope
- **In Scope:**
  - Penambahan instruksi `[EXPRESSION & EMOTICON HANDLING]` di `backend/services/prompt_templates.py` pada `build_core_translation_guidelines()`.
  - Unit test di `test_prompt_templates.py` untuk memverifikasi instruksi pengecualian kaomoji dan penerjemahan gestur tanda kurung.
- **Out of Scope (Not Doing):**
  - Mengubah simbol teks menjadi stiker/gambar gambar PNG.
  - Membatasi jenis kaomoji yang boleh dipakai (biarkan dinamis sesuai kreativitas penulis asli).

## Open Questions & Next Steps
- Mengimplementasikan pembaruan aturan ini langsung ke `backend/services/prompt_templates.py` dan memvalidasi via test suite.
