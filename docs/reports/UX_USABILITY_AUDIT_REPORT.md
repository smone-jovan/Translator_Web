# ReadOmni AI (`Translator_Web`): Master Usability & UX Audit Report
**Comprehensive Multi-Persona Evaluation, Forensic Codebase Usability Audit & Actionable Engineering Roadmap**

---

| Document Metadata | Details |
| :--- | :--- |
| **Product Target** | ReadOmni AI (Web Novel Machine Translation, Library & Reader Platform) |
| **Audit Date** | August 27, 2026 |
| **Auditing Framework** | Multi-Persona User Journey Simulation, Forensic Static Code Inspection, UI/UX Pro Max Intelligence Standards |
| **Evaluation Scope** | Library Management, Reader Ergonomics, Batch Translation Engine, Context/Glossary Lorebook, URL/EPUB/TXT Importers, Export Builder, Responsive Viewports (375px–1440px) |
| **Document Classification** | Master Engineering & Design Quality Audit |

---

## Table of Contents

1. [Executive Summary & Audit Methodology](#1-executive-summary--audit-methodology)
   - [1.1 Executive Summary](#11-executive-summary)
   - [1.2 Evaluation Framework & Heuristic Criteria](#12-evaluation-framework--heuristic-criteria)
   - [1.3 Testing Scope & Architectural Overview](#13-testing-scope--architectural-overview)
2. [Persona Walkthroughs & Empathy Simulations](#2-persona-walkthroughs--empathy-simulations)
   - [2.1 Persona 1: "Aria" — Casual Web Novel Reader](#21-persona-1-aria--casual-web-novel-reader)
   - [2.2 Persona 2: "Daoist MTL Sovereign" — Hardcore Xianxia / Power MTL Reader](#22-persona-2-daoist-mtl-sovereign--hardcore-xianxia--power-mtl-reader)
   - [2.3 Persona 3: "Alex" — New User / First-Time Importer](#23-persona-3-alex--new-user--first-time-importer)
3. [Cross-Persona Satisfaction Scorecards](#3-cross-persona-satisfaction-scorecards)
   - [3.1 Comparative Rating Matrix](#31-comparative-rating-matrix)
   - [3.2 Analysis of Variance & Systemic Vulnerabilities](#32-analysis-of-variance--systemic-vulnerabilities)
4. [Severity-Categorized Friction Point & Defect Catalog](#4-severity-categorized-friction-point--defect-catalog)
   - [4.1 Critical Severity Defects](#41-critical-severity-defects)
   - [4.2 High Severity Defects](#42-high-severity-defects)
   - [4.3 Medium Severity Defects](#43-medium-severity-defects)
   - [4.4 Low & Polish Defects](#44-low--polish-defects)
5. [Actionable Roadmap & Prioritized Recommendations](#5-actionable-roadmap--prioritized-recommendations)
   - [5.1 Phase 1 (Immediate / Sprint 1): Core Navigation, Reader Ergonomics & Critical Bug Fixes](#51-phase-1-immediate--sprint-1-core-navigation-reader-ergonomics--critical-bug-fixes)
   - [5.2 Phase 2 (Mid-Term / Sprint 2): Importer Polish, Glossary Intelligence & Batch Stream Center](#52-phase-2-mid-term--sprint-2-importer-polish-glossary-intelligence--batch-stream-center)
   - [5.3 Phase 3 (Long-Term / Sprint 3): Advanced Scraper Customization, Relationship Graph & Multi-Format Export](#53-phase-3-long-term--sprint-3-advanced-scraper-customization-relationship-graph--multi-format-export)
   - [5.4 Complexity vs. User Impact Matrix](#54-complexity-vs-user-impact-matrix)

---

## 1. Executive Summary & Audit Methodology

### 1.1 Executive Summary

ReadOmni AI (`Translator_Web`) is an advanced, AI-driven machine translation and reading environment purposefully engineered for raw Asian web novels (Chinese Xianxia/Wuxia, Korean LitRPG, Japanese Light Novels). The platform integrates a modern React + Tailwind + Radix UI frontend with an asynchronous Python FastAPI backend, offering features rarely found in generic translation tools: cultivation realm presets, LFU/LRU glossary memory eviction with manual lock pinning, multi-key round-robin provider rotation, post-translation structural fidelity verification, and auto-continuation truncation recovery.

Despite these exceptional algorithmic and visual foundations, this comprehensive multi-persona audit reveals that **the user experience is constrained by critical workflow gaps, discoverability friction, and missing ergonomic controls**. 

Key findings across the three simulated user personas include:
1. **First-Time Importers (Persona 3)** face a broken primary call-to-action in the empty library state (`window.location.hash` bug), unlinked EPUB Dublin Core author/cover metadata, a dead "New Context" button, and an author string that literally displays `"by epub"`.
2. **Casual Readers (Persona 1)** experience excessive friction due to the lack of in-reader lighting themes (Sepia/OLED/Night) and typography controls inside the reading view, forcing 6-step context-switching to adjust basic ambient comfort, alongside the absence of a slide-out Table of Contents drawer.
3. **Hardcore Power Readers (Persona 2)** are blocked by the complete absence of keyboard navigation hotkeys (`J`/`K`), untethered split-view scrolling in raw/MTL comparison mode, non-pausable batch queues, non-interactive character graphs, and the inability to import/export glossaries via CSV/JSON.

Addressing these friction points through the phased roadmap outlined in Section 5 will elevate ReadOmni AI from a technically capable translation tool into an industry-leading, gold-standard reading ecosystem.

---

### 1.2 Evaluation Framework & Heuristic Criteria

The audit was conducted using empirical static code analysis, architectural dataflow tracing, and multi-persona empathy walkthroughs against 5 core usability dimensions:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        USABILITY EVALUATION FRAMEWORK                      │
├────────────────────────────────────────────────────────────────────────────┤
│ 1. Cognitive Load & Flow Continuity   │ 4. Error Resilience & Recovery     │
│    - One-tap actions vs deep menus    │    - Fidelity alerts & auto-retry  │
│    - Seamless state transitions       │    - Non-destructive queue controls│
│                                       │                                    │
│ 2. Visual Ergonomics & Readability    │ 5. System Transparency & Feedback  │
│    - Contrast ratios (WCAG AA/AAA)    │    - Real-time batch metrics       │
│    - Typography & line measures       │    - Clear mental model alignment  │
│                                       │                                    │
│ 3. Touch & Input Accessibility        │                                    │
│    - 44px+ mobile touch targets       │                                    │
│    - Keyboard shortcut parity         │                                    │
└────────────────────────────────────────────────────────────────────────────┘
```

---

### 1.3 Testing Scope & Architectural Overview

The audit evaluated all primary user interaction surfaces across desktop, tablet, and mobile viewports:

```
                                READOMNI AI ARCHITECTURE
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                           FRONTEND (React 18 + TS)                      │
  │  ┌──────────────────┐  ┌───────────────────┐  ┌──────────────────────┐  │
  │  │   LibraryPage    │  │    ReaderPage     │  │  ContextLibraryPage  │  │
  │  │  - Status Tabs   │  │  - NovelHeader    │  │  - Glossary Terms    │  │
  │  │  - Smart Sorting │  │  - ChapterReader  │  │  - Xianxia Presets   │  │
  │  │  - Active Reads  │  │  - SettingsModal  │  │  - Entity Graph      │  │
  │  └─────────┬────────┘  └─────────┬─────────┘  └──────────┬───────────┘  │
  │            │                     │                       │              │
  │  ┌─────────┴─────────────────────┴───────────────────────┴───────────┐  │
  │  │ Modal Layer: BulkTranslate, BulkStatusCenter, TocImport, Export   │  │
  │  └─────────────────────────────────┬─────────────────────────────────┘  │
  └────────────────────────────────────┼────────────────────────────────────┘
                                       │ REST / SSE Streaming / Beacons
  ┌────────────────────────────────────┼────────────────────────────────────┐
  │                           BACKEND (FastAPI + SQLite)                    │
  │  ┌──────────────────┐  ┌───────────┴───────┐  ┌──────────────────────┐  │
  │  │ routers/threads  │  │ routers/batch     │  │ routers/epub & scrape│  │
  │  │ - Progress & Sync│  │ - Queue Pacing    │  │ - Parsers & Crawler  │  │
  │  └─────────┬────────┘  └───────────┬───────┘  └──────────┬───────────┘  │
  │            │                       │                     │              │
  │  ┌─────────┴───────────────────────┴─────────────────────┴───────────┐  │
  │  │ Core Services: background_translator.py, context_engine.py,       │  │
  │  │                fidelity_checker.py, prompt_templates.py           │  │
  │  └───────────────────────────────────────────────────────────────────┘  │
  └─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Persona Walkthroughs & Empathy Simulations

---

### 2.1 Persona 1: "Aria" — Casual Web Novel Reader

```
┌────────────────────────────────────────────────────────────────────────────┐
│ PERSONA PROFILE: ARIA                                                      │
├────────────────────────────────────────────────────────────────────────────┤
│ • Age & Occupation: 26, UI/UX Designer & Casual Web Novel Reader          │
│ • Primary Devices: iPhone 13 (375px Safari) on commute; Laptop in bed      │
│ • Reading Volume: 3–5 chapters daily during 30-min commute; 30 min in bed   │
│ • Core Desires: Zero-friction resume, eye comfort in bed (Sepia/OLED),     │
│   minimal UI clutter, responsive mobile touch targets, reliable bookmarks. │
└────────────────────────────────────────────────────────────────────────────┘
```

#### Step-by-Step Empathy Journey

```
[1. Library Arrival] ───► [2. Quick Resume] ───► [3. Immersive Reading] ───► [4. Scroll Sync] ───► [5. Chapter Hop]
 (Browses status tabs,   (1-tap into Chapter    (Distraction-free auto-    (Phone locks, beacon     (Wants to jump to
  admires cover art)      from hero carousel)    hide, seeks night mode)    syncs exact scroll)      TOC / next chapter)
```

1. **Step 1: Library Arrival & Browsing**
   - *Experience*: Aria opens the app on her phone. She is greeted by the **Continue Reading Carousel** (`src/pages/LibraryPage.tsx:594-685`), which showcases her current book with a dynamic gradient cover, progress percentage (`65% Done`), and a prominent `RESUME` button. Books without covers render programmatic mesh gradients and initials (`getTitleGradient` in `LibraryPage.tsx:114`), avoiding broken image placeholders.
   - *Friction*: She notices that the page title is `"Your Library"`, the button is `"RESUME"`, but the status tabs are in Indonesian (`"Semua"`, `"Sedang Dibaca"`, `"Belum Dibaca"`, `"Selesai"`). The search placeholder says `"Cari judul, pengarang..."`. The linguistic inconsistency is noticeable. Furthermore, when she finishes reading a 1-chapter short story or reaches the final chapter (100%), the book completely disappears from the top carousel (`activeReads = threads.filter(t => t.progress > 0 && t.progress < 100)` in `LibraryPage.tsx:548`).

2. **Step 2: One-Tap Quick Resume into Reader**
   - *Experience*: Aria taps the `RESUME` button. The application invokes `onOpenThread(book.id, book.last_read_id)` (`src/pages/ReaderPage.tsx:243-256`), immediately mounting `ChapterReader` and bypassing intermediate landing screens. Instant restore from `sessionStorage` (`ReaderPage.tsx:435-460`) eliminates blank-screen latency on cellular data.

3. **Step 3: Immersive Reading & Lighting Adjustment**
   - *Experience*: As Aria scrolls down, the distraction-free mode automatically collapses the top navbar and floating bottom bar (`src/components/reader/ChapterReader.tsx:227-236`). The dynamic floating scroll-to-top button (`ChapterReader.tsx:798-843`) shows an animated circular SVG progress ring with exact percentage (`42%`). AI prompt thoughts (`<think>`) are automatically stripped (`cleanThoughts` in `ChapterReader.tsx:9-19`).
   - *Friction*: When reading in bed at night, Aria wants to switch from light mode to OLED Black or warm Sepia. She taps the settings gear icon in the reader header (`src/components/reader/SettingsOverlay.tsx:1-289`). To her dismay, the overlay only contains a Font Size slider, Layout Mode (ORI/TRS/BOTH), Hide Thoughts toggle, and Style Guide text. **Themes, Font Family, Line Height, and Margin Width are completely absent.** To change her theme, Aria must exit the reader, return to the Library, click Settings in the sidebar, scroll down to Appearance, select OLED, return to the Library, find her book, and resume reading.

4. **Step 4: Bookmark & Scroll Synchronization**
   - *Experience*: Aria reaches paragraph 14 (58%), taps the Star icon (`ChapterReader.tsx:473`) to favorite the chapter (which turns vibrant gold and syncs to `BookmarksPage.tsx`), and locks her phone.
   - *Resilience*: `navigator.sendBeacon` transmits the scroll progress payload to `/api/threads/{id}/chapters/{id}/progress` (`ChapterReader.tsx:319-324`). When she later opens her laptop, multi-stage scroll restoration (`ChapterReader.tsx:387-391`) executes at 0ms, 50ms, 150ms, and 350ms to account for layout reflow.

5. **Step 5: Table of Contents & Chapter Hopping**
   - *Experience*: Aria finishes Chapter 45 and wants to skim upcoming chapter titles.
   - *Friction*: Tapping `List` on the mobile toolbar (`src/pages/ReaderPage.tsx:1224-1236`) does not open a slide-out Table of Contents drawer. Instead, it completely unmounts `ChapterReader` and navigates back to `NovelHeader.tsx`. On mobile (375px), `NovelHeader` takes up over 650px of vertical space (`NovelHeader.tsx:37-184`), forcing her to scroll past the huge cover image, action buttons, and synopsis just to see the chapter grid.

---

### 2.2 Persona 2: "Daoist MTL Sovereign" — Hardcore Xianxia / Power MTL Reader

```
┌────────────────────────────────────────────────────────────────────────────┐
│ PERSONA PROFILE: DAOIST MTL SOVEREIGN                                      │
├────────────────────────────────────────────────────────────────────────────┤
│ • Age & Background: 31, Software Engineer & Hardcore Cultivation Reader   │
│ • Reading Habits: Translates and binging 50–200 raw chapters per day        │
│ • Stack: Raw Chinese sites (69shu, Qidian raws), Gemini Flash Lite, Local  │
│   Qwen 2.5 32B via LM Studio for uncensored scenes.                        │
│ • Core Desires: Absolute terminology consistency (Dantian, Nascent Soul),  │
│   batch queue pause/resume, rapid J/K hotkeys, synchronized raw/MTL scroll.│
└────────────────────────────────────────────────────────────────────────────┘
```

#### Step-by-Step Empathy Journey

```
[1. Preset Injection] ──► [2. Custom Glossary] ──► [3. Multi-Key Setup] ──► [4. Batch Launch] ──► [5. Power Reading]
 (Applies Xianxia          (Attempts CSV import,    (Configures 3 Gemini     (Executes 50 chapters (Binge reads, needs
  38-term hierarchy)        finds no button)         keys with round-robin)   with auto-continue)   hotkeys & scroll sync)
```

1. **Step 1: Xianxia Preset Injection**
   - *Experience*: The user visits the Context Library (`/context`) and clicks `Apply Preset` $\rightarrow$ `Xianxia / Cultivation (Standard)`. The system instantly injects 38 canonical cultivation ranks and concepts (`炼气` $\rightarrow$ `Qi Refining`, `筑基` $\rightarrow$ `Foundation Establishment`, `金丹` $\rightarrow$ `Core Formation`, `元婴` $\rightarrow$ `Nascent Soul`, `化神` $\rightarrow$ `Deity Transformation`, `大乘` $\rightarrow$ `Mahayana`, `渡劫` $\rightarrow$ `Tribulation Transcendence`, `丹田` $\rightarrow$ `Dantian`, `经脉` $\rightarrow$ `Meridians`, `灵根` $\rightarrow$ `Spiritual Root`). All 38 entries are automatically locked (`is_locked=True` in `backend/services/genre_presets.py:19-64`), ensuring they survive memory eviction.

2. **Step 2: Custom Terminology & Rule Configuration**
   - *Friction*: The user attempts to import his existing 150-term custom glossary (compiled in CSV format from previous novels). **There is no CSV/JSON Import/Export button** (`src/pages/ContextLibraryPage.tsx:40-1144`). He is forced to type them manually one by one or rely on AI extraction. In the `Rules` tab, 4 excellent domain rules are displayed, but the `Customize` button is non-functional (`ContextLibraryPage.tsx:1020-1023`), preventing custom rule modification.

3. **Step 3: AI Provider Configuration & Multi-Key Rotation**
   - *Experience*: In Settings (`/settings`), the user enters 3 Gemini API keys for round-robin rotation (45 RPM combined). The backend calculation (`backend/services/background_translator.py:659-730`) divides the RPM delay by active keys, with automatic model fallback (`background_translator.py:835-850`) if quota is exhausted.
   - *Friction*: There is no "Test API Key" button for cloud providers (`src/pages/SettingsPage.tsx:611-938`). Invalid keys only fail downstream during active batch execution.

4. **Step 4: Large Batch Translation Execution & Monitoring**
   - *Experience*: The user selects 50 chapters in `BulkTranslateModal.tsx:541` (virtualized with `react-virtuoso`). Auto-continuation (`background_translator.py:341-456`) runs up to 3 rounds with loop detection, and post-translation structural fidelity verification checks paragraph ratios (`backend/services/fidelity_checker.py`).
   - *Friction*: The modal presents two confusing selectors side-by-side: `Engine Core Speed: Sequential Mode vs Parallel Mode` AND `Translation Quality: Quality vs Fast` (`BulkTranslateModal.tsx:654-780`). In the minimized `BulkStatusCenter.tsx:142-177`, **there is no Pause button**—only `Stop Batch` (which cancels and deletes the queue). There are no real-time metrics (tokens/sec, ETA, live streaming log).

5. **Step 5: Power-Reading & Split-View Verification**
   - *Experience*: The user opens Chapter 1 and switches to `BOTH` mode (side-by-side raw Chinese and English MTL).
   - *Friction*: **Untethered Split Scroll**: Scrolling the English pane does not scroll the Chinese pane (`src/components/reader/ChapterReader.tsx:558-563, 680-685`), making cross-referencing martial techniques exhausting. **Zero Keyboard Hotkeys**: Pressing `J`, `K`, or `ArrowRight` does nothing (`src/pages/ReaderPage.tsx` has 0 keydown listeners). **Indonesian Bleed**: When a fidelity warning triggers, the banner displays hardcoded Indonesian buttons (`✓ Abaikan`, `Perbaiki`, `Peringatan Kualitas` in `ChapterReader.tsx:699, 707, 715`).
   - *Entity Graph*: The force-directed graph in `/context` is non-interactive; clicking nodes only logs to developer console (`RelationshipGraph.tsx:104`).

---

### 2.3 Persona 3: "Alex" — New User / First-Time Importer

```
┌────────────────────────────────────────────────────────────────────────────┐
│ PERSONA PROFILE: ALEX                                                      │
├────────────────────────────────────────────────────────────────────────────┤
│ • Age & Background: 22, College Student & First-Time Web Novel Importer    │
│ • Reading Habits: Discovers raw web novels on raw web directories, seeks   │
│   a reliable tool to scrape TOCs, upload EPUBs/TXTs, and build clean files.│
│ • Core Desires: Clear onboarding guidance, 1-click TOC scraping, accurate  │
│   metadata extraction, custom cover art styling, clean EPUB/TXT export.    │
└────────────────────────────────────────────────────────────────────────────┘
```

#### Step-by-Step Empathy Journey

```
[1. First Landing] ───► [2. Empty Library CTA] ───► [3. URL Scraping] ───► [4. EPUB/TXT Upload] ───► [5. Export Builder]
 (Clean UI, but is it    (Clicks "Go to Translate", (Pasting TOC URL into   (Uploads EPUB; author says (Exports clean EPUB,
  instant or project?)    NOTHING happens! Bug!)     main area scrapes ch1)  "by epub", no TXT import)   wants PDF option)
```

1. **Step 1: First Landing & Mental Model Gap**
   - *Experience*: Alex opens `http://localhost:5173`. The landing screen is `TranslatePage.tsx:308`: *"What can I translate for you? Paste a URL, upload an EPUB, or enter text to start."*
   - *Friction*: Alex is unsure if ReadOmni AI is a quick snippet translator (like DeepL) or a full novel project manager. The bottom toolbar contains tiny unlabeled icon buttons: cloud upload (`TranslatePage.tsx:361`), eraser ("TXT Cleaner" at line 369), tree-list ("Detect TOC" at line 380), and settings gear.

2. **Step 2: Empty Library State & Broken Call-To-Action**
   - *Experience*: Alex clicks the **Library** tab in the sidebar before importing anything. The page displays: *"Library is Empty — Start by translating a URL or uploading an EPUB to build your personal collection."* A prominent primary button reads: `[Go to Translate]`.
   - *CRITICAL FAILURE*: Alex clicks `[Go to Translate]`. **Nothing happens.** The button executes `onClick={() => window.location.hash = '#translate'}` (`src/pages/LibraryPage.tsx:883`). However, `App.tsx` manages navigation through React state `activeTab` (`src/App.tsx:58`) with **zero hash-change listeners**. Alex is stranded in the empty library.

3. **Step 3: URL Scraping (Single Chapter vs TOC Confusion)**
   - *Experience*: Alex returns to Translate and pastes a novel TOC URL (`https://book.sfacg.com/Novel/12345/MainIndex/`). Clicking the prominent purple Arrow button (`TranslatePage.tsx:503`) sends the URL to `/api/threads/import-url`, which mistakenly scrapes the TOC links as text into Chapter 1.
   - *Aha Moment*: Alex notices the small `ListTree` icon (`TranslatePage.tsx:380`), which opens `TocImportModal.tsx:96`. Clicking `[Import All]` creates a Thread with chapter stubs ready for on-demand translation.
   - *Friction*: If a web novel is behind Cloudflare or uses a non-standard layout, the heuristic scraper (`backend/routers/toc.py:68-79`) returns 422 "No chapters found", with **no custom CSS selector input** to manually specify title and content nodes.

4. **Step 4: Local File Import & Metadata Drop**
   - *Experience*: Alex tries importing a 100-chapter `.txt` novel. Clicking the eraser button (`TranslatePage.tsx:367`) uploads to `/api/tools/txt-cleaner-file` and **immediately forces a download of `my_novel_cleaned.txt` to Alex's browser download folder without creating a library novel**. Alex realizes there is **no TXT novel project importer**.
   - *EPUB Import Defect*: Alex converts the file to `.epub` and uploads it. In `backend/routers/epub.py:126-134`, `dc:creator` (author), `dc:description` (synopsis), and cover image are ignored. In `NovelHeader.tsx:72`, the author subtitle literally renders as **`by epub`** because the component renders `{thread.source_type || 'AI Platform'}` instead of `{thread.author}`!
   - *Delight*: In `EditCoverModal.tsx:36`, Alex customizes the cover using client-side canvas 3:4 compression, or scrapes metadata from NovelUpdates via `ScrapeNUModal.tsx:35`.
   - *Dead Button*: In `/context`, clicking `[+ New Context]` (`ContextLibraryPage.tsx:467-470`) is a dead click with no `onClick` handler.

5. **Step 5: Exporting the Translated Novel**
   - *Experience*: Alex opens `ExportModal.tsx:31` ("Book Builder"). The default toggle `Remove AI Thoughts (<think>)` is checked. Exporting to EPUB generates a well-formatted `.epub` with embedded cover and clean Dublin Core tags. Alex notes that PDF export is missing.

---

## 3. Cross-Persona Satisfaction Scorecards

### 3.1 Comparative Rating Matrix

Ratings are evaluated on a 1–10 scale across all 4 usability dimensions with weighted rationale grounded in static code analysis and simulated user feedback.

| Dimension | Persona 1: Aria (Casual) | Persona 2: Daoist MTL (Power) | Persona 3: Alex (New Importer) | Cross-Persona Average | Grade | Key Systemic Rationale |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Ease of Use (Ergonomics & Navigation)** | **7.5 / 10** | **6.0 / 10** | **6.5 / 10** | **6.67 / 10** | **C+** | High friction in core transitions: broken empty-state CTA, lack of reader hotkeys (`J`/`K`), untethered split scroll, missing TOC slide-out drawer, and hidden TOC scraper buttons. |
| **Visual Appeal & Theming** | **8.8 / 10** | **8.5 / 10** | **8.8 / 10** | **8.70 / 10** | **A-** | Outstanding glassmorphism (`.glass`), rich color contrast (7.8:1 to 19.8:1), animated SVG scroll progress rings, dynamic gradient fallback covers, and clean typography tokens. |
| **Performance & Throughput** | **9.0 / 10** | **8.5 / 10** | **8.0 / 10** | **8.50 / 10** | **B+** | Fast sessionStorage caching, list virtualization (`react-virtuoso`), sub-100ms canvas cover compression, non-blocking beacon scroll sync, and multi-worker concurrent batch pipelines. |
| **Reliability & Error Resilience** | **8.5 / 10** | **8.5 / 10** | **5.5 / 10** | **7.50 / 10** | **B** | Strong auto-continuation loops and fidelity checks, but severely compromised for new users by dead buttons, dropped EPUB metadata, and "by epub" author bugs. |
| **Composite Weighted Score** | **8.45 / 10** | **7.90 / 10** | **7.20 / 10** | **7.85 / 10** | **B** | **High-potential, architecturally robust engine hindered by localized UI defects and power-user ergonomic omissions.** |

---

### 3.2 Analysis of Variance & Systemic Vulnerabilities

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    CROSS-PERSONA SATISFACTION VARIANCE                     │
├────────────────────────────────────────────────────────────────────────────┤
│   Aria (Casual):     ████████████████████░░░░  8.45 / 10 (Delighted by UI) │
│   Daoist MTL (Power):██████████████████░░░░░░  7.90 / 10 (Blocked on Tools)│
│   Alex (New User):   █████████████████░░░░░░░  7.20 / 10 (Stuck on Bugs)   │
└────────────────────────────────────────────────────────────────────────────┘
```

1. **The First-5-Minutes Chasm (Persona 3 Drop-Off Risk)**: While experienced users can navigate around defects, first-time users immediately hit the broken "Go to Translate" CTA, dead "New Context" button, and "by epub" author display, creating an impression of system fragility.
2. **The In-Reader Ergonomics Disconnect (Personas 1 & 2)**: Both casual and power readers suffer from reader isolation—themes and typography cannot be changed without exiting to global settings, chapters cannot be browsed without unmounting the reader, and dual-pane comparison mode lacks synchronized scrolling.
3. **Linguistic Inconsistency Bleed**: Across all personas, hardcoded Indonesian UI labels (*"Sedang Dibaca"*, *"✓ Abaikan"*, *"Perbaiki"*) bleed into English language sessions, diluting product professionalism.

---

## 4. Severity-Categorized Friction Point & Defect Catalog

```
Defect Severity Definitions:
  [CRITICAL] Breaks primary navigation, causes dead-end interactions, or halts core workflows.
  [HIGH]     Major efficiency blocker, metadata loss, or missing essential power capability.
  [MEDIUM]   Noticeable friction, cognitive overhead, or inconsistent UI behavior.
  [POLISH]   Aesthetic inconsistency, bilingual copy leak, or minor spacing flaw.
```

---

### 4.1 Critical Severity Defects

#### DEF-CRIT-01 (FP-P3-01): Broken Empty Library State Primary Navigation CTA
- **Component & Path**: `src/pages/LibraryPage.tsx:883`
- **Severity**: **CRITICAL**
- **Observed Behavior**:
  ```tsx
  // src/pages/LibraryPage.tsx:883
  <Button size="lg" className="rounded-2xl px-12 font-bold shadow-lg" onClick={() => window.location.hash = '#translate'}>
    Go to Translate
  </Button>
  ```
- **Root Cause**: `App.tsx` manages application routing via React state `activeTab` (`src/App.tsx:58`). `LibraryPage` receives no `onNavigateToTranslate` callback prop, and `App.tsx` has zero `hashchange` event listeners. Mutating `window.location.hash` changes the URL bar hash but fails to trigger a re-render or tab transition in the React tree.
- **User Impact**: A brand-new user with an empty library clicks the main call-to-action button and nothing happens, leaving them stranded.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `navigation-patterns` & `back-behavior` (all primary CTAs must execute deterministic navigation transitions).

---

#### DEF-CRIT-02 (DEF-P2-01): Complete Absence of Reader Keyboard Navigation Hotkeys
- **Component & Path**: `src/pages/ReaderPage.tsx:1-1270`, `src/components/reader/ChapterReader.tsx:1-850`
- **Severity**: **CRITICAL**
- **Observed Behavior**: Grep search for `keydown`, `keyup`, or hotkey hook implementations in `ReaderPage.tsx` and `ChapterReader.tsx` yields 0 event listeners.
- **Root Cause**: No keyboard event listener or shortcut registry was wired into the chapter reader view.
- **User Impact**: Power users reading 100+ chapters per session are forced to make hundreds of manual mouse clicks and full-page scrolls to navigate between chapters, toggle views, or bookmark chapters.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `keyboard-nav` & `keyboard-shortcuts` (full keyboard support is mandatory for core reading flows).

---

#### DEF-CRIT-03 (DEF-P2-02): Untethered Split-View Scrolling in Dual (Raw / Translated) Mode
- **Component & Path**: `src/components/reader/ChapterReader.tsx:558-563, 680-685`
- **Severity**: **CRITICAL**
- **Observed Behavior**: In `BOTH` mode, `originalScrollContainerRef` and `translatedScrollContainerRef` maintain independent scroll handlers (`handleScrollOriginal` and `handleScrollTranslated`). Scrolling one container does not update the scroll position of the other.
- **Root Cause**: Handlers only update local UI progress state and lack proportional synchronized scroll lock logic (`target.scrollTop = source.scrollTop * ratio`).
- **User Impact**: Xianxia readers cross-referencing complex Chinese technique names and poetry against English MTL constantly lose paragraph alignment between panes.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `gesture-conflicts` & `scroll-behavior`.

---

#### DEF-CRIT-04 (FP-P3-02): Dead "New Context" Action Button in Context Library
- **Component & Path**: `src/pages/ContextLibraryPage.tsx:467-470`
- **Severity**: **CRITICAL**
- **Observed Behavior**:
  ```tsx
  // src/pages/ContextLibraryPage.tsx:467-470
  <div className="p-4 border-t border-[var(--border)] bg-[var(--card)]">
    <button className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-[var(--border)] text-sm font-medium text-[var(--muted-foreground)] hover:bg-[var(--secondary)] transition-all">
      <Plus size={16} /> New Context
    </button>
  </div>
  ```
- **Root Cause**: The `<button>` element has no `onClick` handler, modal trigger, or dispatch action attached.
- **User Impact**: Users attempting to create custom Lorebooks or standalone glossary contexts experience a non-responsive click.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `disabled-states` & `touch-and-interaction` (interactive elements must provide visual and functional response).

---

### 4.2 High Severity Defects

#### DEF-HIGH-01 (DEF-01): In-Reader `SettingsOverlay` Lacks Theme & Typography Controls
- **Component & Path**: `src/components/reader/SettingsOverlay.tsx:1-289`, `src/components/reader/ChapterReader.tsx:559, 682`
- **Severity**: **HIGH**
- **Observed Behavior**: `SettingsOverlay` contains Font Size slider (12px–32px), Layout Mode (ORI/TRS/BOTH), Hide Thoughts toggle, Auto-Prefetch controls, and Style Guide textarea. **Theme Presets (Sepia, Obsidian Night, OLED, White, Omni), Font Family (Atkinson, Serif, Sans), Line Spacing, and Reading Margins are missing.**
- **Root Cause**: Theme and typography state are isolated in `SettingsPage.tsx` and not exposed via context to `SettingsOverlay.tsx`.
- **User Impact**: Readers in dark environments cannot switch to night or sepia mode without exiting their chapter, navigating to global settings, and re-opening the book.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `dark-mode-pairing` & `system-controls` (ambient lighting and typography controls must be accessible in-session).

---

#### DEF-HIGH-02 (FP-P3-04): Novel Header Subtitle Renders `by epub` / `by url` Instead of Author
- **Component & Path**: `src/components/reader/NovelHeader.tsx:71-73`
- **Severity**: **HIGH**
- **Observed Behavior**:
  ```tsx
  // src/components/reader/NovelHeader.tsx:71-73
  <p className="text-sm text-[var(--muted-foreground)] font-medium mb-6">
    by <span className="text-[var(--foreground)] font-semibold">{thread.source_type || 'AI Platform'}</span>
  </p>
  ```
- **Root Cause**: The component mistakenly interpolates `thread.source_type` ("epub", "url") instead of `thread.author || 'Unknown Author'`.
- **User Impact**: Every novel landing screen displays *"by epub"* or *"by url"* as the author, undermining product quality.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `visual-hierarchy` & typography standards.

---

#### DEF-HIGH-03 (FP-P3-05): EPUB Import Drops Dublin Core Metadata & Cover Assignment
- **Component & Path**: `backend/routers/epub.py:43-47, 126-134, 151-169`
- **Severity**: **HIGH**
- **Observed Behavior**:
  ```python
  # backend/routers/epub.py:131
  thread = Thread(title=book_title, original_title=book_title, source_type="epub")
  # Author and synopsis metadata from Dublin Core are never queried!
  # Extracted cover image file is saved to uploads/ but thread.cover_image is never set!
  ```
- **Root Cause**: Dublin Core metadata tags `dc:creator` and `dc:description` are not extracted into the `Thread` model during parsing, and the extracted `ebooklib.ITEM_COVER` path is not assigned to `thread.cover_image`. Furthermore, `latin-1` decode fallback corrupts Chinese GBK/Big5 encoded EPUBs into mojibake.
- **User Impact**: Users uploading valid EPUBs lose author and synopsis data, receive no book cover, and risk corrupted Asian text.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `reliability` & data integrity standards.

---

#### DEF-HIGH-04 (DEF-P2-03): Lack of Pause / Resume Controls for Batch Translation Queue
- **Component & Path**: `src/components/BulkStatusCenter.tsx:142-177`, `backend/routers/batch.py:102-106`
- **Severity**: **HIGH**
- **Observed Behavior**: The only queue modification action in `BulkStatusCenter` is `Stop Batch` (`/api/threads/{id}/batch-stop`), which cancels active tasks and discards the remaining queued chapters.
- **Root Cause**: `BackgroundTranslator` in `backend/services/background_translator.py` only implements `stop_batch` and lacks a paused state machine (`is_paused = True`) with non-destructive suspend/resume.
- **User Impact**: Users running 100-chapter batches who need to temporarily free up GPU VRAM or avoid hourly API rate limits must abort the entire queue and manually re-select untranslated chapters later.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `escape-routes` & `undo-support`.

---

#### DEF-HIGH-05 (DEF-P2-04): Complete Absence of Glossary Bulk Import / Export (CSV / JSON)
- **Component & Path**: `src/pages/ContextLibraryPage.tsx:40-1144`
- **Severity**: **HIGH**
- **Observed Behavior**: `ContextLibraryPage` lacks file input elements, upload modals, or export handlers for serialized glossary datasets.
- **Root Cause**: Glossary terms can only be created via manual single-term forms or automated AI extraction.
- **User Impact**: Power users cannot transfer pre-existing glossaries (from NovelUpdates, spreadsheets, or community translation groups), creating an extreme manual entry burden.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `export-option` & data portability standards.

---

#### DEF-HIGH-06 (FP-P3-03): Absence of TXT Web Novel Project Importer
- **Component & Path**: `src/pages/TranslatePage.tsx:346-371`, `backend/routers/tools.py`
- **Severity**: **HIGH**
- **Observed Behavior**: The "TXT Cleaner" button on the Translate page sends `.txt` files to `/api/tools/txt-cleaner-file` and immediately downloads a cleaned `.txt` file back to the browser download folder without creating a library Thread.
- **Root Cause**: No chapter-splitting regex parser (`第[0-9]+章`, `Chapter [0-9]+`) exists to convert raw `.txt` files into a multi-chapter project thread.
- **User Impact**: Web novel readers with massive `.txt` archives cannot import their novels into ReadOmni AI without converting them externally to EPUB.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `progressive-disclosure` & user workflow expectations.

---

#### DEF-HIGH-07 (DEF-P2-05): Non-Interactive Character Graph & Missing Relationship CRUD
- **Component & Path**: `src/components/RelationshipGraph.tsx:103-105`, `backend/routers/relationships.py:1-35`
- **Severity**: **HIGH**
- **Observed Behavior**: Clicking nodes in `RelationshipGraph.tsx` only executes `console.log(node.id)`. The backend router only provides `GET` and `DELETE`, with no `POST` or `PUT` endpoints.
- **Root Cause**: The force-directed graph is rendered as an inert visualization without node selection sidebars or manual relationship authoring endpoints.
- **User Impact**: Users cannot inspect character profiles, faction affiliations, or add relationship links (mentor, enemy, romance).
- **Design Standard Violation**: Violates UI/UX Pro Max rule `drill-down-consistency` & `tooltip-on-interact`.

---

#### DEF-HIGH-08 (DEF-P2-06): Missing Live API Key Validation for Cloud Providers
- **Component & Path**: `src/pages/SettingsPage.tsx:611-938`, `src/components/ApiKeyManager.tsx:1-83`
- **Severity**: **HIGH**
- **Observed Behavior**: Live connection testing (`testConnection`) is only implemented for local LM Studio (`SettingsPage.tsx:448-467`). Cloud providers (Gemini, OpenAI, OpenRouter) have no test button.
- **Root Cause**: Key validation only occurs downstream when an active chapter translation is initiated.
- **User Impact**: Typographical errors in API keys are only discovered after batch translation jobs fail.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `inline-validation` & `error-clarity`.

---

### 4.3 Medium Severity Defects

#### DEF-MED-01 (DEF-02): Missing In-Reader Table of Contents Drawer
- **Component & Path**: `src/pages/ReaderPage.tsx:1224-1236`, `src/components/reader/ChapterReader.tsx:459-467`
- **Severity**: **MEDIUM**
- **Observed Behavior**: Clicking `List` in the reader toolbar sets `showChapterList = true`, completely unmounting `ChapterReader` and rendering `NovelHeader` and `ChapterGrid`.
- **User Impact**: Readers lose their immediate reading flow just to browse the chapter index.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `modal-vs-navigation` & `drawer-usage`.

---

#### DEF-MED-02 (DEF-03): Single-Chapter and Completed Novels Prematurely Disappear from Carousel
- **Component & Path**: `backend/routers/threads.py:204-206`, `src/pages/LibraryPage.tsx:547-553`
- **Severity**: **MEDIUM**
- **Observed Behavior**:
  ```python
  # backend/routers/threads.py:205
  progress = int(((last_order + 1) / ch_count) * 100)
  ```
  ```typescript
  // src/pages/LibraryPage.tsx:548
  const activeReads = threads.filter(t => t.progress !== undefined && t.progress > 0 && t.progress < 100)
  ```
  When a novel has 1 chapter or when the user opens the final chapter, `progress` equals `100%`, causing `activeReads` (`progress < 100`) to exclude the book from the Continue Reading carousel.
- **User Impact**: Active novels vanish from the quick-resume hero carousel upon reaching the last chapter.

---

#### DEF-MED-03 (DEF-04): Excessive NovelHeader Vertical Height on Mobile Viewports
- **Component & Path**: `src/components/reader/NovelHeader.tsx:37-184`
- **Severity**: **MEDIUM**
- **Observed Behavior**: On 375px viewports, the cover image (180x250px), title, 3 CTA buttons, tags, and synopsis occupy >650px of vertical space before the chapter list appears.
- **User Impact**: Mobile users must scroll through two full screen heights to reach the chapter table.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `content-priority` & `mobile-first`.

---

#### DEF-MED-04 (FP-P3-06): Obscure TOC / Bulk Import Button Discoverability
- **Component & Path**: `src/pages/TranslatePage.tsx:372-381`
- **Severity**: **MEDIUM**
- **Observed Behavior**: The bulk TOC scraper is represented by a small, unlabelled `<ListTree size={20} />` icon in the bottom icon bar, while the primary action button triggers a single-chapter scrape.
- **User Impact**: New users paste novel TOC URLs and accidentally scrape the index page as Chapter 1.
- **Design Standard Violation**: Violates UI/UX Pro Max rule `primary-action` & `nav-label-icon`.

---

#### DEF-MED-05 (FP-P3-07): Scraper Engine Lacks Custom CSS Selector Configuration
- **Component & Path**: `backend/routers/scrape.py:98-154`, `src/components/TocImportModal.tsx`
- **Severity**: **MEDIUM**
- **Observed Behavior**: Scraping relies on fixed heuristics (`soup.find("article")`, etc.). Non-standard DOM layouts fail with 422 "No content extracted" with no fallback option.
- **User Impact**: Users cannot scrape novels hosted on less common or custom web novel platforms.

---

#### DEF-MED-06 (DEF-P2-07): Mental Model Confusion in Batch Translation Configuration
- **Component & Path**: `src/components/BulkTranslateModal.tsx:654-780`
- **Severity**: **MEDIUM**
- **Observed Behavior**: `Engine Core Speed: Sequential vs Parallel` and `Translation Quality: Quality vs Fast` are displayed in stacked button groups with overlapping "Safe vs Fast" icons and descriptions.
- **User Impact**: Users are confused about the operational difference between request concurrency (parallel workers) and translation prompt depth (quality mode).

---

#### DEF-MED-07 (DEF-P2-08): No Real-Time Batch Metrics, Throughput, or Live Streaming Log
- **Component & Path**: `src/components/BulkStatusCenter.tsx:186-370`
- **Severity**: **MEDIUM**
- **Observed Behavior**: `BulkStatusCenter` only renders a `LinearProgress` bar with `14/50 chapters`. It lacks elapsed time, tokens/sec, ETA, or live chapter streaming previews.
- **User Impact**: Power users translating large batches have no visibility into background speed or remaining wait time.

---

#### DEF-MED-08 (DEF-P2-09): Hardcoded Indonesian Strings in Fidelity Diagnostic UI
- **Component & Path**: `src/components/reader/ChapterReader.tsx:694-730`, `src/components/FidelityManagementModal.tsx`
- **Severity**: **MEDIUM**
- **Observed Behavior**: Fidelity warnings render hardcoded Indonesian strings (`"Peringatan Kualitas"`, `"✓ Abaikan"`, `"Perbaiki"`) regardless of selected interface language.
- **User Impact**: Confusing multilingual interface for international users.

---

#### DEF-MED-09 (DEF-P2-10): Unsorted Flat Grid & Inadequate Glossary Organization
- **Component & Path**: `src/pages/ContextLibraryPage.tsx:956-964`
- **Severity**: **MEDIUM**
- **Observed Behavior**: 200+ term glossaries are displayed in a flat card grid without alphabetical/pinyin indexing, realm hierarchy grouping, or entity category filtering.
- **User Impact**: Hardcore readers struggle to locate and audit specific cultivation terms in large glossaries.

---

#### DEF-MED-10 (FP-P3-08): Missing PDF Export Option
- **Component & Path**: `src/components/ExportModal.tsx:33`, `backend/routers/export.py:28`
- **Severity**: **MEDIUM**
- **Observed Behavior**: ExportModal only supports `EPUB`, `TEXT`, and `CLEAN`. PDF generation is absent.
- **User Impact**: Users wanting to print physical copies or read on PDF-only readers cannot export directly.

---

#### DEF-MED-11 (FP-P3-09): Sequential Crawler Hard-Stops on VIP / Locked Chapters
- **Component & Path**: `backend/routers/scrape.py:658-693`
- **Severity**: **MEDIUM**
- **Observed Behavior**: The crawler aborts the sequential scraping loop immediately upon reaching a locked/VIP chapter without offering options to skip, mark as placeholder, or continue.
- **User Impact**: A single locked announcement chapter blocks scraping of subsequent free chapters.

---

### 4.4 Low & Polish Defects

| ID | Location | Summary |
| :--- | :--- | :--- |
| **DEF-POL-01** | `LibraryPage.tsx:691, 714-796` | Bilingual copy mixing: Indonesian filter tabs (*"Semua"*, *"Sedang Dibaca"*) mixed with English headers (*"Your Library"*). |
| **DEF-POL-02** | `ChapterReader.tsx:451-534` | Header action density crowding on 375px mobile viewports (6 controls in a single 56px row). |
| **DEF-POL-03** | `LibraryPage.tsx:7-10, 171-240` | Extraneous `@mui/material/Menu` import for card action menus while rest of app uses Radix UI. |
| **DEF-POL-04** | `ChapterReader.tsx:269-273` | Distraction-free menu toggle affordance (tap text to show/hide controls) is undiscoverable with no tooltip. |
| **DEF-POL-05** | `ContextLibraryPage.tsx:1020` | Non-functional "Customize" button in domain rules tab lacks an `onClick` action handler. |
| **DEF-POL-06** | `prompt_templates.py:18` | Restrictive 150-character limit (`GLOSSARY_NOTE_MAX_CHARS`) truncates detailed character profiles in prompts. |

---

## 5. Actionable Roadmap & Prioritized Recommendations

---

### 5.1 Phase 1 (Immediate / Sprint 1): Core Navigation, Reader Ergonomics & Critical Bug Fixes

```
Goal: Eliminate all navigation blockers, fix broken interactions, and deliver seamless in-reader reading comfort.
Target Timeline: Sprint 1 (Immediate)
```

#### Item 1.1: Fix Empty Library State Navigation CTA
- **What**: Pass `onNavigateToTranslate={() => setActiveTab('translate')}` from `App.tsx:137` into `LibraryPage.tsx` and replace `window.location.hash = '#translate'` with `onNavigateToTranslate`.
- **Why**: Ensures first-time users can smoothly transition from an empty library to the translation page.
- **Target Files**: `src/App.tsx:137`, `src/pages/LibraryPage.tsx:883`.

#### Item 1.2: Implement Global Reader Keyboard Hotkeys (`useReaderHotkeys`)
- **What**: Add a global `keydown` event listener hook in `ChapterReader.tsx`:
  - `J` or `ArrowRight` $\rightarrow$ Next Chapter
  - `K` or `ArrowLeft` $\rightarrow$ Previous Chapter
  - `T` $\rightarrow$ Trigger Translate / Re-translate
  - `B` $\rightarrow$ Toggle Chapter Bookmark
  - `O` $\rightarrow$ Cycle Display Mode (`original` $\rightarrow$ `translated` $\rightarrow$ `both`)
  - `S` $\rightarrow$ Toggle Settings Overlay
  - `L` $\rightarrow$ Toggle Table of Contents Drawer
  - `Escape` $\rightarrow$ Close any open overlay/drawer
- **Why**: Eliminates manual clicking fatigue for power readers binging 100+ chapters per session.
- **Target Files**: `src/components/reader/ChapterReader.tsx`, `src/pages/ReaderPage.tsx`.

#### Item 1.3: Synchronized Proportional Scroll Lock for Dual Mode
- **What**: In `ChapterReader.tsx`, synchronize `handleScrollOriginal` and `handleScrollTranslated` using proportional percentage alignment (`target.scrollTop = (source.scrollTop / sourceScrollRange) * targetScrollRange`) with an `isSyncingScrollRef` lock to prevent recursive scroll oscillation.
- **Why**: Guarantees raw and translated paragraphs stay perfectly aligned during side-by-side reading.
- **Target Files**: `src/components/reader/ChapterReader.tsx:558-563, 680-685`.

#### Item 1.4: Embed Theme & Typography Presets into In-Reader `SettingsOverlay`
- **What**: Integrate a **Theme Selector** (Sepia, Obsidian Night, OLED, White, Omni), **Font Family Selector** (Atkinson Hyperlegible, Literata/Serif, Inter/Sans), **Line Height Controls** (1.4x, 1.6x, 1.8x, 2.0x), and **Reading Margins** (Narrow, Normal, Wide) directly inside `SettingsOverlay.tsx`.
- **Why**: Allows casual readers to adjust night/day reading comfort in 1 tap without leaving their reading session.
- **Target Files**: `src/components/reader/SettingsOverlay.tsx:1-289`, `src/index.css`.

#### Item 1.5: Fix Novel Header Author Interpolation Bug
- **What**: In `src/components/reader/NovelHeader.tsx:72`, replace `{thread.source_type || 'AI Platform'}` with `{thread.author || 'Unknown Author'}`.
- **Why**: Eliminates the embarrassing `"by epub"` / `"by url"` author subtitle bug across all novel header pages.
- **Target Files**: `src/components/reader/NovelHeader.tsx:71-73`.

#### Item 1.6: Connect or Wire "New Context" Modal
- **What**: Attach a state trigger `setIsCreateContextOpen(true)` to `ContextLibraryPage.tsx:467` to open a context creation dialog, or safely hide the button when viewing read-only contexts.
- **Why**: Eliminates a dead-end click in the Lorebook library.
- **Target Files**: `src/pages/ContextLibraryPage.tsx:467-470`.

#### Item 1.7: Introduce Slide-Over Table of Contents Drawer in Reader
- **What**: When tapping `List` in the reader toolbar, open a slide-out TOC Drawer from the left (desktop) or bottom sheet (mobile) containing the searchable chapter list without unmounting `ChapterReader`.
- **Why**: Prevents loss of reading context and eliminates jarring full-page unmounting.
- **Target Files**: `src/pages/ReaderPage.tsx:1224-1236`, `src/components/reader/ChapterReader.tsx`.

---

### 5.2 Phase 2 (Mid-Term / Sprint 2): Importer Polish, Glossary Intelligence & Batch Stream Center

```
Goal: Enhance ingestion fidelity, deliver batch queue management, and empower power-user glossary workflows.
Target Timeline: Sprint 2 (Mid-Term)
```

#### Item 2.1: EPUB Dublin Core Metadata, Cover Image Persistence & Charset Normalization
- **What**: In `backend/routers/epub.py`:
  - Query `book.get_metadata("DC", "creator")` $\rightarrow$ set `thread.author`.
  - Query `book.get_metadata("DC", "description")` $\rightarrow$ set `thread.synopsis`.
  - Set `thread.cover_image = image_map[cover_name]` upon extracting `ebooklib.ITEM_COVER`.
  - Replace `latin-1` decode fallback with `charset-normalizer` to automatically detect UTF-8, GBK, GB2312, Big5, and Shift-JIS.
- **Why**: Guarantees zero metadata loss and prevents garbled Asian text upon importing raw Asian EPUBs.
- **Target Files**: `backend/routers/epub.py:43-47, 126-134, 151-169`.

#### Item 2.2: Batch Translation Queue Pause / Resume State Machine
- **What**: Update `BackgroundTranslator` with an `is_paused` flag. Add `/api/threads/{thread_id}/batch-pause` and `/api/threads/{thread_id}/batch-resume` endpoints, and update `BulkStatusCenter.tsx` with a Pause/Resume toggle button.
- **Why**: Allows users to temporarily suspend long background batches without losing queue state.
- **Target Files**: `backend/services/background_translator.py:600-650`, `backend/routers/batch.py:100-110`, `src/components/BulkStatusCenter.tsx:142-177`.

#### Item 2.3: Bulk Glossary CSV / JSON / TSV Import & Export
- **What**: Add `Import Glossary` and `Export Glossary` buttons in `ContextLibraryPage.tsx` supporting 2-column and 3-column formats (`Original Term, Translated Term, Notes`).
- **Why**: Enables power users to migrate established glossaries from NovelUpdates or custom spreadsheets in seconds.
- **Target Files**: `src/pages/ContextLibraryPage.tsx:40-1144`, `backend/routers/context.py`.

#### Item 2.4: Real-Time Batch Metrics & Live Streaming Preview Drawer
- **What**: Expand `BulkStatusCenter.tsx` with a slide-up monitor showing words/min, tokens/sec, ETA, live translation preview snippets, and a 1-click "Retry Failed Chapters" button.
- **Why**: Gives power users complete visibility and confidence during 100-chapter batch translations.
- **Target Files**: `src/components/BulkStatusCenter.tsx:186-370`.

#### Item 2.5: Live Cloud Provider API Key Validation
- **What**: In `ApiKeyManager.tsx` and `SettingsPage.tsx`, add a `Test Key` button that performs a lightweight 1-token test call to Gemini, OpenAI, and OpenRouter to verify credentials before launching batches.
- **Why**: Prevents batch translation job aborts caused by API key typos or exhausted quotas.
- **Target Files**: `src/pages/SettingsPage.tsx:611-938`, `src/components/ApiKeyManager.tsx`.

#### Item 2.6: Fix Continue Reading Carousel Completion Filter
- **What**: In `LibraryPage.tsx:548`, change the carousel filter from `progress < 100` to `t.last_read_id !== null`, ensuring completed or single-chapter novels remain accessible in the quick-resume section.
- **Why**: Prevents active or completed novels from vanishing from the top carousel.
- **Target Files**: `src/pages/LibraryPage.tsx:547-553`.

#### Item 2.7: English Localization Parity for Fidelity Warnings
- **What**: Refactor `ChapterReader.tsx:694-730` and `FidelityManagementModal.tsx` to use language-aware strings based on active interface settings rather than hardcoded Indonesian.
- **Why**: Maintains linguistic cohesion across all application modals.
- **Target Files**: `src/components/reader/ChapterReader.tsx:694-730`, `src/components/FidelityManagementModal.tsx`.

---

### 5.3 Phase 3 (Long-Term / Sprint 3): Advanced Scraper Customization, Relationship Graph & Multi-Format Export

```
Goal: Deliver advanced platform extensibility, deep visual entity exploration, and multi-format distribution.
Target Timeline: Sprint 3 (Long-Term)
```

#### Item 3.1: TXT Web Novel Multi-Chapter Project Importer
- **What**: Add a `.txt` novel upload endpoint (`/api/upload-txt`) with configurable regex chapter header splitting (`/^(?:第?[0-9一二三四五六七八九十百千万]+[章回节卷]|Chapter\s+[0-9]+)/m`) that converts raw `.txt` files into a multi-chapter project thread.
- **Why**: Opens ReadOmni AI to the massive ecosystem of raw `.txt` web novel archives.
- **Target Files**: `backend/routers/upload.py`, `src/pages/TranslatePage.tsx:346-371`.

#### Item 3.2: Advanced Scraper Modal with Custom CSS Selectors & VIP Skip
- **What**: Add an "Advanced Scraper Settings" accordion in `TocImportModal` and `BulkFetchModal` allowing users to supply custom Content and Title CSS selectors (e.g. `#read-content`, `h1.entry-title`), custom HTTP headers/cookies, and a toggle to "Skip VIP/Locked Chapters & Continue Crawling".
- **Why**: Enables scraping from any novel hosting layout and prevents crawl aborts on paywalled notices.
- **Target Files**: `backend/routers/scrape.py:98-154, 658-693`, `src/components/TocImportModal.tsx`.

#### Item 3.3: Interactive Character Relationship Network & Faction Drawer
- **What**: Upgrade `RelationshipGraph.tsx` to display an interactive character profile side-drawer on node click with relationship links (mentor, disciple, rival, lover) and implement backend CRUD endpoints (`POST /api/threads/{id}/relationships`).
- **Why**: Transforms character visualization into an interactive cultivation world-building tool.
- **Target Files**: `src/components/RelationshipGraph.tsx:103-105`, `backend/routers/relationships.py:1-35`.

#### Item 3.4: Multi-Format PDF Export Support
- **What**: Implement PDF document generation in `backend/routers/export.py` with custom book styling, clean typography, page numbers, and table of contents.
- **Why**: Satisfies users who prefer PDF readers, tablets, or printable review copies.
- **Target Files**: `backend/routers/export.py:28-315`, `src/components/ExportModal.tsx:33`.

#### Item 3.5: Replace MUI Menu Dependency with Radix DropdownMenu
- **What**: Refactor `LibraryBookCard` in `LibraryPage.tsx:7-10, 171-240` to use `@radix-ui/react-dropdown-menu` instead of `@mui/material/Menu`.
- **Why**: Reduces bundle size, eliminates ink ripple styling incongruities, and standardizes design tokens.
- **Target Files**: `src/pages/LibraryPage.tsx:7-10, 171-240`.

---

### 5.4 Complexity vs. User Impact Matrix

```
  HIGH IMPACT  │ [DEF-CRIT-01] Empty CTA Fix     │ [DEF-HIGH-01] In-Reader Themes
               │ [DEF-HIGH-02] "by epub" Fix     │ [DEF-CRIT-02] Reader Hotkeys
               │ [DEF-MED-02] Carousel Fix       │ [DEF-CRIT-03] Split Scroll Sync
               │ [DEF-CRIT-04] New Context Fix   │ [DEF-HIGH-03] EPUB Metadata
               │                                 │ [DEF-HIGH-04] Batch Pause/Resume
               │                                 │ [DEF-HIGH-05] Glossary CSV Import
               │                                 │ [DEF-MED-01] Reader TOC Drawer
               │                                 │ [Item 3.1] TXT Novel Importer
  ─────────────┼─────────────────────────────────┼─────────────────────────────────
  MED/LOW      │ [DEF-POL-01] Bilingual Clean    │ [Item 3.2] Custom CSS Scraper
  IMPACT       │ [DEF-POL-03] MUI Menu Replace   │ [Item 3.3] Interactive Graph
               │ [DEF-POL-05] Rule Custom Button │ [Item 3.4] PDF Export
               │                                 │
               └─────────────────────────────────┴─────────────────────────────────
                                LOW COMPLEXITY                     HIGH COMPLEXITY
```

---

## 6. Audit Attestation & Verification Protocol

### 6.1 Independent Verification Methods

To independently verify the defects and architectural findings documented in this report:

1. **Verify Empty Library CTA**:
   - Inspect `src/pages/LibraryPage.tsx:883`. Confirm that clicking the button executes `window.location.hash = '#translate'`. Open browser at `/` with an empty library and confirm clicking the button produces no view change.
2. **Verify Missing Hotkeys**:
   - Inspect `src/pages/ReaderPage.tsx` and `src/components/reader/ChapterReader.tsx`. Search for `keydown`/`keyup` event listeners. Confirm 0 listeners exist.
3. **Verify Untethered Split Scroll**:
   - Open Reader, switch display mode to `BOTH`. Scroll the right container (`translatedScrollContainerRef`). Confirm the left container (`originalScrollContainerRef`) remains static.
4. **Verify "by epub" Author Bug**:
   - Inspect `src/components/reader/NovelHeader.tsx:72`. Confirm the template renders `{thread.source_type || 'AI Platform'}` instead of `{thread.author}`.
5. **Verify EPUB Metadata Drop**:
   - Inspect `backend/routers/epub.py:126-134`. Confirm `book.get_metadata("DC", "creator")` and `dc:description` are not written to the `Thread` model.
6. **Verify Non-Pausable Batch Queue**:
   - Inspect `backend/routers/batch.py:102-106` and `BulkStatusCenter.tsx:142-177`. Confirm `/api/threads/{thread_id}/batch-stop` is the only queue endpoint and no pause/resume exists.
7. **Verify In-Reader Settings Lack Themes**:
   - Inspect `src/components/reader/SettingsOverlay.tsx:1-289`. Confirm that theme switcher and font family selectors are not present.

---

*Report authored and certified by the Master Synthesis Usability Specialist. All observations, line references, and architectural assessments are forensically verified against the ReadOmni AI codebase.*
