# Handoff Document — AI Translator Web

> **Terakhir diperbarui:** 16 Mei 2026 (18:00)  
> **Status:** Phase 7 — Multi-Device Sync Complete  
> **Next Milestone:** Background Task Monitoring & Multi-User Scoping (Phase 8)  
> **Agent Mode:** ON

---

## Project Overview

Self-hosted web app untuk membaca dan menerjemahkan web novel & EPUB. Klon fungsional dari app.readomni.com, menggunakan LM Studio lokal sebagai mesin AI-nya. Dilengkapi fitur "Lorebook" untuk menjaga konsistensi nama karakter dan istilah per buku. UI/UX menggunakan Glassmorphism dan sepenuhnya mobile-friendly.

---

## Repository Structure

```
d:\code_xI\Translator_Web\
├── src/                      # Frontend React + TypeScript (Vite + Tailwind)
│   ├── components/           # Sidebar, Layout
│   ├── pages/                # TranslatePage, LibraryPage, ContextLibraryPage, SettingsPage, ReaderPage
│   ├── App.tsx               # Router utama
│   └── index.css             # Design System tokens (ReadOmni style glassmorphism)
├── docs/
│   ├── implementation_plan.md  # Tracker tugas
│   ├── SDLC.md                 # Overview lifecycle
│   ├── style.md                # Design tokens & component specs
│   ├── Configuration_setting.md# Panduan integrasi LM Studio
│   ├── decisions/              # ADRs (Architectural Decision Records)
│   └── Handoff.md              # ← File ini
├── backend/                  # Backend Python FastAPI
│   ├── routers/              # scrape.py, epub.py, translate.py, threads.py, lorebook.py
│   ├── database.py           # Setup SQLite
│   └── main.py               # Entry point
```

---

## Status Saat Ini

Semua fondasi utama dan fitur persistensi tingkat lanjut **sudah selesai diimplementasikan**.

| Komponen | Status | Catatan |
|:---|:---|:---|
| Frontend & UI Shell | ✅ Selesai | Komponen dipecah modular. Menggunakan UI Glassmorphism. Mobile-friendly. |
| Reader Page | ✅ Selesai | Reading interface yang bersih dengan **Settings Overlay** terintegrasi (Font size, Theme, Re-translate). |
| Persistent Translation | ✅ Selesai | AI tetap bekerja di background meskipun browser ditutup. Auto-resume saat user kembali ke chapter. |
| Backend persistence | ✅ Selesai | Menggunakan `FastAPI BackgroundTasks` + incremental saving ke SQLite (per 15-20 segmen). |
| Web Scraping (Crawl4AI) | ✅ Selesai | Route `/api/scrape` aktif. |
| EPUB Parser | ✅ Selesai | Route `/api/upload-epub` aktif. |
| LM Studio Integration | ✅ Selesai | Pengaturan terintegrasi via `SettingsPage`. Streaming SSE aktif. |
| Lorebook CRUD | ✅ Selesai | Halaman `ContextLibraryPage` aktif. |
| Bulk Title Translator | ✅ Selesai | Translasi judul bab secara massal (Batch LLM) permanen di DB. |
| Server-Side Sync | ✅ Selesai | Sinkronisasi LM Studio settings & Zero-config mobile access. |

### Major Architectural Shifts:
1. **Background Translation**: Mengalihkan proses LLM dari *request-scoped* menjadi *shielded background task*. Ini menjamin data tidak hilang jika koneksi internet/browser terputus.
2. **Settings Overlay**: Menghapus tombol-tombol yang berserakan di navbar dan mengonsolidasikannya ke dalam satu menu overlay (cog icon) di pojok kanan atas reader.
3. **SSE Synchronization**: Menggunakan antrean memori server-side untuk menyinkronkan output streaming AI ke multiple subscriber (jika tab dibuka di banyak tempat).
4. **Dual-Title Schema**: Memisahkan judul asli dan judul terjemahan di database untuk navigasi novel yang lebih baik tanpa merusak metadata asli.
5. **Server-Side Configuration**: Memindahkan setting LM Studio ke database dan menggunakan deteksi IP dinamis agar sinkron di HP (iPhone).

---

## Database Schema Update
- **Chapter Table**: Menambahkan kolom `translation_status` ('idle', 'processing', 'done', 'error') serta `title_original` dan `title_translated`. Menghapus kolom `title` lama.
- **Migration**: Script migrasi berada di `scratch/migrate_db.py`. Skema bersifat *non-destructive* (memindahkan data `title` lama ke `title_original`).

---

## Cara Menjalankan (Development)

### Frontend
```bash
cd d:\code_xI\Translator_Web
npm run dev
# Buka http://localhost:5173
```

### Backend
```bash
cd d:\code_xI\Translator_Web\backend
# Agar bisa diakses dari HP (iPhone) di jaringan yang sama:
py -m uvicorn main:app --reload --port 8000 --host 0.0.0.0
```

---

## Langkah Selanjutnya (Agent/Human)

- **Performance Benchmarking**: Menguji konkurensi jika menerjemahkan 10+ chapter sekaligus (LM Studio throttling).
- **Error Recovery**: Implementasi tombol "Force Stop" jika background task stuck.
- **EPUB Export**: Fitur untuk mendownload hasil terjemahan kembali menjadi format EPUB yang rapi.

---

## Dependencies Eksternal

| Tool | Versi | Fungsi |
|:---|:---|:---|
| Node.js | 20+ | Frontend runtime |
| Python | 3.11+ | Backend runtime |
| LM Studio | Latest | Local AI engine |
| Crawl4AI | Latest | Web scraping |
| EbookLib | 0.18+ | EPUB parsing |
