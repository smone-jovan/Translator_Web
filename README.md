# ReadOmni AI

**Self-hosted AI-powered web novel reader & translator with complete privacy.**

[![Build](https://img.shields.io/badge/build-passing-brightgreen?style=flat-square)](#)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square&logo=python)](#)
[![React](https://img.shields.io/badge/react-19-61DAFB?style=flat-square&logo=react)](#)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](#license)

ReadOmni AI lets you read, crawl, and translate Chinese web novels using local or cloud AI — with zero data leaving your network. Import EPUBs, scrape from URLs, batch-translate chapters, manage glossaries, and export polished EPUBs — all from a single self-hosted dashboard.

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
- [License](#license)

---

## Features

### Translation Engine
- **Multi-provider support** — LM Studio (local), Google Gemini, OpenAI, OpenRouter with seamless switching
- **Quality / Fast mode** — Quality mode for cloud (full glossary, style guide), Fast mode for local LLMs (10K token cap)
- **Auto-continue** — Detects truncated translations and automatically continues until complete
- **Batch translation** — Translate hundreds of chapters with real-time progress tracking
- **Smart glossary** — AI-extracted terms with usage tracking, auto-injection into prompts
- **Style guide per novel** — Define translation tone and rules, injected into Quality mode
- **Multiple API keys** — Store and rotate keys per provider to distribute free-tier quotas

### Reading Experience
- **Glassmorphic UI** — 6 theme presets (Obsidian, OLED, Sepia, White, Omni, Black)
- **Mobile-first** — Bottom navigation, gesture-friendly layout, floating toolbars
- **Bookmark sync** — Exact scroll position saved per chapter, restored on revisit
- **Markdown rendering** — Bold/italic formatting preserved in reader and EPUB export

### Library Management
- **EPUB import/export** — Upload EPUBs, compile translations back with custom covers
- **URL scraping** — Crawl chapters from web URLs with ad/noise stripping
- **SFACG integration** — Direct metadata and chapter scraping from SFACG
- **Cover editor** — Canvas-based cover compression (<100KB) with gradient fallbacks
- **Delete chapters** — Remove individual chapters with automatic re-ordering
- **Fix truncated** — Detect and reset translations cut off mid-sentence
- **TOC detection** — Auto-skips Table of Contents pages to prevent AI hallucination

### Context & Intelligence
- **Character relationship graph** — Interactive D3 force-directed graph of extracted relationships
- **Hallucination detection** — Automated detection of garbled output and repeated patterns
- **TXT/EPUB cleaners** — Strip ads, noise, and false chapters from imported content
- **Glossary up to 1000 terms** — Usage-ranked term injection with LFU eviction

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, Vite 8, TailwindCSS v4, Radix UI |
| **Backend** | Python 3.11, FastAPI, SQLAlchemy 2.0 |
| **Database** | SQLite (WAL mode) |
| **AI Providers** | LM Studio, Google Gemini, OpenAI, OpenRouter |
| **Scraping** | Crawl4AI, BeautifulSoup4 |
| **EPUB** | EbookLib |
| **Testing** | pytest (backend) |

---

## Quick Start

### Prerequisites

- **Node.js** v20+
- **Python** 3.11+
- **AI Provider** (one of):
  - [LM Studio](https://lmstudio.ai/) running on port 1234 (free, local)
  - [Google AI Studio](https://aistudio.google.com/) API key (free tier available)
  - OpenAI API key (paid)
  - OpenRouter API key (optional, cloud access to multiple models)

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
py -m uvicorn main:app --reload --port 8000 --host 0.0.0.0
```

### 2. Frontend

```bash
npm install
npm run dev
```

Open `http://localhost:5173` or use your local IP (e.g., `http://192.168.1.50:5173`) for mobile access.

---

## Configuration

### Environment Variables

Create `backend/.env` (gitignored):

```env
OPENAI_API_KEY=sk-your-key-here
GEMINI_API_KEY=AIzaSy-your-key-here
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

### Settings Page

All configuration is available in the app's Settings page:

| Setting | Description |
|---------|-------------|
| **AI Provider** | LM Studio / OpenAI / Gemini / OpenRouter |
| **Model** | Provider-specific model selection (Gemini: gemini-2.5-flash, gemini-3-flash, gemma-4-31b, etc.) |
| **Target Language** | Indonesian / English |
| **Translation Mode** | Quality (cloud, full glossary) / Fast (local, 10K cap) |
| **Token Safety Cap** | 7K / 15K / 22K / 30K / Off |
| **Glossary Limit** | 20-1000 terms per thread |
| **API Keys** | Multiple keys per provider with auto-rotation |
| **Prefetch** | 1-5 chapters ahead, soft/hard mode |
| **Theme** | 6 glassmorphic presets |

---

## Architecture

```
Translator_Web/
├── backend/
│   ├── main.py                 # FastAPI app entry
│   ├── database.py             # SQLAlchemy models & auto-migration
│   ├── routers/                # API endpoints (15 routers)
│   │   ├── system.py          # Workspace switching (Ghost Mode) with PIN authentication
│   │   └── toc.py             # TOC scraping and bulk chapter import pipeline
│   ├── services/
│   │   ├── ai/                 # Provider adapters (Gemini, OpenAI, LM Studio, OpenRouter)
│   │   ├── background_translator.py  # Batch engine with auto-continue
│   │   ├── context_engine.py   # Prompt builder & glossary injection
│   │   └── cleaner_tools.py    # TXT/EPUB cleanup pipelines
│   └── tests/                  # pytest test suite configuration
├── src/
│   ├── pages/                  # 6 main pages
│   ├── components/             # Reusable UI components
│   └── hooks/                  # Custom React hooks
└── docs/
    ├── decisions/              # 90 Architectural Decision Records (ADR-004 to ADR-093)
    ├── Handoff.md              # Developer onboarding guide
    └── SDLC.md                 # Development lifecycle docs
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Handoff Guide](docs/Handoff.md) | Developer onboarding, architecture overview |
| [SDLC](docs/SDLC.md) | Software development lifecycle |
| [ADRs](docs/decisions/) | 90 architectural decision records (ADR-004 to ADR-093) |
| [Implementation Plan](docs/implementation_plan.md) | Task definitions & acceptance criteria |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Themes look dark/wrong** | Disable Dark Reader or Opera GX "Force Dark Pages" extension |
| **Vite keeps reloading** | Check `vite.config.ts` ignores `backend/` and `.db` files |
| **Gemini 400 error** | Model doesn't support thinking mode — app auto-disables for incompatible models |
| **TOC pages hallucinated** | Auto-detected and skipped (5+ chapter indicators in <5000 chars) |
| **Translations truncated** | Use "Fix Truncated" button in Library menu, then re-translate with overwrite |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Run tests
cd backend && py -m pytest tests/ -v
npm run lint && npm run build
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Privacy

This application is **100% self-hosted**. No data leaves your network unless you explicitly configure a cloud AI provider. No analytics, no tracking, no external APIs.

---

Built with care for the web novel translation community.
