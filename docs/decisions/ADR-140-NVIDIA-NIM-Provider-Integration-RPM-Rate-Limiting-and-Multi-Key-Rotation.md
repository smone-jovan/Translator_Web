# ADR-140: NVIDIA NIM Provider Integration, RPM Rate Limiting & Multi-Key Quota Rotation

## Status
Accepted (diimplementasikan dan diverifikasi via unit test & live smoke test, 2026-11-03).

## Date
2026-11-03

## Context
ReadOmni AI mendukung berbagai provider LLM (Gemini, OpenRouter, OpenAI, Groq, dan LM Studio lokal). Dalam pengujian performa translasi bahasa Indonesia, platform NVIDIA NIM (`integrate.api.nvidia.com`) menawarkan kombinasi model yang sangat efisien untuk penerjemahan web novel:
1. **`nvidia/nemotron-3.5-bolt-e4b`**: Kecepatan inferensi tinggi, latensi rendah, hemat token, dan menghasilkan terjemahan Bahasa Indonesia yang koheren.
2. **`nvidia/riva-translate-4b-instruct-v2`**: Model khusus mesin penerjemah (*machine translation*).
3. **`mistralai/mistral-large-4-1t-a52b`**: Model penalaran mendalam (*reasoning*) untuk idiom sastra yang kompleks.

Namun, mengintegrasikan NVIDIA NIM menghadirkan tantangan teknis khusus:
- **Rate Limit & Throttling (RPM)**: Tier pengembang dan free-tier memberlakukan batas rate limit berkisar ~20 hingga 40 RPM serta batas kuota harian.
- **Variasi Format Header 429**: Gateway reverse proxy upstream NVIDIA dapat mengembalikan nilai `x-ratelimit-reset` dalam format Unix epoch timestamp (detik atau milidetik), bukan durasi relatif. Implementasi naif yang membaca nilai numerik epoch secara mentah akan menghasilkan *delay stall* puluhan tahun (~55 tahun).
- **Invarian Keamanan ADR-126**: API key NVIDIA (`nvapi-...`) tidak boleh dikirimkan ke sembarang host jika pengguna atau klien memasukkan `base_url` kustom.
- **Invarian Multi-Tenancy Compound Key (ADR-115, ADR-117, ADR-118)**: Pengaturan kredensial dan model harus tersinkronisasi bersih antara `main.db` dan `ghost.db` tanpa membocorkan state antar-workspace.
- **Rotasi Multi-Key pada Background Translator**: Jika sebuah key mencapai batas kuota harian (*daily quota exhausted*), background worker harus memutar key (*round-robin key rotation*) alih-alih membatalkan seluruh antrean translasi buku.

---

## Decisions

### 1. Adapter AI Resmi (`backend/services/ai/nvidia.py`)
Membuat kelas `NvidiaAdapter(BaseAIProviderAdapter)` yang mengimplementasikan komunikasi REST berbasis OpenAI-compatible:
- **`chat_completion` & `stream_chat`**: Mengirim payload standar JSON ke `/v1/chat/completions` dengan streaming SSE.
- **Ekstraksi Reasoning `<think>`**: Model seperti `mistral-large` mengalirkan penalaran di `reasoning` atau `reasoning_content`. Adapter membungkusnya dalam tag `<think>\n...\n</think>` agar UI dapat merender atau menyembunyikan proses berpikir sesuai preferensi pengguna.
- **Proteksi Null-Safety**: Menangani chunk streaming kosong `{"choices": []}` dan delta null secara defensif agar tidak memicu `IndexError` atau `AttributeError`.
- **Token Ceiling Clamping**: Membatasi `max_tokens` maksimal 4.096 untuk model Riva dan Nemotron, serta 8.192 untuk model umum guna menghindari halusinasi berlebih.

### 2. Allowlist Host & Validasi URL (Kepatuhan ADR-126)
Di `backend/services/ai/settings.py`:
- Menambahkan host resmi:
  ```python
  OFFICIAL_PROVIDER_HOSTS["nvidia"] = "integrate.api.nvidia.com"
  OFFICIAL_PROVIDER_URLS["nvidia"] = "https://integrate.api.nvidia.com/v1"
  ```
- `is_trusted_provider_url("nvidia", url)` memvalidasi bahwa skema wajib `https`, port standar (443), dan hostname hasil parsing adalah `integrate.api.nvidia.com`.
- Kunci `NVIDIA_API_KEY` ditolak secara otomatis jika `base_url` mengarah ke host tidak tepercaya.

### 3. Penanganan RPM Rate Limiting & Epoch Timestamp Anti-Stall
Implementasi `_extract_retry_delay(headers, error_body)` pada `NvidiaAdapter`:
- **Epoch Timestamp Normalization**: Jika nilai header numerik `val > 1_000_000_000` (atau `> 1_000_000_000_000` untuk milidetik), adapter menguranginya dengan waktu saat ini (`time.time()`) untuk mendapatkan durasi jeda yang sebenarnya.
- **RFC 7231 HTTP-Date Parsing**: Menggunakan `email.utils.parsedate_to_datetime` untuk mem-parsing string tanggal HTTP jika dikembalikan oleh proxy.
- **Ekstraksi Tag Kategori Kuota**: Fungsi `_extract_quota_tag(status_code, body)` mendeteksi kata kunci `"quota"` atau `"exhausted"` dan menambahkan tag kategoris aman `[quota exhausted]` tanpa melanggar privasi body error upstream.
- **Pola Retryable Error**: Menambahkan token `quota` dan `exhausted` pada `_is_retryable_error` di `background_translator.py` agar translasi bab otomatis memicu rotasi key alih-alih melempar error fatal.

### 4. Skema Database & Multi-Key Secret Management
Di `backend/database.py` dan `backend/services/ai/secrets.py`:
- Menambahkan kolom berikut pada `GlobalSetting`:
  - `nvidia_model: Mapped[str] = mapped_column(String(200), default="nvidia/nemotron-3.5-bolt-e4b")`
  - `nvidia_api_key: Mapped[Optional[str]] = mapped_column(String(500), default="")`
  - `nvidia_api_keys: Mapped[Optional[str]] = mapped_column(Text, default="[]")`
  - `nvidia_active_key_index: Mapped[int] = mapped_column(default=0)`
- Migrasi otomatis schema pada `_migrate_engine`.
- Mendaftarkan kolom NVIDIA pada `_SHARED_SETTINGS_MAIN_TO_GHOST` untuk menjaga paritas antara database utama dan workspace ghost.
- Menambahkan dukungan variabel lingkungan `.env` fallback (`NVIDIA_API_KEY`) dan fungsi masking kunci (`mask_secret`).

### 5. Fleksibilitas Model Custom (Namespace Passthrough)
Di `backend/services/ai/factory.py` dan `backend/services/ai/settings.py`:
- Resolusi model NVIDIA mendukung namespace `org/model` (seperti `deepseek-ai/deepseek-r1` atau `meta/llama-3.3-70b-instruct`) di samping preset resmi NVIDIA, sehingga pengguna dapat memasang model katalog NVIDIA NIM mana pun tanpa dibatasi whitelist kaku.

### 6. Integrasi Frontend UI
- **`src/pages/SettingsPage.tsx`**: Kartu penyedia layanan NVIDIA NIM dengan input key ganda/tunggal, preset dropdown (`nvidia/nemotron-3.5-bolt-e4b`, `nvidia/riva-translate-4b-instruct-v2`, `mistralai/mistral-large-4-1t-a52b`), tombol tes koneksi API, dan field override model kustom.
- **`src/pages/TranslatePage.tsx`**: Selector model otomatis tersinkronisasi saat memilih provider NVIDIA NIM.
- **`src/components/BulkTranslateModal.tsx`**: Opsi provider dan badge NVIDIA NIM pada dialog penerjemahan batch novel.
- **`src/pages/ReaderPage.tsx`**: Resolusi nama model fallback saat membaca bab.

---

## Consequences

### Positif:
1. **Pilihan Provider Cepat & Hemat**: Pengguna mendapatkan akses ke model translasi berkualitas tinggi dengan latensi sangat rendah via chip GPU/LPU NVIDIA.
2. **Kekebalan terhadap Rate Limit Bug**: Algoritma backoff kebal terhadap bug delay epoch timestamp dan mampu menangani jeda 429 secara transparan.
3. **Ketahanan Translasi Massal**: Fitur multi-key rotasi memungkinkan pengguna menggabungkan beberapa akun free-tier untuk melipatgandakan throughput harian tanpa interupsi.
4. **Kepatuhan Invarian Arsitektur**: Tidak ada dependensi eksternal baru (`package.json` dan `requirements.txt` tidak berubah). Kualitas kode terbukti 100% lulus uji tipe TypeScript (`strict: true`) dan uji unit backend.

### Keterbatasan & Mitigasi:
- *Model Availability*: Tidak semua model di katalog NVIDIA terbuka untuk akun tier gratis. Sistem mengantisipasi ini dengan menyediakan preset model yang telah terverifikasi aktif (`nemotron-3.5-bolt-e4b`, `riva-translate-4b-instruct-v2`, `mistral-large-4-1t-a52b`) dan validasi endpoint tes koneksi di halaman pengaturan.
