# ReadOmni AI (Translator Web)

**Self-hosted AI-powered web novel reader & translator with complete privacy.**

[![Version](https://img.shields.io/badge/version-2.0.0-2DD4BF?style=flat-square)](#)
[![Build](https://img.shields.io/badge/build-passing-brightgreen?style=flat-square)](#)
[![Tests](https://img.shields.io/badge/tests-392%20passed-brightgreen?style=flat-square)](#contributing)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square&logo=python)](#)
[![React](https://img.shields.io/badge/react-19-61DAFB?style=flat-square&logo=react)](#)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](#license--attribution)

ReadOmni AI lets you read, crawl, and translate Chinese, Japanese, and Korean web novels using local or cloud AI — with zero data leaving your network unless you choose a cloud provider. Import EPUBs, scrape chapters with the Adaptive DOM engine, batch-translate with smart glossary locking, visualize character relationships, and export polished EPUBs — all managed from a self-hosted web dashboard and native dark-mode **Desktop Control Hub**.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License & Attribution](#license--attribution)

---

## Features

### Translation Engine & MTL Quality Guards
- **Multi-provider support** — Seamlessly switch between LM Studio (local offline), Google Gemini, OpenAI, and OpenRouter with strict model-leak guards
- **Adaptive source language guidelines** — Tailored translation rules for Chinese, Japanese, and Korean web novels with Indonesian honorifics and clitic (`-nya`, `-mu`, `-ku`) support
- **Quality / Fast mode** — Quality mode for cloud models (full glossary, character relationship matrix, style guide), Fast mode for local LLMs (locked terms priority, 10K token cap)
- **Auto-continue & partial recovery** — Preserves partial translated text on token limits (`finish_reason: "length"`) and automatically continues mid-sentence until complete
- **Fidelity & anti-hallucination guards** — Automated verification against raw source script leakage, multi-word N-gram phrase loops, AI conversational wrappers, inline bilingual notes, and CJK summarization drops
- **Single-pass glossary locking** — Protects markdown image URLs, prioritizes compound terms, and enforces case-sensitive single-syllable Pinyin collision prevention
- **Multi-key rotation** — Store multiple API keys per provider with automatic rotation and live rate-limit exhaustion telemetry

### Reading Experience
- **Glassmorphic UI** — 6 theme presets (Obsidian, OLED, Sepia, White, Omni, Black)
- **Mobile-first ergonomics** — Responsive bottom navigation with safe-area insets, directional scroll physics with hysteresis, pinch-to-zoom support, and quick TOC drawer triggers (`BAB X / Y`)
- **Instant SWR & adjacent prefetch** — Workspace-scoped chapter caching (`sessionStorage` + memory) with 100% cache hit on adjacent chapter background prefetching
- **Frame-accurate bookmark sync** — Exact scroll percentage saved per chapter and automatically reassigned to surviving chapters during EPUB/TXT cleanup
- **Illustrated novel support** — Thread-level image caching pipeline, resilient local image proxy, novel illustration gallery, and safe reader image rendering

### Library & Adaptive Scraper Engine
- **Adaptive DOM engine** — 3-tier resilient fetcher (`fetch_html_adaptive`) with structural/semantic fingerprinting, zero-shot prose density scoring, and thread-local Playwright fallback
- **Dedicated novel scrapers** — Novalpie dual-mode authenticated crawler (active Cloudflare Turnstile solver, resource shield, XHR JSON chapter capture), SFACG TOC/chapter scraper, and Novel Updates metadata scraper
- **Chained bulk web crawler** — Real-time SSE progress streaming for bulk chapter fetching and full TOC imports
- **Status filter tabs & smart sorting** — Segment library into All, Currently Reading, Unread, and Completed; sort by Recently Read, Recently Added, Reading Progress %, or Title A-Z
- **Fidelity management hub** — Audit chapter-level fidelity warnings, run selective repair, and reset truncated chapters
- **EPUB import/export & cover studio** — Extracts synopsis, cover, and illustrations on import; compresses custom covers (<100KB canvas engine); compiles clean EPUB/TXT books

### Context Studio & Workspace Security
- **3-Layer Context & Glossary Studio** — Full studio redesign managing Global Context, Thread Synopsis & Style Guide, and Lorebook entries (up to 1000 terms with bidirectional capacity enforcement and self-eviction protection)
- **Stratified AI extraction** — Multi-window chapter sampling (40%/30%/30%) with gender-aware character detection and existing glossary injection
- **Interactive 2D Relationship Graph** — Force-directed graph (`react-force-graph-2d`) and table view with full CRUD modal for managing character connections
- **Bilingual genre presets** — Instant English & Indonesian terminology presets for Cultivation (Xianxia/Xuanhuan), Wuxia, LitRPG/System, and Korean Hunter/Tower genres
- **Ghost Mode workspace isolation** — PIN-protected dual SQLite databases (`app.db` and `ghost.db`) with isolated frontend caches, SSE stream queues, and background tasks

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, TypeScript (Strict), Vite 8, TailwindCSS v4, Radix UI, MUI, Lucide |
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic |
| **Database** | Dual SQLite (`app.db` & `ghost.db` in WAL mode) |
| **AI Providers** | LM Studio (Local), Google Gemini, OpenAI, OpenRouter |
| **Scraping** | AdaptiveDOM, Playwright/Patchright Stealth, httpx, curl-cffi, BeautifulSoup4 |
| **EPUB & NLP** | EbookLib, pypinyin |
| **Launcher** | Python Tkinter Desktop Control Hub (Windows DWM Dark Mode) & CLI |
| **Testing** | pytest (392 backend tests, hermetic: no network needed), TypeScript strict typecheck & ESLint |

---

## Quick Start

### Prerequisites

- **Node.js** v20+
- **Python** 3.11+
- **AI Provider** (one of):
  - [LM Studio](https://lmstudio.ai/) running on port `1234` (free, local offline)
  - [Google AI Studio](https://aistudio.google.com/) API key (free tier available)
  - OpenAI API key (paid)
  - [OpenRouter](https://openrouter.ai/) API key (optional, access to DeepSeek, Claude, Llama, etc.)

### Option A: 1-Click Desktop Control Hub (Windows Recommended)

After installing dependencies once (`pip install -r backend/requirements.txt` and `npm install`), simply double-click **`start_app.bat`**:

```bat
:: Launches the native dark-mode Desktop Control Hub GUI (Zero-CMD via pythonw)
start_app.bat
```

The **Desktop Control Hub (`v2.0`)** provides:
- Real-time **Backend (`:8000`)** and **Frontend (`:5173`)** online status indicators and uptime counter
- One-click **Buka Aplikasi** (`http://localhost:5173`) and **Copy Link HP** (`http://<LAN_IP>:5173`) for mobile Wi-Fi reading
- Instant service controls (**Restart Semua**, **Restart Backend**, **Restart Frontend**, **Swagger API Docs**, **Buka Folder**)
- Built-in **🩺 Cek Sistem (Doctor)** diagnostics and a collapsible **Live Server Logs** drawer

For CLI or diagnostic modes:

```bash
python launcher.py --gui        # Launch Desktop Control Hub GUI
python launcher.py --cli        # Launch interactive terminal CLI dashboard
python launcher.py doctor       # Run read-only pre-flight system diagnostics
```

To allow smartphone access over local Wi-Fi on Windows, run **`setup_mobile_access.bat`** once as Administrator to configure Windows Firewall rules for ports `5173` and `8000`.

### Option B: Manual Terminal Setup

#### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
py -m uvicorn main:app --reload --port 8000 --host 0.0.0.0
```

#### 2. Frontend

```bash
npm install
npm run dev
```

Open `http://localhost:5173` on your laptop or `http://<your-lan-ip>:5173` on your phone.

---

## Configuration

### Environment Variables

Create `backend/.env` (gitignored, or copy from `backend/.env.example`):

```env
OPENAI_API_KEY=sk-your-key-here
GEMINI_API_KEY=AIzaSy-your-key-here
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

### Settings Page

All runtime settings are synchronized across devices via the SQLite `global_settings` table:

| Setting | Description |
|---------|-------------|
| **AI Provider** | LM Studio / OpenAI / Gemini / OpenRouter |
| **Model** | Provider-specific model selector (e.g., `gemini-2.5-flash`, `gemini-3-flash`, `gemma-4-31b-it`) |
| **Target Language** | Indonesian / English |
| **Translation Mode** | Quality (cloud, full glossary + relationships + style guide) / Fast (local, 10K cap) |
| **Token Safety Cap** | 7K / 15K / 22K / 30K / Off |
| **Glossary Limit** | 20 / 50 / 100 / 150 / 200 / 300 / 500 / 750 / 1000 terms per thread |
| **API Keys** | Multiple keys per provider with automatic rate-limit rotation |
| **Prefetch** | 1–5 chapters ahead, Soft (sequential) or Hard (concurrent) load mode |
| **Scraper Settings** | Browser concurrency (1–5 workers) & Novalpie authenticated session toggle |
| **Ghost Mode** | PIN-protected workspace switcher (`main` ↔ `ghost` isolated databases) |
| **Theme** | 6 glassmorphic presets (Obsidian, OLED, Sepia, White, Omni, Black) |

---

## Architecture

```text
Translator_Web/
├── launcher.py                 # v2.0 Desktop Control Hub GUI, CLI dashboard & Doctor diagnostics
├── start_app.bat               # Zero-console Windows launcher (pythonw GUI default)
├── setup_mobile_access.bat     # Windows Firewall helper for LAN mobile access
├── backend/
│   ├── main.py                 # FastAPI app entry, lifespan hooks & LAN CORS guard
│   ├── database.py             # Dual SQLite engines (app.db & ghost.db) & auto-migration
│   ├── data/
│   │   └── adaptive_selectors.json # Learned domain selectors for AdaptiveDOM
│   ├── routers/                # 16 API routers (threads, translate, batch, lorebook,
│   │                           #   context, relationships, scrape, toc, epub, export,
│   │                           #   polish, images, settings, system, tools, discovery)
│   ├── services/
│   │   ├── ai/                 # Provider adapters (Gemini, OpenAI, LM Studio, OpenRouter) & secrets
│   │   ├── scrapers/           # AdaptiveDOM, Novalpie Turnstile/XHR, SFACG, Novel Updates, Stealth
│   │   ├── background_translator.py  # Workspace-scoped batch engine & auto-continue
│   │   ├── context_engine.py   # Prompt builder, relationship injection & note stripping
│   │   ├── fidelity_checker.py # Script leakage, truncation & summarization verification
│   │   ├── glossary_lock.py    # Single-pass term locking, Pinyin & clitic protection
│   │   ├── genre_presets.py    # Bilingual genre presets (English & Indonesian)
│   │   ├── hallucination_detector.py # N-gram phrase loop & word-soup detector
│   │   ├── image_cacher.py     # Asynchronous chapter illustration caching
│   │   └── cleaner_tools.py    # TXT/EPUB cleanup pipelines
│   └── tests/                  # 392 pytest unit & integration tests
├── src/
│   ├── pages/                  # 6 pages (Library, Reader, Translate, ContextLibrary, Bookmarks, Settings)
│   ├── components/             # Modals, 2D RelationshipGraph, FidelityHub, reader controls & shadcn UI
│   ├── lib/                    # Workspace-scoped API client, cache invalidation & settings sync
│   └── hooks/                  # Custom React hooks (useConfirm)
└── docs/
    ├── overview.md             # High-level system architecture & data flows
    ├── Handoff.md              # Developer onboarding guide & Agent Playbook
    ├── SDLC.md                 # 31-phase development lifecycle & Categorized ADR Index
    └── decisions/              # 122 Architectural Decision Records (ADR-004 to ADR-125)
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture Overview](docs/overview.md) | High-level system architecture, data flows, and key entry points |
| [Handoff Guide](docs/Handoff.md) | Developer onboarding, architecture overview, and Agent Playbook |
| [SDLC](docs/SDLC.md) | Software development lifecycle (Phases 1–31) & Categorized ADR Index |
| [ADRs](docs/decisions/) | 122 architectural decision records (ADR-004 to ADR-125) |
| [Configuration Guide](docs/Configuration_setting.md) | Detailed setup and multi-device sync instructions |
| [Implementation Plan](docs/implementation_plan.md) | Historical task definitions & acceptance criteria |
| [Ghost Mode Security Notes](docs/ghost-mode-security.md) | Known limitation: the Ghost PIN hides the UI but does not protect `ghost.db` from other devices on the LAN |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Themes look dark/inverted** | Disable Dark Reader or Opera GX "Force Dark Pages" extension for this site |
| **Cannot open on phone (LAN)** | Run `setup_mobile_access.bat` as Administrator and use the LAN URL from Control Hub |
| **Environment / port issues** | Click **🩺 Cek Sistem (Doctor)** in Control Hub or run `python launcher.py doctor` |
| **Cloudflare blocks scraping** | Enable Novalpie Auth in Settings or let the built-in Turnstile solver & AdaptiveDOM fallback run |
| **Translations truncated** | Use the **Fidelity Hub** or **Fix Truncated** action in Library menu, then re-translate |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines and quality gates.

```bash
# Backend test suite
cd backend && py -m pytest tests/ -v

# Frontend strict typecheck, lint & production build
npm run typecheck
npm run lint && npm run build
```

---

## License & Attribution

This project is licensed under the **Apache License 2.0** with mandatory attribution requirements. See the [LICENSE](LICENSE) file for the full license terms.

### ⚖️ Attribution Notice
Under Section 4(d) of the Apache License 2.0, any public deployment, redistribution, modification, or fork of this project **must retain the [NOTICE](NOTICE) file** and provide clear attribution referencing the original author and repository:
- **Author:** SMONE ([@smone-jovan](https://github.com/smone-jovan))
- **Original Repository:** [https://github.com/smone-jovan/Translator_Web](https://github.com/smone-jovan/Translator_Web)

---

## Privacy

This application is **100% self-hosted**. All novels, reading bookmarks, dual-workspace databases (`app.db` and `ghost.db`), cached illustrations, and glossary contexts remain local to your machine. No telemetry or analytics are collected.

> **Ghost Mode note:** the Ghost PIN is a UI privacy screen, not access control. Any device on the same network can read the ghost workspace by calling the API directly. Run the app only on networks you trust. See [Ghost Mode Security Notes](docs/ghost-mode-security.md).

---

Built with care for the web novel translation community.
