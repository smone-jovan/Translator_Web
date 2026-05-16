# Handoff Document — AI Translator Web

> **Terakhir diperbarui:** 16 Mei 2026  
> **Status:** Phase 2 — Polish & Feature Integration  
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
│   ├── pages/                # TranslatePage, LibraryPage, ContextLibraryPage, SettingsPage
│   ├── App.tsx               # Router utama
│   └── index.css             # Design System tokens (ReadOmni style glassmorphism)
├── docs/
│   ├── implementation_plan.md  # Tracker tugas
│   ├── SDLC.md                 # Overview lifecycle
│   ├── style.md                # Design tokens & component specs
│   ├── Configuration_setting.md# Panduan integrasi LM Studio
│   └── Handoff.md              # ← File ini
├── backend/                  # Backend Python FastAPI
│   ├── routers/              # scrape.py, epub.py, translate.py, threads.py, lorebook.py
│   ├── database.py           # Setup SQLite
│   └── main.py               # Entry point
```

---

## Status Saat Ini

Semua fondasi utama **sudah selesai diimplementasikan**.

| Komponen | Status | Catatan |
|:---|:---|:---|
| Frontend & UI Shell | ✅ Selesai | Komponen dipecah modular. Menggunakan UI Glassmorphism. Mobile-friendly (Responsive dengan hamburger menu). |
| Backend FastAPI + SQLite | ✅ Selesai | Berjalan normal di port 8000. |
| Web Scraping (Crawl4AI) | ✅ Selesai | Route `/api/scrape` aktif. |
| EPUB Parser | ✅ Selesai | Route `/api/upload-epub` aktif. Tombol upload sudah diperjelas dan *Chapter Slider/Selector* sudah ditambahkan di halaman Translate. |
| LM Studio Integration | ✅ Selesai | Pengaturan terintegrasi via `SettingsPage`. Konfigurasi disimpan di `localStorage`. Streaming endpoint aktif. |
| Lorebook CRUD | ✅ Selesai | Halaman `ContextLibraryPage` untuk manajemen kamus karakter aktif. |

### UI/UX Fixes yang Sudah Dilakukan:
1. **EPUB Upload Link:** Tautan teks kecil telah diubah menjadi tombol yang jelas (dengan icon) untuk mempermudah upload EPUB.
2. **Chapter Slider:** Slider (previous/next selector) telah ditambahkan di panel "Original" halaman Translate untuk berpindah chapter hasil parsing EPUB.
3. **Mobile Responsiveness:** Tampilan sudah diuji dan dipastikan menumpuk vertikal dengan baik (*stacking*) dan aman digunakan pada ukuran layar mobile (e.g., iPhone X).
4. **LM Studio Form:** Terhubung secara mulus di halaman "Settings".

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
# Pastikan virtual environment aktif
uvicorn main:app --reload
# Buka http://localhost:8000/docs untuk Swagger UI
```

### LM Studio (harus running sebelum backend)
- Buka LM Studio → Load model yang diinginkan.
- Start Local Server di port `1234` (atau sesuai konfigurasi di tab Settings).
- Pastikan setting *Cross-Origin-Resource-Sharing (CORS)* di LM Studio dalam keadaan "ON".

---

## Langkah Selanjutnya (Agent/Human)

- Uji coba penerjemahan secara end-to-end (buka URL / upload EPUB -> terjemahkan dengan model LM Studio aktif).
- Evaluasi kualitas parsing `Crawl4AI` dan `EbookLib`.
- Jika perlu, tambahkan view khusus untuk membaca (`Reader View`) yang lebih leluasa dari halaman Translate.

---

## Dependencies Eksternal

| Tool | Versi | Fungsi |
|:---|:---|:---|
| Node.js | 20+ | Frontend runtime |
| Python | 3.11+ | Backend runtime |
| LM Studio | Latest | Local AI engine |
| Crawl4AI | Latest | Web scraping |
| EbookLib | 0.18+ | EPUB parsing |

