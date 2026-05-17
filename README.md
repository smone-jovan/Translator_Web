# 🌌 ReadOmni AI (Self-Hosted Novel Reader & Translator)
> **A premium, privacy-first web novel reader and batch translator powered by local AI.**

[![Project Status](https://img.shields.io/badge/status-Phase%2010%20Complete-success?style=for-the-badge&logo=github)](docs/Handoff.md)
[![Tech Stack](https://img.shields.io/badge/stack-React%2019%20%7C%20FastAPI%20%7C%20Tailwind%20v4-blue?style=for-the-badge)](#-tech-stack)
[![AI Engine](https://img.shields.io/badge/AI%20Engine-LM%20Studio%20(Local)-orange?style=for-the-badge&logo=openai)](https://lmstudio.ai/)
[![Database](https://img.shields.io/badge/Database-SQLite%20(WAL%20Mode)-lightgrey?style=for-the-badge&logo=sqlite)](backend/models.py)

**ReadOmni AI** is a premium, self-hosted web application built for reading, crawling, and translating web novels and local EPUB files with complete privacy. By integrating with local LLMs (via **LM Studio**), the entire translation pipeline runs on your local machine, ensuring no data ever leaves your network. 

---

## 🌟 Key Pillars & Features

### 🎨 1. Premium Visuals & Multi-Theme System
*   **Aesthetics First:** Exquisite glassmorphic interface inspired by `app.readomni.com` with smooth, organic micro-interactions and transitions.
*   **Dynamic Theme Presets:** Toggle instantly between **OLED Dark**, **Warm Sepia**, and the signature **Omni Preset** using visual selectors built fully on HSL CSS design tokens.
*   **Mobile-First Ergonomics:** Fully responsive layout with an elegant mobile bottom navigation bar and gesture-friendly reading layout for smartphones.

### ⚡ 2. Batch Translation Studio
*   **Studio Dashboard:** A dedicated command center to translate multiple chapters at once.
*   **Dual Processing Load:** 
    *   *Soft Load:* Safe sequential 1-by-1 processing for extreme GPU thermal safety.
    *   *Hard Load:* High-throughput bulk translation (3-20+ chapters simultaneously) for fast updates.
*   **Status Center:** Real-time visual tracking of batch queue progress and thread states.
*   **Mandatory Overwrite:** Enforces glossary updates immediately to rewrite and sync translated text whenever a term is modified.

### 🧠 3. Smart Context & Glossary Engine
*   **AI Extract First (Smart Extraction):** Recommends automatic term extraction before translation if the thread has < 40 glossary terms, ensuring translation consistency.
*   **Smart Scoping:** Automatic character and term scanning starts precisely from the user's `last_read` chapter bookmark.
*   **Usage-Based Glossary Routing:** Automatically tracks and ranks the top 50 most relevant terms (`usage_count` & `last_used_at`) and feeds them into the system prompt to avoid token bloat.
*   **Terminology Auto-Discovery:** Parses "Translator Notes" and LLM suggestions at the end of chapters to auto-save new glossary terms directly.

### 📚 4. Library & Premium Book Export
*   **Progressive Bookmarking:** Real-time reading history tracking, custom progress banners, and "Last Read" indicators on the chapter index.
*   **EPUB & TXT Compiler:** Compile translated chapters into beautifully formatted files with:
    *   *Custom Cover Upload:* Embed cover images directly from your system.
    *   *Curation & Metadata:* Custom author and book title details.
    *   *Selective Compiling:* Select all or filter to compile translated chapters only.

### ⚙️ 5. Server-Side Configuration Sync
*   **Unified Multi-Device Sync:** Transitioned from volatile browser `localStorage` to SQLite-backed `global_settings` table, synchronizing settings instantly between desktop and mobile devices on the same network.
*   **Sequential Background Prefetching:** Configure a smart prefetching range slider (1-5 chapters ahead) to sequentially pre-translate the upcoming chapters in the background while you read.

### 🛡️ 6. Stability & GPU Guardrails
*   **Throttling Mitigation:** Title translations chunked into blocks of 50 with a `1.0s` delay to prevent local LLM server timeout or freeze.
*   **300s Heavy-Duty Timeout:** Elevated HTTP connections to support complex deep-context translations without abrupt closures.
*   **AbortController Integration:** Automatically cancels past streaming threads when rapidly skipping through chapters to avoid VRAM clashing.

---

## 🛠️ Tech Stack & Dependencies

*   **Frontend:** React 19, Vite, TailwindCSS v4 (Glassmorphic theme presets).
*   **Backend:** Python 3.11, FastAPI (Asynchronous endpoints + background workers).
*   **Database:** SQLite with SQLAlchemy ORM (WAL mode enabled for robust read/write operations).
*   **Scraping Engine:** Crawl4AI (LLM-friendly, stealth web scraping).
*   **EPUB Core:** EbookLib & BeautifulSoup4 (Accurate file parsing & compilation).
*   **AI Backend:** LM Studio (OpenAI-compatible local server at `http://localhost:1234`).

---

## 💻 Getting Started (Windows Setup)

### 📋 Prerequisites
*   **Node.js** v20+
*   **Python** v3.11+
*   **LM Studio** installed and running on port `1234`. Make sure to enable local server in LM Studio.

### 1. Backend Installation & Start
```powershell
# Navigate to backend directory
cd backend

# Create and activate Python virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start backend server bound to local IP
py -m uvicorn main:app --reload --port 8000 --host 0.0.0.0
```

### 2. Frontend Installation & Start
```powershell
# In the project root directory
npm install

# Start Vite dev server
npm run dev
```

Open `http://localhost:5173` on your laptop, or use your laptop's local IP (e.g. `http://192.168.1.50:5173`) to read and translate on your iPhone/Android!

---

## 📂 Project Architecture

```text
├── backend/
│   ├── database.py             # Database connection & engine setup
│   ├── main.py                 # FastAPI application & router mounting
│   ├── models.py               # SQLAlchemy SQLite schemas (Threads, Chapters, Lorebook, Settings)
│   ├── routers/
│   │   ├── batch.py            # Batch translation endpoints
│   │   ├── epub.py             # EPUB uploading and parsing
│   │   ├── export.py           # Premium book compiler service
│   │   ├── lorebook.py         # Thread-specific glossary CRUD
│   │   ├── scrape.py           # URL crawling endpoints
│   │   └── settings.py         # Server-side persistent settings sync
│   └── services/
│       ├── background_translator.py  # Prefetcher, title translating & batch engine
│       ├── context_engine.py         # AI extraction, prompts, usage-tracking & lorebook injection
│       └── epub_exporter.py          # EPUB builder and metadata packager
├── src/
│   ├── components/             # Reusable UI controls (Sidebar, ChapterList, ExportModal, dsb.)
│   ├── pages/
│   │   ├── BatchStudioPage.tsx # Batch Translation Studio workspace
│   │   ├── LibraryPage.tsx     # Thread collection & Book builder interface
│   │   ├── ReaderPage.tsx      # Dual-pane immersive reading environment
│   │   └── SettingsPage.tsx    # Persistent system configurations
│   ├── index.css               # Central stylesheet & HSL CSS theme design system
│   └── main.tsx                # React entry point
└── docs/                       # Technical documentations & Architectural Decisions (ADRs)
```

---

## 📂 Documentation & ADRs
For detailed insights into the technical architecture, read our official guides:
*   [docs/SDLC.md](docs/SDLC.md) — The 10-phase software development lifecycle documentation.
*   [docs/implementation_plan.md](docs/implementation_plan.md) — Exact task definitions and acceptance criteria from Task 1 to 24.
*   [docs/Handoff.md](docs/Handoff.md) — The main developer handoff guide and future roadmap suggestions.
*   [docs/decisions/](docs/decisions/) — Directory containing all 15 accepted Architectural Decision Records (ADRs).

---

## 🛡️ License & Privacy
This application is **100% self-hosted**. All of your novels, reading bookmarks, glossary contexts, and translations remain offline and local to your system. No external analytical APIs are used. 

*Designed to bring premium reading directly to your own self-hosted terminal.*
