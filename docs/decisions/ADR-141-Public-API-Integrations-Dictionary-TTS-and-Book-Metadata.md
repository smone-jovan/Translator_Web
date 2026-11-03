# ADR-141: Public API Integrations — In-Reader Lexical Lookup, Native Text-to-Speech, and Concurrent Library Metadata Auto-Fill

## Status
Accepted

## Date
2026-11-02

## Context
ReadOmni AI (Translator Web) is designed as a web reader and translation workstation for light novels, web novels, and manga. While the platform excels at automated and batch translation, users frequently encountered two reading workflow frictions:
1. **In-Reader Vocabulary Barriers**: Readers reading raw or translated novel chapters in `ReaderPage` lacked convenient inline lookup tools. Looking up foreign words or translated idioms required switching browser tabs, interrupting the immersive reading experience.
2. **Audiobook / Hands-Free Reading Deficiency**: The platform had no built-in accessibility or Text-to-Speech (TTS) capabilities for audio listening.
3. **Sparse Book Cataloging on Manual Import**: When importing TXT or EPUB files via `txt_importer.py` or `epub.py`, book entries in `LibraryPage` frequently had missing authors, genres, synopses, and cover art, creating an unorganized library interface.

Furthermore, project-level safety invariants ([`project-safety-and-architecture.md`](file:///D:/code_xI/Translator_Web/.agent/rules/project-safety-and-architecture.md)) strictly prohibit adding new npm/Python dependencies or modifying lockfiles without explicit approval. All new capabilities had to be implemented using zero-cost, dependency-free public APIs and native web standards.

---

## Decisions

### 1. In-Reader Lexical Popover (Free Dictionary API + CJK Unicode Regex)
- **Component**: [`src/components/reader/DictionaryPopup.tsx`](file:///D:/code_xI/Translator_Web/src/components/reader/DictionaryPopup.tsx) integrated into [`src/components/reader/ChapterReader.tsx`](file:///D:/code_xI/Translator_Web/src/components/reader/ChapterReader.tsx).
- **Service**: Integrated the public `https://api.dictionaryapi.dev/api/v2/entries/en/<word>` endpoint (zero auth, zero quota restrictions).
- **Unicode & CJK Logograph Preservation**:
  - Replaced ASCII-only regex (`^[^\w]+|[^\w]+$`) with Unicode property escape regex:
    ```typescript
    const cleanWord = word.replace(/^[\s\p{P}\p{S}]+|[\s\p{P}\p{S}]+$/gu, "").trim().toLowerCase();
    ```
  - Lowered minimum selection trigger to `length >= 1` to support single-character logographic Asian words (`剑`, `道`, `仙`, `神`).
  - Added graceful 1-click fallback link to Wiktionary (`https://en.wiktionary.org/wiki/<word>`) when words are not found in the English dictionary (e.g. CJK terms, slang, or fantasy cultivation names).

### 2. Client-Side Text-to-Speech Player (Web Speech API + Anti-Cutoff Chunking)
- **Component**: [`src/components/reader/TextToSpeechPlayer.tsx`](file:///D:/code_xI/Translator_Web/src/components/reader/TextToSpeechPlayer.tsx).
- **Engine**: Native browser `window.speechSynthesis` and `SpeechSynthesisUtterance` (zero backend compute, offline-capable).
- **Chromium 15-Second Cutoff Prevention**:
  - Chromium engines suffer from an internal audio buffer freeze when feeding paragraphs longer than 15 seconds.
  - Implemented `cleanTextForSpeech` with sentence boundary splitting supporting Latin and Asian fullwidth punctuation (`。！？\n`).
  - Paragraphs $> 250$ characters are subdivided into sub-chunks of $< 200$ characters:
    ```typescript
    const sentences = trimmed.match(/[^.!?。！？\n]+[.!?。！？]+|\s*[^.!?。！？\n]+$/g) || [trimmed];
    ```
- **Automatic Language & Voice Script Detection**:
  - Dynamically detects chapter script (Japanese Hiragana/Katakana `[\u3040-\u30ff]`, Chinese Hanzi `[\u4e00-\u9fff]`, Korean Hangul `[\uac00-\ud7af]`, Indonesian common words, or English) to route to native voice packs (`ja-JP`, `zh-CN`, `ko-KR`, `id-ID`, `en-US`).
  - Includes playback rate controls ($0.75\times$ to $2.0\times$) and voice selection dropdown.

### 3. Concurrent Library Metadata & Cover Auto-Fill
- **Backend Endpoint**: `GET /api/books/search` in [`backend/routers/threads.py`](file:///D:/code_xI/Translator_Web/backend/routers/threads.py).
- **Parallel Aggregation**: Uses `asyncio.gather` with `return_exceptions=True` to query both **Open Library API** (`openlibrary.org/search.json`) and **Google Books API** (`googleapis.com/books/v1/volumes`) concurrently, cutting latency in half.
- **Defensive Parameter Clamping & Sanitization**:
  - Clamps `limit` to range `[1, 20]`.
  - Sanitizes Google Books image URLs by stripping `&edge=curl` for clean rectangular covers.
- **Frontend Integration**: Added **"Auto-Fill Metadata (Open Library)"** action in [`src/pages/LibraryPage.tsx`](file:///D:/code_xI/Translator_Web/src/pages/LibraryPage.tsx), allowing users to search by book title, review cover previews, synopsis, year, and author, and apply them with one click.

---

## Consequences

### Positive
- **Zero Operating Costs**: Free Dictionary, Open Library, Google Books, and Web Speech APIs require no paid subscriptions or billing setups.
- **No Dependency Footprint**: Implemented without modifying `package.json` or `requirements.txt`.
- **Improved UX**: Users can listen to chapters as audiobooks, look up definitions in-reader, and auto-enrich imported novel covers with high accuracy.
- **Robustness**: 100% CJK-safe regex and chunking avoids crashes or text erasure on Asian web novels.

### Trade-offs & Limitations
- **English-Only Dictionary**: Free Dictionary API only returns definitions for English words; non-English terms rely on the 1-click Wiktionary fallback link.
- **Operating System Voice Availability**: Web Speech API audio fidelity depends on locally installed OS voice packs (e.g., Windows Natural Voices vs Android/iOS voices).
