# Batch Translation Queue for Local LLM (LM Studio)

## Problem Statement
Bagaimana kita bisa membangun antrian terjemahan yang memproses *chapter* secara berurutan (satu per satu) per *Novel Thread*, sehingga 100% aman dijalankan semalaman di hardware lokal (LM Studio) tanpa campur tangan pengguna?

## Recommended Direction
Membangun **Single-Worker Background Queue** di *backend*. Pengguna dapat "mengantrikan" beberapa *Novel Thread* ke sistem. *Worker* ini berjalan di latar belakang dan akan menyelesaikan *Thread A* sampai tuntas (chapter per chapter), sebelum berpindah ke *Thread B*. Progres/status selalu di-update ke dalam `app.db` secara *real-time*.

## Key Assumptions to Validate (Potensi Bahaya Tersembunyi)
- [ ] **LM Studio tidak akan *hang* abadi:** Saat ditinggal semalaman, API lokal kadang bisa tersendat tanpa merespons. **Solusi:** Kita wajib memasang *hard timeout* (misal: maksimal 5 menit/chapter). Jika gagal, sistem mencatat *error* dan lanjut ke *chapter* berikutnya, tidak boleh *stuck* selamanya.
- [ ] **Database tidak *locked*:** SQLite rawan *error* jika banyak jalur mencoba menulis sekaligus. **Solusi:** Hanya si *worker* satu ini yang diizinkan mengupdate status *"done"* ke dalam database.

## MVP Scope (Yang Akan Dibuat)
- *Endpoint* khusus untuk "Masukkan Thread ke Antrian".
- *Background task/thread* yang berjalan otomatis di dalam *backend* Python.
- Proses murni sekuensial (1 Chapter aktif di waktu yang sama di seluruh aplikasi).
- Database menyimpan status per chapter: `queued`, `translating`, `done`, `error`.

## Not Doing (and Why)
- **Tidak ada Parallel Processing:** (Saat ini). Akan mematikan/men-crash LM Studio. Mode paralel (seperti `ThreadPoolExecutor`) bisa dibuat terpisah nanti KHUSUS untuk *provider* berbayar seperti Gemini/OpenAI.
- **Tidak ada Celery / Redis:** Infrastruktur itu memakan RAM. RAM Anda lebih baik didedikasikan untuk LM Studio secara utuh.
- **Tidak ada UI Dashboard Antrian yang rumit:** Untuk *Minimum Viable Product* (MVP), cukup status sederhana di halaman *Thread* tanpa perlu halaman *dashboard* khusus pengelola tugas.

## Open Questions
- Jika sebuah *chapter* terkena *error* (timeout/putus), sistem akan menandai *error* dan langsung lanjut ke *chapter* berikutnya agar sisa antrian tetap jalan.
