# ADR-137: Riset Model Kedua Lokal untuk Konteks Halaman (Overlay)

## Status
Proposed (2026-10-25). Hasil riset terukur; belum ada kode produksi. Menunggu keputusan pengguna.

## Context
Mode overlay menerjemahkan tiap balon sendiri-sendiri dengan `index-translate-2b`, sehingga alur dialog, nama, dan nada tidak terjaga. Sesi sebelumnya membuktikan konteks tidak bisa dimasukkan ke prompt Index-Translate (model menyalin konteks) dan transkripsi lewat Index-Translate tidak andal. Pertanyaan: apakah model kedua di LM Studio menolong, dan di mana ditempatkan.

Model di LM Studio (RTX 3050 4 GB): `google/gemma-4-e4b` (visi, Q4_K_M, konteks 131072), `qwen/qwen3-4b-2507` (teks, 262144), `qwen3.5-4b-uncensored-hauhaucs-aggressive` (visi, Q4_K_M), `prism-ml/bonsai-27b` (Q1, tidak dicoba), `index-translate-9b`. LM Studio memuat model secara otomatis saat dipanggil; panggilan pertama ke model yang belum dimuat memakan ~11-22 dtk (gemma 22,6 dtk, qwen3 11,1 dtk), panggilan berikutnya 2-4 dtk per halaman.

## Hasil

### Eksperimen A: penyunting teks setelah Index-Translate (tanpa gambar)
Data: draf Indonesia nyata `events3.json` (82 halaman, 761 balon; 49 `description` + 1 `refusal` = 6,6% balon bermasalah). 6 halaman (3, 4, 5, 12, 30, 50; 69 balon), prompt: daftar draf berurutan kanan ke kiri, keluaran JSON array berjumlah sama.

| Model | Konteks halaman sebelumnya | JSON valid | Jumlah elemen sama | Latensi/halaman | Kemiripan dgn draf | Komentar tersisa |
|---|---|---|---|---|---|---|
| gemma-4-e4b | 0 | 6/6 | 6/6 | 2,1-4,1 dtk (+22 dtk pemuatan) | 0,89-1,0 | 0 |
| gemma-4-e4b | 2 halaman | 6/6 | 6/6 | 2,5-4,3 dtk | 0,89-1,0 | 1 (hlm. 3) |
| qwen3-4b-2507 | 0 | 6/6 | 6/6 | 1,6-3,4 dtk (+11 dtk) | 0,90-0,99 | 1 (hlm. 3) |
| qwen3.5-4b (uncensored) | 0 | 3/6 | 3/6 | 0,4-3,6 dtk | 0,95-0,97 | 0 |

Temuan jujur:
- Penyunting hanya **membersihkan**: membuang pengantar ("Teks dalam gambar:", "Ini adalah teks dari sebuah manga ...", blok kode) dan merapikan tanda kutip. Kemiripan ~1,0 berarti hampir tidak ada penyuntingan alur; ia tidak menyalin konteks halaman sebelumnya ke keluaran, tetapi juga tidak memperbaiki terjemahan yang salah makna.
- Konteks 2 halaman tidak mengubah keluaran secara terukur (kemiripan sama, malah satu komentar lolos di hlm. 3). Tidak ada bukti konteks menolong.
- Kesalahan: beberapa balon sah dikosongkan (`...`, 2 balon pendek di hlm. 5, `invent` 1), komentar "Manga ini menunjukkan bahwa ..." lolos; Qwen3.5 gagal JSON/jumlah di 3 dari 6 halaman.
- Pembersihan yang sama sudah dilakukan deterministik oleh `translation_guard`, gratis dan tanpa memuat model kedua.
- Penilaian alur dialog bersifat subjektif (saya membaca urutan teks): tidak terlihat perbaikan alur karena kesalahan utamanya ada di terjemahan per balon (makna keliru), bukan di gaya; model teks tanpa gambar tidak bisa memperbaikinya tanpa mengarang.

### Eksperimen B: fallback visi untuk kotak gagal
Keterbatasan: ZIP uji sudah terhapus dari cache Windows, sehingga dipakai 95 halaman PDF render lain (524 balon). Index-Translate hanya gagal pada 7 kotak (1,3%): 4 `description`, 3 `loop`, bukan 50. Sampel terlalu kecil untuk kesimpulan statistik.
- `gemma-4-e4b` pada 7 kotak gagal: 4 dijawab NOTEXT (kemungkinan memang tanpa teks), 3 menghasilkan terjemahan yang tampak sah ("Aku adikmu...", "Aku sayang kamu~ ...").
- Pada 20 kotak kontrol (Index-Translate sukses): Gemma memberi NOTEXT pada 3 (15%), dan beberapa keluaran bocor ke Inggris/romaji ("Sa... sa, work's work", "Aa ni kitsu"). Jadi Gemma E4B pembaca teks Jepang yang lebih lemah daripada Index-Translate; hanya cocok sebagai cadangan untuk kotak yang sudah gagal.
- Latensi ~0,9 dtk per kotak setelah dimuat.

## Decision (usulan)
Arsitektur **B penuh (model visi menerjemahkan halaman utuh) tidak dipilih**: tidak ada bukti pembacaan Gemma E4B melampaui Index-Translate. Arsitektur **A (penyunting teks) tidak layak dibangun sekarang**: manfaatnya hanya pembersihan yang sudah dicakup `translation_guard`, dan konteks tidak terbukti menolong.
Satu opsi kecil bernilai: **fallback visi per kotak gagal** (varian B terbatas): setelah retry Index-Translate gagal, kirim crop ke model visi opsional yang dipilih di Pengaturan (mati secara default, lokal saja). Dampaknya terbatas (1-7% balon) dan bukti masih lemah (3/7).

## Risiko
- Pemuatan/penggantian model di LM Studio 11-22 dtk dan memakan VRAM 4 GB; bergantian Index-Translate dan model kedua per halaman akan memboroskan waktu (urutkan: semua kotak dulu, lalu semua fallback).
- Model "uncensored"/Qwen3.5 tidak stabil untuk JSON; Gemma bisa menolak konten dewasa (belum teramati pada sampel ini).
- Sampel kecil (6 halaman teks, 7 kotak gagal); satu bab, satu bahasa.

## Langkah TDD berikutnya (bila disetujui)
1. RED: tes `translate_page_boxes` memanggil `fallback_translate(crop)` hanya untuk kotak berstatus gagal, dan tidak memanggilnya saat pengaturan mati.
2. GREEN: klien fallback memakai `ai/factory.py` + pengaturan model/base URL; keluaran lewat `classify_image_reply`.
3. REFACTOR + tombol UI opsional "Cadangkan kotak gagal dengan model lain", default mati.
4. Ulangi ukur pada bab webtoon dengan ≥50 kotak gagal sebelum mengaktifkan.

Skrip eksperimen ada di scratchpad sesi (tidak di repo).

## Implementasi (2026-10-25)
Status berubah menjadi Accepted untuk bagian fallback saja; penyunting teks (A) dan terjemahan halaman penuh (B) tidak dibangun.
- `services/manga_fallback.py`: prompt fallback, `NOTEXT` menjadi teks kosong, balasan lolos `classify_image_reply`.
- `services/manga_pipeline.py`: parameter `fallback_crop`; dipanggil hanya untuk kotak yang ditolak (`NonTranslationError`) atau kosong, setelah semua panggilan utama halaman itu selesai (satu kali ganti model per halaman). Galat penyedia tidak memicu fallback. Tiga penolakan model berturut-turut di awal tidak lagi dianggap "penyedia mati".
- Konkurensi: crop dikirim `CROP_CONCURRENCY = 4` sekaligus per halaman (sesuai LM Studio dengan 4 slot paralel); urutan hasil tetap. Kecepatan belum diukur pada bab nyata.
- `POST /api/translate/images`: field form `fallback_model` (opsional, hanya efektif dengan `overlay`, base URL sama dengan model utama).
- UI: kolom teks "Perbaiki kotak gagal dengan model lain", kosong = mati, disimpan per workspace lewat `getWorkspaceStorageKey`.
- Belum: pengukuran pada bab webtoon dengan ≥50 kotak gagal; pemilihan model dari daftar Pengaturan.
