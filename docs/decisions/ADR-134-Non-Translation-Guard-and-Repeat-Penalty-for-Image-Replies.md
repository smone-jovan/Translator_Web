# ADR-134: Pengaman Hasil Bukan-Terjemahan dan Penalti Pengulangan untuk Balasan Gambar

## Status
Accepted (2026-10-24). Diuji dengan tes unit/router dan provider tiruan. Ambang heuristik **belum divalidasi** pada halaman manga nyata.

Hasil uji kecil ke LM Studio lokal (`index-translate-2b`, suhu 0, teks Mandarin pendek, 5 permintaan): semua mengembalikan HTTP 200. `repeat_penalty=50` mengubah keluaran (tanda baca terakhir `.` menjadi `!`), sedangkan parameter palsu `bogus_param=50` dan `repeat_penalty=1.1` tidak mengubahnya. Jadi `repeat_penalty` **dikenali dan dipakai** LM Studio, dan parameter tak dikenal diabaikan tanpa galat (fallback "tanpa parameter" hanya relevan bila server berubah menjadi menolak). `frequency_penalty=1.5` tidak menunjukkan perubahan pada teks sependek itu (tidak konklusif). Dampak 1,1 terhadap pengulangan pada halaman gambar belum diukur.

## Context
Satu bab 184 gambar yang diterjemahkan halaman utuh dengan `index-translate-2b` menghasilkan banyak balasan yang bukan terjemahan: deskripsi gambar, penolakan model terhadap konten dewasa, dan pengulangan baris yang terpotong di batas 1024 token. Semuanya ditampilkan apa adanya dan ikut ke teks gabungan dan PDF. Target bahasa di database `English` (bukan bug). Aplikasi sudah mengirim `enable_thinking: false` untuk model Index-Translate (`LMStudioAdapter._extra_payload`).

## Decision
- `backend/services/translation_guard.py`: `classify_image_reply(text, finish_reason)` mengembalikan `ok | truncated | empty | refusal | description | loop`. Hanya dipakai pada balasan **gambar**, tidak pernah pada terjemahan teks.
  - `refusal`: balasan < 400 karakter yang cocok dengan frasa penolakan asisten yang spesifik (mis. "explicit adult content", "feel free to ask", "I cannot provide/assist/translate", padanan Indonesia/Mandarin/Jepang). Frasa umum seperti "I can't believe it" tidak dihitung.
  - `description`: dibuka dengan "This image/This is an/In this scene/Gambar ini…" **dan** memuat >= 3 kata kosakata deskripsi berbeda.
  - `loop`: baris yang sama (>= 8 karakter) berulang >= 4 kali, atau rasio baris unik < 0,4 pada >= 8 baris, atau potongan 40 karakter (>= 8 karakter berbeda) berulang >= 4 kali.
  - `truncated`: `finish_reason == "length"` tanpa loop: teks dipertahankan dan diberi penanda `truncated`.
- `LMStudioAdapter.chat_completion_detailed(...)` mengembalikan `Completion(text, finish_reason)` dan menerima parameter sampling tambahan (`messages`, `model`, `stream` tidak bisa ditimpa); `chat_completion` memanggilnya, sehingga perilaku teks tidak berubah.
- `translate_image_checked` (`routers/image_translate.py`): permintaan gambar mengirim `repeat_penalty` 1,1; balasan `loop` diulang **sekali** dengan 1,2; `refusal`, `description`, `empty` tidak diulang. Bila server menolak parameter tambahan, permintaan diulang tanpa parameter itu (dengan peringatan di log). Provider lama tanpa `chat_completion_detailed` tetap bekerja lewat `chat_completion`.
- Kegagalan menjadi `NonTranslationError(reason)`: `page_error` dengan `reason` dan pesan Indonesia di rute folder gambar dan PDF; HTTP 422 di `POST /api/translate/image`. Pada mode overlay, potongan gelembung yang gagal dilewati seperti kegagalan kotak yang sudah ada. Halaman gagal otomatis tidak ikut ke teks gabungan dan memakai placeholder di PDF.
- UI: alasan tampil per halaman gagal, tanda "(terpotong)", dan banner yang menyarankan mode overlay bila mode itu mati dan >= 30% halaman gagal karena alasan di atas; catatan bahwa bahasa target mengikuti Pengaturan.

## Consequences / Residual
- Heuristik bisa salah menandai terjemahan sah atau meloloskan deskripsi; ambang konservatif dan alasan terlihat. Daftar pola ada di satu tempat untuk disetel.
- Nama parameter `repeat_penalty` belum terverifikasi di LM Studio; bila ditolak, fallback tanpa parameter. Penalti terlalu tinggi dapat merusak terjemahan sah.
- Percobaan ulang menambah ±3 detik pada halaman yang loop.
- Tidak ada deteksi bahasa; deskripsi berbahasa Inggris saat target Indonesia hanya tertangkap lewat pola.
- Penolakan model tidak bisa dicegah oleh aplikasi; hanya ditandai dan disarankan mode overlay atau model lain.

## Files
`backend/services/translation_guard.py`, `backend/services/ai/base.py` (`Completion`), `backend/services/ai/lm_studio.py`, `backend/services/ai/index_translate.py` (konstanta penalti), `backend/routers/image_translate.py`, `image_batch_translate.py`, `pdf_translate.py`, `src/lib/pdfTranslate.ts`, `src/components/ImageFolderTranslatePanel.tsx`. Tes: `test_translation_guard.py`, `test_lm_studio_detailed.py`, `test_routers/test_non_translation_guard.py`.

## Addendum (2026-10-24): pengulangan frasa pendek di kotak overlay
- Kasus nyata: pada kotak teks kecil, model mengulang "...Okay? ...Okay? ..." sampai ~3000 karakter. Potongan 40 karakternya hanya punya 7 huruf berbeda (di bawah ambang 8), sehingga lolos pengaman, lalu ekspor PDF menolak dengan "boxes must be a JSON array ..." karena teks kotak > 2000 karakter.
- `translation_guard.is_loop` kini juga menandai satu unit pendek (2-40 karakter) yang berulang berurutan >= 5 kali dan membentang >= 150 karakter; tawa/napas pendek ("Ha ha ha ha") tetap lolos. Balasan seperti ini ikut diulang sekali dengan penalti lebih kuat.
- `manga_pipeline.MAX_BOX_TEXT_CHARS` (2000, dipakai juga oleh router): teks kotak yang lebih panjang dibuang (kotak dikosongkan) agar ekspor tidak gagal.
- Tes: `test_translation_guard.py`, `test_manga_pipeline.py`. Pada ZIP nyata 82 halaman: 5 dari 740 kotak ditandai loop (3 di atas 2000 karakter, 2 sekitar 1100), tanpa salah deteksi lain yang terlihat.
