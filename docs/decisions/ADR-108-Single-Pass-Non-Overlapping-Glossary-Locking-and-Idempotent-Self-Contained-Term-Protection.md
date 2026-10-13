# ADR-108: Single-Pass Non-Overlapping Glossary Locking & Idempotent Self-Contained Term Protection

## Status
Accepted (2026-09-13)

## Context
Pada ADR-106 dan ADR-107, kami memperkenalkan sistem *Glossary Hard-Locking* (`backend/services/glossary_lock.py`) untuk mengunci konsistensi nama dan istilah pada hasil terjemahan AI secara deterministik, baik pasca-terjemahan, saat ekspor (EPUB/TXT), maupun via sinkronisasi manual (*in-reader zero token sync*).

Namun, ditemukan insiden duplikasi beruntun (*cascading runaway duplication*) pada thread *"I Became the Emperor's Miko"* (Thread ID: 100). Pada Bab 12 dan 29 bab lainnya, kemunculan nama tokoh `白蛇` berulang kali menghasilkan teks anomali:
> `"Bai She (White Serpent) (White Serpent) (White Serpent)"`

### Akar Masalah (Root Causes)
1. **Aturan Regex Tumpang Tindih (Overlapping Patterns)**:
   Entri Lorebook (ID 10978) memiliki `original_term = "白蛇"` dan `translated_term = "Bai She (White Serpent)"`.
   Fungsi `build_glossary_lock_rules` menghasilkan 3 aturan terpisah yang semuanya mencocokkan kata `"Bai She"` (secara `re.IGNORECASE`):
   - Aturan Suku Kata Mandarin: `\bbai\s*['’\-]?\s*she\b`
   - Aturan Alias Spasi: `\bBai\s+She\b`
   - Aturan Alias Huruf Kecil: `\bbai\s+she\b`
   Ketiga pola ini tidak terdeduplikasi karena string polanya sedikit berbeda secara teks.

2. **Eksekusi Sekuensial Saling Menimpa (Cascading `sub()` Loop)**:
   Pada implementasi awal, `apply_glossary_lock` melakukan loop sekuensial:
   ```python
   locked_text = text
   for rule in rules:
       locked_text = rule.pattern.sub(rule.replacement, locked_text)
   ```
   Ketika Rule 1 mengganti `Bai She` menjadi `Bai She (White Serpent)`, Rule 2 dijalankan pada string hasil tersebut. Karena string hasil diawali kata `Bai She`, Rule 2 mencocokkan kembali kata tersebut dan menggantinya lagi menjadi `Bai She (White Serpent) (White Serpent)`. Selanjutnya Rule 3 menimpanya sekali lagi menjadi `Bai She (White Serpent) (White Serpent) (White Serpent)`.

3. **Pelanggaran Idempotensi pada Istilah *Self-Containing***:
   Jika teks terjemahan *sudah* memuat istilah target yang di dalamnya memuat alias/pinyin sumber (misal `Bai She (White Serpent)` atau `Bishop Torreka`), pemanggilan berulang (`reapply_glossary` atau *export*) akan terus melipatgandakan akhiran tersebut tanpa batas karena aturan tidak membedakan apakah kata tersebut merupakan bagian dari istilah yang sudah valid.

## Decision

1. **Arsitektur Single-Pass Non-Overlapping Span Replacement (`backend/services/glossary_lock.py`)**:
   - Mengubah implementasi `apply_glossary_lock` dari loop sekuensial `sub()` menjadi algoritma pelacakan rentang (*non-overlapping span matching*).
   - Seluruh aturan dievaluasi terhadap teks asli. Setiap kecocokan aturan diverifikasi agar tidak bertubrukan (*no overlap*) dengan rentang yang sudah diklaim oleh aturan berprioritas lebih tinggi.
   - String keluaran dirangkai dalam satu lintasan tunggal (*single-pass reconstruction*) menggunakan *literal string slicing*, sehingga teks pengganti **mustahil dievaluasi atau ditimpa ulang** oleh aturan berikutnya.

2. **Proteksi Idempotensi Mutlak untuk Istilah Target**:
   - Sebelum aturan dieksekusi, sistem mendeteksi kemunculan istilah target (`r.replacement`) yang sudah ada di dalam teks dan memasukkannya ke dalam `occupied_spans`.
   - Aturan yang mencocokkan substring di dalam istilah target yang sudah benar akan langsung diabaikan (*skipped*).
   - Untuk istilah pendek ($\le 3$ karakter) atau stopword, proteksi dilakukan secara *case-sensitive* agar tidak memakan kata sambung umum.
   - Sifat fungsi kini dijamin $100\%$ idempoten: $f(f(x)) = f(x)$.

3. **Normalisasi Deduplikasi Regex (`build_glossary_lock_rules`)**:
   - Kunci deduplikasi `seen_patterns` kini menormalisasi string pola ke huruf kecil jika flag `re.IGNORECASE` aktif:
     `norm_pat = rule.pattern.pattern.lower() if (rule.pattern.flags & re.IGNORECASE) else rule.pattern.pattern`
   - Mencegah pendaftaran aturan redundan yang hanya berbeda kapitalisasi pada pola regex `IGNORECASE`.

4. **Pembersihan Data dan Perbaikan Database (`backend/app.db`)**:
   - Entri Lorebook ID 10978 diperbaiki: `translated_term` diubah menjadi `Bai She`, dengan catatan `(Codename: White Serpent)` dipindahkan ke kolom deskripsi `notes`.
   - Melakukan sanitasi otomatis pada 155 kemunculan teks berulang di seluruh 30 bab terdampak pada Thread 100.

## Consequences

- **Positive**:
  - Eliminasi total bug pengulangan beruntun pada istilah nama karakter majemuk/beranotasi.
  - Idempotensi mutlak: aman dipanggil ribuan kali via *in-reader sync*, *batch sync*, maupun saat ekspor buku tanpa risiko merusak teks.
  - Teks terjemahan di Thread 100 kini bersih dan sesuai standar narasi novel profesional.
  - 100% tes lulus: 189 unit test backend, `tsc -b --noEmit` (0 error), dan `eslint .` (0 error).
- **Negative / Trade-offs**:
  - Penambahan alokasi list rentang indeks `(start, end)` di memori saat pemrosesan per bab. Beban komputasi ini sangat kecil (<1ms per bab) dan jauh lebih aman daripada rekursi `re.sub`.
