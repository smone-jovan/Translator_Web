# 🌌 ReadOmni AI (Self-Hosted Novel Reader & Translator)
> **A premium, privacy-first web novel reader and batch translator powered by local AI.**

[![Project Status](https://img.shields.io/badge/status-Phase%2016%20Complete-success?style=for-the-badge&logo=github)](docs/Handoff.md)
[![Tech Stack](https://img.shields.io/badge/stack-React%2019%20%7C%20FastAPI%20%7C%20Tailwind%20v4-blue?style=for-the-badge)](#-tech-stack)
[![AI Engine](https://img.shields.io/badge/AI%20Engine-LM%20Studio%20%7C%20Gemini%20%7C%20OpenAI-orange?style=for-the-badge&logo=openai)](https://lmstudio.ai/)
[![Database](https://img.shields.io/badge/Database-SQLite%20(WAL%20Mode)-lightgrey?style=for-the-badge&logo=sqlite)](backend/models.py)

**ReadOmni AI** is a premium, self-hosted web application built for reading, crawling, and translating web novels and local EPUB files with complete privacy. By integrating with local LLMs (via **LM Studio**), the entire translation pipeline runs on your local machine, ensuring no data ever leaves your network. 

---

## 🌟 Key Pillars & Features

### 🎨 1. Premium Visuals & Multi-Theme System
*   **Aesthetics First:** Exquisite glassmorphic interface inspired by `app.readomni.com` with smooth, organic micro-interactions and transitions.
*   **Dynamic Theme Presets:** Toggle instantly between **OLED Dark**, **Warm Sepia**, and the signature **Omni Preset** using visual selectors built fully on HSL CSS design tokens.
*   **Mobile-First Ergonomics:** Fully responsive layout with an elegant mobile bottom navigation bar and gesture-friendly reading layout for smartphones.
*   **Custom Cover Personalization System (ADR-019):** High-fidelity canvas compression engine (<100KB JPEG resolution 300x400) to keep SQLite DB/network lightweight, dynamic HSL linear gradients linear fallback, and support for absolute URL cover links.
*   **Premium Novel Details Dashboard (ADR-021):** Premium overlay modal displaying real-time translation statistics, multi-source metadata aggregates, inline detail editing, custom descriptions, and covers.

### ⚡ 2. Batch Translation Studio
*   **Studio Dashboard:** A dedicated command center to translate multiple chapters at once.
*   **Dual Processing Load:** 
    *   *Soft Load:* Safe sequential 1-by-1 processing for extreme GPU thermal safety.
    *   *Hard Load:* High-throughput bulk translation (3-20+ chapters simultaneously) for fast updates.
*   **Status Center:** Real-time visual tracking of batch queue progress and thread states.
*   **Mandatory Overwrite:** Enforces glossary updates immediately to rewrite and sync translated text whenever a term is modified.
*   **Dynamic Action & Continuation Sweep (ADR-026):** Decoupled **"Polish Remaining"** vs **"Re-polish All"** triggers in Soft Load mode to resume batch title polishing from the last completed offset without infinite looping.

### 🧠 3. Smart Context & Glossary Engine
*   **AI Extract First (Smart Extraction):** Recommends automatic term extraction before translation if the thread has < 40 glossary terms, ensuring translation consistency.
*   **Smart Scoping:** Automatic character and term scanning starts precisely from the user's `last_read` chapter bookmark.
*   **Usage-Based Glossary Routing:** Automatically tracks and ranks the top 50 most relevant terms (`usage_count` & `last_used_at`) and feeds them into the system prompt to avoid token bloat.
*   **Terminology Auto-Discovery:** Parses "Translator Notes" and LLM suggestions at the end of chapters to auto-save new glossary terms directly.
*   **Metadata & Synopsis Auto-Translating (ADR-020):** Auto-cleans original descriptions, automatically isolates raw titles from nested bracket/siku tags, and translates summaries from Chinese to target language.
*   **Volume-Aware Zero-Padding Formatting (ADR-024):** Zero-padded serial title formatting supporting standard, volume-level, and custom dynamic increments (e.g. `V1-001. Title`).
*   **Target Language Enforcement in Extraction (ADR-041):** All AI extraction passes (thread context, glossary, relationships) now explicitly inject the user's `target_language` setting into system prompts, ensuring Lorebook notes and summaries are always written in the configured output language instead of defaulting to the source language.

### 📚 4. Library & Premium Book Export
*   **Progressive Bookmarking & Frame-Accurate Scroll Sync (ADR-032):** Automatically saves the user's exact scroll position percentage (on both mobile and desktop) in the background with a 2s client-side debounce, restoring their reading position instantly upon chapter load.
*   **"Continue Reading" History Banner:** The Library automatically tracks and displays your most recently read novel, allowing you to instantly jump back into the exact chapter and scroll percentage where you left off.
*   **Premium Reader UX Refinements (ADR-033):** Mobile-first floating toolbars, morphing radial SVG scroll-to-top buttons, elegant "End of Chapter" premium dividers, and in-chapter bottom controls create a reading experience rivaling Apple Books.
*   **Batch Reliability & Global Progress UX (ADR-034):** Background translation progress now remains visible across the whole app, provider-aware model routing prevents stale model mismatches, and empty/blocked results are surfaced honestly instead of silently succeeding.
*   **Configurable Chapter Token Safety Cap (ADR-035):** Global per-chapter token guardrail with `7K`, `15K`, `22K`, and `30K` presets plus uncapped mode to reduce hallucination drift and wasted token burn on long chapter translations.
*   **Hallucination Audit & Garbled Output Cleanup (ADR-036):** Automated detection and cleanup of common LLM hallucination patterns and garbled output artifacts in translated chapter content.
*   **Thread-Level TXT Cleaning & Book Builder Cleanup Preview (ADR-037):** Per-thread TXT export cleaning pipeline with a live preview modal so users can inspect cleaned content before committing to file export.
*   **Markdown Formatting Support (ADR-038):** Bold (`**text**`) and italic (`*text*`) Markdown is parsed and rendered natively in the Reader UI and exported correctly as `<strong>`/`<em>` tags in EPUB output.
*   **Mobile-Friendly Notifications & Confirmations (ADR-039):** Replaced all native `alert()`/`confirm()` dialogs with `sonner` toasts and a custom `useConfirm()` hook backed by Radix UI `AlertDialog` for a seamless PWA experience.
*   **EPUB & TXT Compiler:** Compile translated chapters into beautifully formatted files with:
    *   *Custom Cover Upload:* Embed cover images directly from your system.
    *   *Curation & Metadata:* Custom author and book title details.
    *   *Selective Compiling:* Select all or filter to compile translated chapters only.
*   **SFACG Scraper & Advanced Search (ADR-022):** Direct integration with stealth parsing strategies to fetch chapters, metadata, and tables of contents from SFACG.
*   **Scraped Author Metadata Integration (ADR-025):** Fully aggregates extracted authorship records into centralized book details.

### 🔎 5. Context Library & Relationship Visualization
*   **Context Capacity Expansion (ADR-040):** Increased Lorebook term limit up to 1000 terms with granular limit presets (20, 50, 100, 200, 300, 500, 750, 1000). Auto-extracted terms now record their source term in notes for full transparency.
*   **Character Relationship Graph (ADR-040):** Interactive physics-based network graph powered by `react-force-graph-2d` that visualizes character connections (Master/Disciple, Factions, Enemies, etc.) extracted automatically by the AI.

### ⚙️ 6. Server-Side Configuration Sync & Volume Boundaries
*   **Unified Multi-Device Sync:** Transitioned from volatile browser `localStorage` to SQLite-backed `global_settings` table, synchronizing settings instantly between desktop and mobile devices on the same network.
*   **Swappable Cloud AI Providers & Adapters (ADR-029):** Seamlessly transition between local offline models (LM Studio) and cloud APIs (OpenAI & Google Gemini) with dynamic card-based selector configuration, secure API key synchronization, and direct streaming outputs. Supports premium free-tier options like `gemini-3.1-flash-lite` and `gemma-4-31b`.
*   **Intelligent Model Mapping & Safety Guards (ADR-030):** Automatically normalizes frontend model names (e.g. `gemma-4-31b`) to strict API endpoints (e.g. `gemma-4-31b-it`). Implements robust parsing for Gemini content/safety filters to explicitly notify users if a web novel chapter violates LLM safety guidelines instead of crashing.
*   **Dynamic RPM Safety Guard (Throttling pacing):** Integrates an automated pacing mechanism in the Python background worker that dynamically adjusts request delays according to the selected model's strict RPM limits (e.g., 4.2s for Gemini 3.1 Flash Lite/Gemma, 12.2s for Gemini 2.5/3 Flash), making it 100% safe to run background batch translations on the Google AI Studio Free Tier without hitting 429 rate limit triggers.
*   **Sequential Background Prefetching:** Configure a smart prefetching range slider (1-5 chapters ahead) to sequentially pre-translate the upcoming chapters in the background while you read.
*   **Chapter Token Safety Controls:** Global toggle plus presets (`7K`, `15K`, `22K`, `30K`) let users trade safety vs. uninterrupted long-form output. Default is `22K`; turning it off removes the cap entirely.
*   **Stateful Volume Transition & Prologue Boundary Guards (ADR-027):** Uses isolated state tags (`volume_just_incremented`) and native prologue parsers to block sequential numeric resets from double-incrementing volume sequences.

### 🛡️ 7. Stability & GPU Guardrails
*   **Throttling Mitigation:** Title translations chunked into blocks of 50 with a `1.0s` delay to prevent local LLM server timeout or freeze.
*   **300s Heavy-Duty Timeout:** Elevated HTTP connections to support complex deep-context translations without abrupt closures.
*   **AbortController Integration:** Automatically cancels past streaming threads when rapidly skipping through chapters to avoid VRAM clashing.
*   **Isolated Test Driven Development (TDD) Suites (ADR-018):** Standardized regression defense suites bound to SQLite in-memory databases to safeguard structural changes.
*   **Translation Auto-Continue (ADR-045):** Detects truncated translations (`finish_reason: "length"`) and automatically sends continuation prompts to complete long chapters. Handles prohibited content gracefully by resetting chapter status.
*   **Batch Worker Reliability (ADR-048):** Automatic retry with exponential backoff (10s → 20s → 40s) for transient API errors (429/503). Prevents infinite loops on completed chapters.
*   **Delete All Translations:** Bulk-clear all translated content for a thread while preserving original text and glossary.

### 🎯 7. Quality/Fast Translation Mode (ADR-046)
*   **Quality Mode:** Full glossary (follows `max_context_terms`), style guide injection, no token cap when safety cap is disabled. Best for Gemini cloud models.
*   **Fast Mode:** Locked 10 glossary terms, no style guide, 10K token cap. Best for LM Studio local models.
*   **Style Guide per Novel:** Define translation style, tone, and rules per thread. Injected into prompts in Quality mode.
*   **Smart Safety Cap Interaction:** When safety cap is enabled, both modes respect it. When disabled, Quality runs uncapped while Fast stays at 10K.
*   **Gemini Model Selector:** Text-out models only with RPM info and free tier labels (e.g., `gemini-3.1-flash-lite (free) [15 RPM]`).

---

## 🛠️ Tech Stack & Dependencies

*   **Frontend:** React 19, Vite, TailwindCSS v4 (Glassmorphic theme presets).
*   **Backend:** Python 3.11, FastAPI (Asynchronous endpoints + background workers).
*   **Database:** SQLite with SQLAlchemy ORM (WAL mode enabled for robust read/write operations).
*   **Scraping Engine:** Crawl4AI (LLM-friendly, stealth web scraping).
*   **EPUB Core:** EbookLib & BeautifulSoup4 (Accurate file parsing & compilation).
*   **AI Backend & Engines:** Multi-provider adapter system supporting local offline models (LM Studio at `http://localhost:1234`), cloud OpenAI models (GPT-4o/GPT-4o-mini), and cloud Google Gemini models (Gemini 3.1 Flash Lite, Gemma 4 31B, Gemini 3 Flash, Gemini 2.5 Flash, Gemini 1.5 Pro) with configurable per-chapter token safety caps.

---

## 💻 Getting Started (Windows Setup)

### 📋 Prerequisites
*   **Node.js** v20+
*   **Python** v3.11+
*   **Translation Engine (Any of the following):**
    *   **LM Studio:** Running locally on port `1234` with an active model (for offline gratis translation).
    *   **Google Gemini API Key:** Personal API key from Google AI Studio (includes a generous personal Free Tier).
    *   **OpenAI API Key:** Cloud API key from OpenAI (paid API access).

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
│   │   ├── ContextLibraryPage.tsx # Context Library & AI Glossary Extraction Workspace
│   │   ├── LibraryPage.tsx     # Thread collection, Batch Translation Studio & Book Builder
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
*   [docs/decisions/](docs/decisions/) — Directory containing all 49 Architectural Decision Records (ADRs), including ADR-042 (UI Consolidation), ADR-046 (Auto-Continue), ADR-047 (Quality/Fast Mode), ADR-048 (Cleanup Hardening), and ADR-049 (Batch Reliability).

---

## ⚠️ Troubleshooting & Known Gotchas

*   **Broken/Inverted Themes (White/Sepia looking dark):** If the light themes (White, Sepia) appear as dark grey or muddy brown, you have a browser extension or setting actively forcing dark mode. **You must disable "Dark Reader" or Opera GX's "Force Dark Pages" feature for this site.** These extensions forcefully override custom design tokens at the renderer level.
*   **Constant Page Reloading (Vite):** If the browser keeps refreshing while a novel is being fetched or translated, ensure `vite.config.ts` has the `server.watch.ignored` paths set to ignore the `backend/` directory and `.db` files.
*   **Lorebook Notes in Wrong Language:** If extracted terms have notes in Chinese after extraction, ensure your `target_language` setting is configured correctly in Settings before running AI extraction. Re-run the extraction pass to refresh notes in the correct language (ADR-041).

---

## 🛡️ License & Privacy
This application is **100% self-hosted**. All of your novels, reading bookmarks, glossary contexts, and translations remain offline and local to your system. No external analytical APIs are used. 

*Designed to bring premium reading directly to your own self-hosted terminal.*
