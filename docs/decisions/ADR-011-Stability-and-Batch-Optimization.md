# ADR-011: Stability and Batch Processing Optimization

## Status
Accepted

## Date
2026-05-16

## Context
Selama Phase 7 dan 8, ditemukan beberapa masalah stabilitas operasional:
1. **Batch Translation Failure**: Fitur "Infinite Polish" (batch title translation) sering gagal pada novel dengan jumlah bab besar (>100) karena *timeout* koneksi dan beban LLM yang terlalu berat dalam satu permintaan tunggal.
2. **Husky/Git Hook Interference**: Penggunaan Husky menyebabkan gangguan pada proses commit dan sering memicu kegagalan commit yang berujung pada kebingungan status codebase (seperti kejadian "rollback" yang tidak disengaja).
3. **UI Flickering**: Saat berganti bab dengan cepat, terjadi *race condition* antara konten terjemahan lama dan baru, menyebabkan tampilan "berkedip" (flickering).
4. **LM Studio Throttling**: Permintaan bertubi-tubi tanpa jeda menyebabkan LM Studio terkadang *hang* atau memberikan respon kosong.

## Decision
1. **Removal of Husky**: Menghapus Husky sepenuhnya dari proyek untuk menghilangkan hambatan saat commit dan memastikan kendali penuh pada riwayat Git.
2. **Title Translation Chunking**:
   - Membagi proses translasi judul menjadi *chunks* berukuran **50 judul** (dioptimalkan untuk konteks 8000 token).
   - Menambahkan jeda `asyncio.sleep(1.0)` antar *chunk* untuk memberi ruang bagi LM Studio.
3. **Extended Timeouts**: Meningkatkan `httpx` timeout di `AIProvider` dari 120 detik menjadi **300 detik** (5 menit) untuk mengakomodasi pemrosesan *batch* yang lama.
4. **Race Condition Prevention**: Mengimplementasikan `AbortController` di `ReaderPage.tsx` untuk membatalkan permintaan terjemahan sebelumnya jika user berpindah bab dengan cepat.
5. **Strict Glossary Parsing**: Menyempurnakan parser glosarium di `context_engine.py` untuk menangani format `Original → Translated (Note)` secara akurat agar database glosarium tetap bersih.

## Consequences
- **Stable Infinite Polish**: Fitur pemolesan judul kini sangat stabil bahkan untuk novel dengan 1000+ bab.
- **Smooth Commits**: Proses git kembali normal tanpa gangguan hook otomatis yang tidak perlu.
- **Zero Flickering**: Antarmuka pembaca lebih responsif dan tenang saat navigasi cepat.
- **Reliable AI Connectivity**: Dengan timeout yang lebih panjang, kegagalan koneksi saat beban tinggi (heavy batching) telah diminimalisir.
- **Improved Data Integrity**: Sinkronisasi *server-side* memastikan tidak ada data konfigurasi yang bertabrakan antar perangkat (iPhone/Desktop).
