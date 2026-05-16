# 🌌 AI Translator Web
> **Premium, context-aware web novel reader & translator powered by local AI.**

[![Status](https://img.shields.io/badge/Status-Phase%208%20(Stable)-blueviolet?style=for-the-badge)](docs/Handoff.md)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Tech Stack](https://img.shields.io/badge/Stack-React%20%7C%20FastAPI%20%7C%20SQLite-blue?style=for-the-badge)](#tech-stack)

AI Translator Web adalah aplikasi *self-hosted* yang dirancang khusus untuk pecinta web novel. Aplikasi ini mengkloning pengalaman premium dari **ReadOmni**, mengintegrasikan **Local AI (LM Studio)** untuk menjaga privasi, dan menggunakan **Context Engine** cerdas untuk menjamin konsistensi terjemahan sepanjang ribuan bab.

---

## ✨ Fitur Unggulan

### 🧠 Smart Context Engine (Phase 8)
Sistem translasi yang tidak sekadar menerjemahkan kata demi kata. Ia memahami dunia novel Anda:
- **Usage-Based Glossary**: Hanya 50 istilah paling relevan yang dikirim ke AI berdasarkan deteksi teks otomatis.
- **Strict Translation Ethics**: Menjamin konsistensi honorifik, nama karakter, dan istilah *world-building* (seperti teknik kultivasi atau artefak).
- **Auto-Maintenance**: Glossary membersihkan dirinya sendiri secara otomatis untuk menjaga efisiensi token.

### 📖 Seamless Reading Experience
- **Glassmorphism UI**: Antarmuka modern yang transparan, bersih, dan memanjakan mata.
- **Flicker Protection**: Perpindahan bab yang mulus tanpa kedipan putih (flash).
- **Persistent Translation**: AI terus bekerja di background meskipun tab ditutup.
- **Auto-Prefetch**: Bab selanjutnya otomatis siap dibaca sebelum Anda selesai membaca bab saat ini.

### 🌐 Advanced Content Ingestion
- **One-Click Scraper**: Masukkan URL novel, dan sistem akan mengekstrak konten bersih (bebas iklan) menjadi Markdown.
- **EPUB Intelligence**: Upload file EPUB dan biarkan sistem memecahnya menjadi database bab yang terorganisir.

---

## 🛠️ Tech Stack

Aplikasi ini dibangun dengan teknologi modern untuk performa maksimal:

| Layer | Technology | Purpose |
|:---:|:---|:---|
| **Frontend** | React 19 + Vite | Ultra-fast UI dengan state management modern. |
| **Styling** | TailwindCSS v4 | Custom Glassmorphism design system. |
| **Backend** | Python 3.11 + FastAPI | Asynchronous processing untuk tugas background. |
| **AI Engine** | LM Studio (Local) | Local LLM inference via OpenAI-compatible API. |
| **Database** | SQLite + SQLAlchemy | Persistensi data ringan dan cepat. |
| **Parsing** | Crawl4AI + EbookLib | Ekstraksi konten dari web dan file EPUB. |

---

## 🚀 Memulai Cepat

### Prasyarat
- **Node.js** v20+ & **Python** v3.11+
- **[LM Studio](https://lmstudio.ai/)** terinstal dan berjalan (Default port: 1234)

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # atau venv\Scripts\activate di Windows
pip install -r requirements.txt
py -m uvicorn main:app --reload --port 8000 --host 0.0.0.0
```

### 2. Frontend Setup
```bash
npm install
npm run dev
```
Buka **http://localhost:5173** di browser Anda.

---

## 📂 Dokumentasi Proyek

Kami menjaga standar dokumentasi yang sangat tinggi untuk memastikan proyek ini mudah dikembangkan:

- 📑 **[Implementation Plan](docs/implementation_plan.md)**: Roadmap detail dan tracking progress fitur.
- 🤝 **[Handoff Guide](docs/Handoff.md)**: Status teknis terakhir dan panduan untuk developer.
- 🏗️ **[Architectural Decisions](docs/decisions/)**: Kumpulan ADR (Architecture Decision Records) yang menjelaskan *mengapa* sistem dibangun seperti ini.
- 🎨 **[Design Style Guide](docs/style.md)**: Panduan visual, warna, dan komponen UI.

---

## 🛡️ Keamanan & Privasi
Karena aplikasi ini berjalan sepenuhnya secara lokal (Self-hosted + Local LLM), **tidak ada data novel atau riwayat baca Anda yang dikirim ke server eksternal**. Anda memiliki kendali penuh atas data dan privasi Anda.

---
*Dibuat dengan ❤️ untuk komunitas Web Novel.*
