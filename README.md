# 🌌 translator-web
> **Privacy-focused web novel reader and translator powered by local AI.**

[![Project Status](https://img.shields.io/badge/status-stable-greenviolet?style=flat-square)](docs/Handoff.md)
[![Tech Stack](https://img.shields.io/badge/stack-React%20%7C%20FastAPI%20%7C%20SQLite-blue?style=flat-square)](#tech-stack)
[![AI Engine](https://img.shields.io/badge/AI%20Engine-LM%20Studio-orange?style=flat-square)](https://lmstudio.ai/)

A self-hosted web application built for reading and translating web novels with complete privacy. By integrating with **LM Studio**, the translation process happens entirely on your local machine, ensuring no data ever leaves your network.

---

## 🚀 Key Features

### 🧠 Context-Aware Engine
A sophisticated translation pipeline that maintains consistency across thousands of chapters:
- **Usage-Based Glossary**: Automatically identifies and injects the top 50 most relevant terms into the AI prompt to optimize token usage and accuracy.
- **Translation Ethics**: Enforces strict rules for honorifics, character names, and world-building terminology to prevent generic dictionary errors.
- **Auto-Discovery**: Automatically extracts "Translator Notes" from AI output and saves new terms directly to the database.

### 📖 Premium Reading Interface
- **Glassmorphism Design**: A clean, modern interface optimized for long reading sessions.
- **Mobile-First**: Fully responsive design that feels like a native app on iOS and Android.
- **Background Persistence**: Translation tasks continue in the background even if you close the browser tab.
- **Smart Prefetching**: Predicts your reading progress and translates the next chapter automatically.

### 📥 Content Management
- **Universal Scraper**: Clean extraction of novel content from URLs, converting them into readable Markdown.
- **EPUB Support**: Upload your own EPUB library and organize it into chapters automatically.

---

## 🛠️ Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | React 19, Vite, TailwindCSS v4 |
| **Backend** | Python 3.11, FastAPI |
| **Database** | SQLite with SQLAlchemy ORM |
| **AI Integration** | LM Studio (OpenAI-compatible API) |
| **Processing** | Crawl4AI (Scraping), EbookLib (EPUB) |

---

## 💻 Getting Started

### Prerequisites
- **Node.js** v20+
- **Python** v3.11+
- **[LM Studio](https://lmstudio.ai/)** running on port 1234

### 1. Backend Installation
```bash
cd backend
python -m venv venv
source venv/bin/activate  # venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

### 2. Frontend Installation
```bash
npm install
npm run dev
```
Access the application at `http://localhost:5173`.

---

## 📂 Documentation

For deeper technical details, refer to the following documents:
- [Implementation Plan](docs/implementation_plan.md) — Feature roadmap and progress.
- [Architectural Decisions](docs/decisions/) — Deep dives into why certain patterns were used.
- [Handoff Guide](docs/Handoff.md) — Technical overview for developers.

---

## 🛡️ Privacy
This project is built on the principle of **absolute privacy**. All novel data, reading history, and AI processing remain on your local hardware. No external APIs (other than your own LM Studio instance) are required.

---
*Developed for a better reading experience.*
