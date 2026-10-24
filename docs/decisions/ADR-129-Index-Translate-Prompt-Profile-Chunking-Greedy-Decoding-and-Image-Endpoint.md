# ADR-129: Profil Prompt Index-Translate, Chunking, Greedy Decoding, dan Endpoint Terjemahan Gambar

## Status
Accepted (2026-10-24). Diimplementasikan di commit `e158ca5` (profil, chunking, suhu) dan `3f54f8d` (endpoint gambar). Belum diuji pada bab novel nyata dengan model 2B (lihat Negative / Residual).

Tindak lanjut: butir residual "endpoint gambar belum punya antarmuka frontend" ditindaklanjuti oleh ADR-130 (PDF) dan ADR-131 (folder gambar, ekspor PDF); ADR-132 sampai ADR-135 memperluasnya (overlay manga, ZIP, pengaman balasan, WebP). Teks keputusan di bawah dibiarkan sebagai catatan historis.

## Date
2026-10-24

## Context
Pengguna menjalankan terjemahan massal di laptop dengan RTX 3050 (VRAM 4 GB) lewat LM Studio, memakai model lokal kecil `index-translate-2b` (Bilibili Index, berbasis Qwen3.5). Model ini rapuh bila diperlakukan seperti LLM serbaguna:

1. **Suhu 0.3 hard-coded.** Seluruh jalur terjemahan memanggil provider dengan `temperature=0.3`. Model card Index-Translate merekomendasikan greedy decoding (`temperature=0`); pada model 2B, sampling meloloskan token berprobabilitas rendah yang merusak kalimat sesudahnya (campur aksara, nama berubah, kalimat terpotong).
2. **Input panjang membuat model membeo prompt.** Satu bab dikirim sebagai satu request. Model 2B kehilangan instruksi pada input sepanjang bab dan mengulang system prompt alih-alih menerjemahkan.
3. **Format prompt di luar distribusi latih.** Model hanya dilatih pada dua bentuk: satu baris `请将以下文本翻译为…` dan format `instTrans` (`【源文】` + `【约束要求】`). Proyek mengirim `[system, user]` dengan system prompt panjang (aturan, glosarium, aturan gender).
4. **Thinking.** Model card meminta `enable_thinking: false`. LM Studio **mengabaikan** `chat_template_kwargs` pada `/v1/chat/completions` untuk model Qwen3.5 (bug tracker LM Studio #1559, #1773, #1990), sehingga model menulis penalaran dan menghabiskan `max_tokens`.
5. **Tidak ada terjemahan gambar.** Repo GGUF Index-Translate menyertakan proyektor visual (`mmproj`) dan LM Studio memasangkannya otomatis bila ada di folder model; proyek belum punya jalur untuk gambar (fitur gambar yang ada hanya cache gambar untuk pembaca).

Batas perangkat keras relevan: `lms load --estimate-only` pada konteks 8K menunjukkan 9B Q4_K_M + mmproj butuh 7.32 GiB (tidak muat di 4 GiB; kecepatan teramati ~6 token/detik), sedangkan 2B Q8_0 + mmproj butuh 3.01 GiB (muat).

## Decisions

### 1. Suhu terjemahan menjadi atribut provider
- `BaseAIProviderAdapter.translation_temperature = 0.3` (perilaku lama untuk semua provider); `LMStudioAdapter.translation_temperature = 0.0`.
- Jalur batch (`background_translator.py`: stream, fallback non-stream, pemulihan) dan `POST /api/translate` membaca `getattr(provider, "translation_temperature", 0.3)`. Jalur non-terjemahan (polish, ekstraksi glosarium, konteks) tidak berubah.

### 2. Chunking permintaan terjemahan untuk provider kecil
- `BaseAIProviderAdapter.translation_chunk_chars = 0` (nonaktif); `LMStudioAdapter.translation_chunk_chars = 2500`.
- `ChunkedTranslationProvider` (`backend/services/ai/chunking.py`) membungkus provider lewat `maybe_chunk`. Teks dipecah di batas paragraf, lalu kalimat (`。！？!?….`), lalu hard-split bila satu kalimat melebihi batas. Hasil antar-chunk digabung dengan `\n\n`.
- Hanya pesan bentuk **pertama** yang dipecah (`[system, user]`, atau pesan yang persis sama dengan keluaran `message_builder`). Putaran lanjutan (continuation) dan bentuk lain dilewatkan apa adanya.
- Bila satu chunk mengembalikan marker truncated/prohibited, chunk berikutnya tidak dikirim dan marker diteruskan ke logika yang sudah ada.
- Jalur `/translate` kini ikut di-chunk (sebelumnya hanya batch).

### 3. Profil prompt Index-Translate (`backend/services/ai/index_translate.py`)
- Deteksi lewat `is_index_translate_model(model)`: nama model, dinormalkan (spasi, `-`, `_` dibuang, huruf kecil), memuat `indextranslate`. Index-Homura/NativeLong sengaja tidak terdeteksi.
- Untuk model terdeteksi, request adalah **satu pesan `user`**, tanpa system prompt:
  - Tanpa glosarium: `请将以下文本翻译为{印尼语|英语}，直接输出翻译结果，不要进行任何解释。\n\n{teks}`.
  - Dengan glosarium: format `instTrans` kanonik dari klien resmi (`translate.py`): `【源文】`, `【约束要求】`, `1. 【硬性要求】专名/术语对照: 原→terjemahan、…`, dan sufiks `只输出译文，不要有任何额外说明。`.
- Glosarium diambil lewat `collect_glossary_pairs`: hanya entri lorebook **tidak diarsipkan, bukan sampah, dan benar-benar muncul di teks**, dikunci lebih dulu lalu istilah terpanjang, maksimal 30. Tidak ada efek samping (tidak menaikkan `usage_count`).
- Bahasa target dipetakan `Indonesian` → `印尼语`, selain itu `英语` (mengikuti logika `ContextEngine`).
- Pada tiap chunk, `message_builder` membangun ulang prompt lengkap, sehingga header template tidak ikut terpotong.
- Diterapkan di worker batch dan `POST /api/translate`. Putaran lanjutan memakai `base_messages` + pesan asisten + prompt lanjutan yang ada; retry anti-ringkasan untuk model ini hanya mengirim ulang prompt yang sama.

### 4. Thinking: kirim parameter, tetapi syarat operasionalnya ada di LM Studio
- `LMStudioAdapter._extra_payload()` menambahkan `chat_template_kwargs: {"enable_thinking": false}` untuk model Index-Translate. Efektif di llama-server/vLLM (sesuai README Index), **tidak efektif di LM Studio**.
- Untuk LM Studio, thinking harus dimatikan di pengaturan model atau dengan menaruh `{%- set enable_thinking = false %}` di baris pertama template Jinja. Pemilik proyek sudah melakukannya untuk model Index dan Qwen. Terverifikasi live: balasan 2B tidak memuat `reasoning_content`.

### 5. `POST /api/translate/image`
- Router: `backend/routers/image_translate.py`. Nama file sengaja **bukan** `translate_image.py` karena `.gitignore` baris 78 (`translate_*.py`) akan mengecualikannya dari git.
- Body: `image_data_url` (wajib), `model`, `target_lang`, `lm_url`. Balasan: `{translation, model_used}`.
- Hanya model Index-Translate (400 untuk model lain). Hanya data URL base64 `png/jpeg/webp`, maksimal 10 MB (413 bila lebih; 400 untuk format lain). **Server tidak pernah mengunduh URL dari klien** (menutup vektor SSRF).
- Prompt `请将图片中的文本翻译为{bahasa}，直接输出翻译结果，不要进行任何解释。`, suhu dari provider (0), `max_tokens = 1024` (sama dengan klien resmi). Blok thinking dibersihkan lewat `ContextEngine.clean_final_translation`. Kegagalan provider menjadi 502 tanpa membocorkan detail.
- Tidak menyimpan apa pun ke database dan tidak terkait chapter.

## Alternatives Considered

### Hanya menurunkan suhu dan mempertahankan system prompt
- Pro: perubahan terkecil.
- Kontra: tidak menyentuh akar masalah prompt di luar distribusi latih (poin 3) dan input panjang (poin 2).
- Ditolak; suhu tetap dipakai sebagai bagian dari paket.

### Satu profil global untuk semua model LM Studio (chunk + prompt ringkas)
- Pro: tanpa deteksi nama.
- Kontra: model besar (Gemma, Qwen 27B) justru mendapat manfaat dari glosarium dan aturan gender penuh di system prompt.
- Ditolak; profil hanya untuk Index-Translate. Suhu 0 dan chunk 2500 berlaku untuk seluruh LM Studio (lihat Negative).

### Mengandalkan `chat_template_kwargs` saja untuk mematikan thinking
- Pro: nol konfigurasi manual.
- Kontra: terbukti diabaikan LM Studio (isu #1559, #1773, #1990).
- Ditolak sebagai satu-satunya mekanisme; dipertahankan untuk backend yang menghormatinya. Alternatif endpoint native `/api/v1/chat` dengan `"reasoning": "off"` ditunda karena format request berbeda dari yang dipakai adapter.

### Menerima URL gambar dan mengunduhnya di server
- Pro: klien lebih sederhana.
- Kontra: membuka SSRF dan perlu validasi egress (ADR-126).
- Ditolak; hanya data URL.

### Memakai 9B Q2_K agar tetap "9B"
- Pro: muat nominal (3.91 GB).
- Kontra: README menyebut "significant quality loss", tetap tidak muat dengan KV cache + mmproj di 4 GB.
- Ditolak; rekomendasi untuk perangkat ini 2B Q8_0.

## Consequences

### Positive
- Model 2B menerima persis bentuk prompt yang dilatihkan, per chunk pendek, pada suhu 0, tanpa thinking: terjemahan teks dan gambar terverifikasi live (`index-translate-2b`, Q8_0 + mmproj-f16; teks dan gambar masing-masing sekitar 3 detik).
- Glosarium lorebook tetap bekerja untuk Index-Translate lewat format yang dilatihkan model, hanya untuk istilah yang relevan.
- `/translate` tidak lagi mengirim bab penuh ke model kecil.
- Terjemahan gambar tersedia tanpa OCR eksternal dan tanpa vektor SSRF baru.
- Provider lain (OpenAI, Gemini, OpenRouter) tidak berubah: suhu 0.3, tanpa chunking.

### Negative / Residual
- **Belum diuji pada bab novel nyata.** Bukti perilaku hanya dari tes unit, provider tiruan, dan dua uji live singkat (satu kalimat Mandarin; satu gambar sintetis bersih). Apakah gejala membeo prompt benar-benar hilang pada 2B belum dibuktikan.
- **Suhu 0 dan chunk 2500 berlaku untuk semua model LM Studio**, bukan hanya Index-Translate. Model lain yang dijalankan lewat LM Studio ikut terkena (mis. Gemma, Qwen); nilai ini bisa perlu dibuat per model.
- **Konteks antar-chunk tidak dibagi.** Chunk ke-2 dan seterusnya tidak melihat isi chunk sebelumnya; konsistensi nama bergantung pada glosarium. Penggabungan memakai `\n\n` sehingga jarak paragraf bisa berbeda dari sumber.
- **Tidak ada deteksi echo per chunk.** Chunk yang membeo prompt atau kosong tetap digabung; pemeriksaan fidelity baru berjalan setelah penggabungan.
- **Informasi gender dan catatan glosarium tidak terkirim** ke Index-Translate (format resmi hanya `asal→terjemahan`). Aturan pronomina berbasis gender (ADR-109/110) tidak berlaku pada jalur ini.
- Deteksi bergantung pada nama model memuat `index-translate`; alias LM Studio lain (mis. `penerjemah-kecil`) mengembalikan perilaku lama tanpa peringatan.
- Mematikan thinking di LM Studio adalah langkah manual; bila terlupa, model menulis `reasoning_content` dan bisa menghabiskan `max_tokens`.
- Timeout klien 300 detik per request; pada 9B (~6 token/detik) satu chunk 2500 karakter dapat mendekati batas itu.
- Endpoint gambar belum punya antarmuka frontend dan baru diuji dengan satu gambar bersih; tangkapan layar komik atau papan jalan nyata belum dicoba. Seluruh body JSON dibaca sebelum ukuran divalidasi (pola yang sama dengan endpoint lain).
- Cakupan tes: jalur `/translate` dan `/translate/image` teruji lewat router; **jalur worker batch belum punya tes khusus** untuk cabang Index-Translate.

## References
- `backend/services/ai/index_translate.py`, `backend/services/ai/chunking.py`, `backend/services/ai/lm_studio.py`, `backend/services/ai/base.py`
- `backend/services/background_translator.py`, `backend/routers/translate.py`, `backend/routers/image_translate.py`, `backend/main.py`
- Tes: `backend/tests/test_services/test_chunked_provider.py`, `test_translation_temperature.py`, `test_index_translate_profile.py`, `test_index_translate_image.py`, `backend/tests/test_routers/test_translate_index_profile.py`, `test_translate_image.py`
- Commit `e158ca5`, `3f54f8d`
- ADR-126 (SSRF/egress), ADR-128 (polish judul Index-Translate, memakai builder yang sama), ADR-029 (multi-provider)
- Klien dan template resmi: `github.com/bilibili/Index-Translate` (`inference/llm/translate.py`, `docs/image_translate.md`)
- LM Studio bug tracker: lmstudio-ai/lmstudio-bug-tracker #1559, #1773, #1990
