# ADR-128: Polish Judul Khusus Index-Translate

## Status
Accepted (2026-10-24).

## Date
2026-10-24

## Context
Polish judul (`POST /api/threads/{id}/translate-titles`, `backend/routers/polish.py`) dirancang untuk LLM umum: satu system prompt panjang, 50 judul berlabel `[CHAPTER_n]:` dalam satu request, lalu hasilnya di-parse per label. Tiga masalah muncul saat model aktif adalah Index-Translate (2B lokal, `backend/services/ai/index_translate.py`):

1. **Prompt di luar distribusi latihnya.** Index-Translate hanya dilatih pada template satu pesan. Dengan system prompt panjang dan label, model mengulang prompt atau menjawab ngawur, sehingga judul rusak.
2. **Langkah "bersihkan judul asli" (ADR-020) menimpa data.** Langkah ini meminta model hanya membersihkan judul Mandarin. Index-Translate hanya menerjemahkan, jadi hasilnya (judul terjemahan) disimpan ke `thread.original_title`.
3. **Pemborosan request.** Percobaan pertama (satu request per judul) memperbaiki kualitas tetapi memboroskan request.

## Decisions

### 1. Jalur Index-Translate memakai template native, tanpa label
- Model dideteksi lewat `is_index_translate_model(active_model)`.
- Judul dikirim lewat `build_index_translate_messages` (satu pesan user), dengan glosarium lorebook yang relevan (`collect_glossary_pairs`). Sinopsis memakai template yang sama.
- Label `[BOOK_TITLE]` / `[CHAPTER_n]` tidak dikirim ke model; label dipasang kembali di sisi server, sehingga logika penugasan hasil yang ada tidak berubah.
- Langkah pembersihan judul asli **dilewati** untuk model ini.

### 2. Batching 10 judul per request, satu judul per baris
- `translate_titles_with_index` mengirim `TITLE_BATCH_SIZE = 10` judul dipisah newline. Judul yang berisi newline diratakan dulu.
- Balasan dipecah per baris (blok `<think>` dibuang, label gema dan tanda kutip dibersihkan lewat `clean_index_title_output`).
- **Jaminan keamanan:** bila jumlah baris balasan tidak sama dengan jumlah judul, balasan tidak bisa dipasangkan dengan aman, maka grup itu diulang **satu judul per request**. Judul tidak pernah dipasangkan dengan tebakan.
- Terverifikasi pada model live (`index-translate-2b`): 10 baris masuk, 10 baris keluar, urutan sama; 24 judul butuh 3 request.

### 3. Provider lain tidak berubah
- Gemini, OpenAI, OpenRouter, dan model LM Studio non-Index-Translate tetap memakai jalur generik semula: system prompt berlabel, 50 judul per request, dan pembersihan judul asli seperti biasa. Semua perubahan di atas hanya aktif bila `is_index_translate_model` benar.


## Alternatives Considered

### Satu request per judul untuk Index-Translate
- Pro: tidak mungkin salah pasang.
- Kontra: N request untuk N judul; boros waktu dan kuota.
- Ditolak sebagai default; tetap dipakai sebagai fallback per grup (Keputusan 2).

### Tetap memakai prompt berlabel dan memperbaiki parser
- Pro: satu jalur kode untuk semua model.
- Kontra: akar masalahnya adalah prompt yang di luar distribusi latih model; parser tidak bisa memperbaiki balasan yang ngawur.
- Ditolak.

### Menghemat request untuk provider berkuota (lewati pembersihan judul asli bila tanpa anotasi, naikkan `CHUNK_SIZE`)
- Pro: mengurangi request Gemini/OpenAI/OpenRouter.
- Kontra: mengubah perilaku jalur generik yang sudah dipakai.
- Sempat diterapkan lalu **dibatalkan**: perubahan ini khusus Index-Translate, jalur generik dibiarkan seperti semula.

## Consequences

### Positive
- Judul, sinopsis, dan `original_title` tidak lagi rusak atau tertimpa saat memakai Index-Translate.
- Request polish Index-Translate turun dari N menjadi ceil(N/10) per polish.

### Negative / Residual
- Judul lama yang sudah terlanjur rusak di database tidak berubah sendiri; perlu polish ulang (`repolish=true`).
- Cakupan tes: `clean_index_title_output`, `translate_titles_with_index`, teruji unit. Alur endpoint `translate_titles` sendiri belum punya tes.
- Jalur label asli (non-Index-Translate) tidak diubah dan tetap bergantung pada model yang patuh format `[CHAPTER_n]:`.

## References
- `backend/routers/polish.py`, `backend/services/ai/index_translate.py`
- `backend/tests/test_services/test_index_translate_profile.py`
- ADR-020 (pembersihan judul asli)
