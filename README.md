# AI Translator Web

> Self-hosted web app untuk membaca dan menerjemahkan web novel & EPUB menggunakan AI lokal (LM Studio). Klon fungsional dari app.readomni.com.

## Fitur

- 🌐 **Web Scraping** — Paste URL → konten otomatis bersih menjadi Markdown
- 📚 **EPUB Management** — Upload EPUB → otomatis dipecah per chapter
- 🤖 **AI Translation** — Terhubung ke LM Studio lokal (privacy-first)
- 📖 **Lorebook / Context Library** — Simpan nama karakter & istilah per buku agar terjemahan konsisten
- 📱 **Mobile-first** — Dioptimalkan untuk dibaca di HP

## Tech Stack

| Layer | Teknologi |
|:---|:---|
| Frontend | React 19 + Vite + TailwindCSS v4 |
| Backend | Python 3.11 + FastAPI |
| Scraping | Crawl4AI |
| EPUB | EbookLib |
| Database | SQLite |
| AI Engine | LM Studio (OpenAI-compatible API) |

## Cara Menjalankan

### Prerequisites
- Node.js 20+
- Python 3.11+
- [LM Studio](https://lmstudio.ai/) (running di port 1234)

### Frontend
```bash
npm install
npm run dev
```
Buka `http://localhost:5173`

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```
API docs tersedia di `http://localhost:8000/docs`

## Dokumentasi

| File | Isi |
|:---|:---|
| [`docs/implementation_plan.md`](docs/implementation_plan.md) | Rencana implementasi lengkap per task (**baca ini dulu**) |
| [`docs/SDLC.md`](docs/SDLC.md) | Software Development Life Cycle overview |
| [`docs/style.md`](docs/style.md) | Design tokens, warna, dan komponen UI |
| [`docs/Handoff.md`](docs/Handoff.md) | Status terkini & panduan untuk developer/agent berikutnya |

## Status

**Phase 1 — Foundation** (sedang berjalan)

Lihat [`docs/implementation_plan.md`](docs/implementation_plan.md) untuk tracking progress task per task.
