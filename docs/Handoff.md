# Handoff Document — AI Translator Web

> **Terakhir diperbarui:** 17 Mei 2026 (01:10)  
> **Status:** Phase 8 (Context Engine & Pipeline Ethics Complete)  
> **Next Milestone:** Error Recovery & EPUB Export (Phase 9)  
> **Agent Mode:** ON

---

## Project Overview

Self-hosted web app untuk membaca dan menerjemahkan web novel & EPUB. Klon fungsional dari app.readomni.com, menggunakan LM Studio lokal sebagai mesin AI-nya. Dilengkapi fitur "Lorebook" pintar yang membatasi context secara dinamis (Top 50 terms) dan sistem etika translasi yang ketat. UI/UX menggunakan Glassmorphism dan sepenuhnya mobile-friendly.

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
│   ├── services/             # background_translator.py, context_engine.py, ai_provider.py
│   ├── database.py           # Setup SQLite & Auto-Migration logic
│   └── main.py               # Entry point
```

---

## Status Saat Ini

Sistem translasi sekarang memiliki **kecerdasan kontekstual** dan **manajemen glossary otomatis**.

| Komponen | Status | Catatan |
|:---|:---|:---|
| Frontend & UI Shell | ✅ Selesai | Komponen dipecah modular. Menggunakan UI Glassmorphism. |
| Reader Page | ✅ Selesai | Reading interface bersih dengan Settings Overlay. |
| Persistent Translation | ✅ Selesai | AI tetap bekerja di background menggunakan FastAPI BackgroundTasks. |
| Context Engine | ✅ Selesai | Prompt dinamis dengan 4 aturan etika ketat (ADR-012). |
| Glossary Optimizer | ✅ Selesai | Limit 50 term per prompt (berdasarkan usage count). Auto-cleanup aktif. |
| Auto-Save Glossary | ✅ Selesai | Deteksi otomatis "Translator Notes" dari output AI dengan regex fleksibel. |
| Bulk Title Translator | ✅ Selesai | Stabil dengan sistem Chunking (50 titles). |

### Major Architectural Shifts:
1. **Context Engine (ADR-012)**: Pemisahan logika pembuatan prompt ke dalam service khusus yang menyuntikkan etika translasi (Context over Dictionary, World-building, etc.).
2. **Usage-Based Glossary**: Implementasi tracking `usage_count` dan `last_used_at` untuk memastikan hanya istilah paling relevan yang masuk ke context LLM.
3. **FastAPI BackgroundTasks**: Migrasi dari `asyncio.create_task` untuk menjamin stabilitas event loop pada proses translasi background.
4. **Auto-Migration Logic**: Penambahan mekanisme di `database.py` untuk secara otomatis melakukan `ALTER TABLE` saat ada kolom baru yang diperlukan.

---

## Database Schema Update
- **Chapter Table**: Kolom `translation_status` ('idle', 'processing', 'done', 'error'), `title_original`, dan `title_translated`.
- **LorebookEntry Table**: Menambahkan kolom `usage_count` (integer) dan `last_used_at` (datetime) untuk manajemen glossary cerdas.

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

- **Error Recovery UI**: Tombol "Force Stop" di UI jika background task terdeteksi stuck.
- **Enhanced EPUB Export**: Fitur untuk mendownload hasil terjemahan kembali menjadi format EPUB.
- **Character Clustering**: Logika untuk mendeteksi hubungan antar karakter secara otomatis dari teks.

---

## Dependencies Eksternal

| Tool | Versi | Fungsi |
|:---|:---|:---|
| Node.js | 20+ | Frontend runtime |
| Python | 3.11+ | Backend runtime |
| LM Studio | Latest | Local AI engine |
| Crawl4AI | Latest | Web scraping |
| EbookLib | 0.18+ | EPUB parsing |
| SQLAlchemy | 2.0+ | Database ORM |
