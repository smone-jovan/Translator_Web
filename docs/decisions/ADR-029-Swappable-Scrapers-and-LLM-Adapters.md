# ADR-029: Swappable Scrapers and LLM Provider Adapters

## Status
Accepted & Implemented (AI Translation Adapters & Settings Sync Phase)

## Date
2026-05-18

## Context
ReadOmni AI's core functionality relies heavily on external data sources:
1. **Metadata Scrapers:** Fetching novel summaries, authors, cover art, tags, and genres from platforms like Novel Updates and SFACG.
2. **AI Translation Providers:** Sending context prompts and chapter contents to LLMs (currently a local LM Studio instance at `localhost:1234`) for high-fidelity translation, glossary extraction, and title formatting.

Currently, these subsystems are implemented as shallow modules:
- The **Scraping** logic is tightly integrated into route handlers (`scrape.py`), where cookie management, custom HTTP headers, site-specific HTML parsers (`BeautifulSoup` selectors), and Yahoo search match algorithms are executed sequentially inside the route. 
- The **AI Provider** logic (`ai_provider.py`) is hardcoded to target mock-OpenAI endpoints, forcing route files to coordinate fallbacks, custom streaming deltas, and OpenAI-specific client parameters directly.

This creates architectural friction:
- **Poor Locality:** If a scraper's selector breaks, or a new LLM provider (like Anthropic/Gemini) needs to be integrated, changes must be made within core router paths.
- **Low Leverage:** Callers must manage specific details of the target network client or site DOM.
- **Poor AI Navigability:** Future AI agents asked to add new scrapers or LLM models must read massive, procedural router scripts and rewrite database updates and network wrappers, increasing the risk of introducing regression bugs in critical components like the volume transition guardian.

## Decision
We will refactor these subsystems in the next update (not now, but in the next structural phase) to introduce clean **seams** and structured **adapters** following the Port-and-Adapter (Hexagonal) pattern. This is specifically optimized to be highly testable, decoupled, and extremely easy for both human developers and future AI agents to extend.

### 1. The Metadata Scraper Adapter Pattern
We will isolate all scraping logic behind a deep **Metadata Scraper** module. 
- **The Seam (Interface):** We will define a strict `BaseScraperAdapter` abstract interface:
  ```python
  class BaseScraperAdapter(ABC):
      @abstractmethod
      async def search_novels(self, query: str) -> list[ScrapeSearchResult]: ...

      @abstractmethod
      async def scrape_metadata(self, url: str) -> ScrapedNovelMetadata: ...
  ```
- **The Adapters:** Site-specific scrapers will be written as clean, isolated adapters implementing this interface:
  - `NovelUpdatesAdapter`
  - `SFACGAdapter`
- **The Engine (Depth):** A central `MetadataScraperEngine` will act as a deep coordinator, choosing the correct adapter based on the query pattern (URL vs. title search), performing similarity matching, and returning a unified Pydantic schema to the router.

### 2. The Swappable AI Provider Adapter Pattern
We will decouple route files from direct mock-OpenAI dependencies.
- **The Seam (Interface):** We will define a standard `BaseAIProviderAdapter` abstract interface:
  ```python
  class BaseAIProviderAdapter(ABC):
      @abstractmethod
      async def chat_completion(self, system_prompt: str, user_prompt: str, config: AIConfig) -> str: ...

      @abstractmethod
      async def stream_chat(self, system_prompt: str, user_prompt: str, config: AIConfig) -> AsyncGenerator[str, None]: ...
  ```
- **The Adapters:** Different model APIs will be encapsulated within concrete adapters:
  - `LMStudioAdapter` (for local mock-OpenAI fallback client)
  - `OpenAIAdapter` (for authentic cloud-based GPT models)
  - `AnthropicAdapter` (for native Claude Claude-3.5-sonnet streaming)
- **The Factory:** A central `AIProviderFactory` will resolve the active adapter dynamically based on the server-synchronized `GlobalSetting` config.

---

## Consequences

### 🤖 Why this is extremely easy for AI to work on and expand:
1. **Single-File Locality:** If a developer or an AI is tasked with "Add Syosetu scraping support" or "Add Anthropic LLM provider," the implementation is 100% localized to a new file (e.g. `syosetu_adapter.py` or `anthropic_provider.py`). The AI does not need to read, understand, or touch routing files, database transactions, or volume numbering guards.
2. **Strict Typings and Schemas:** Pydantic models (`ScrapedNovelMetadata`, `AIConfig`) serve as a robust compiler/linter gate. The AI immediately gets clear type errors if it returns incorrect fields, preventing silent runtime crashes.
3. **Seam-Level Unit Testing:** The interface becomes the test surface. AI agents can easily write isolated tests passing static HTML text fixtures directly into `NovelUpdatesAdapter` without performing real HTTP calls, or mock network streams to verify the `AnthropicAdapter` chunk parser.

### Consequences on the codebase:
- **Router Simplification (High Leverage):** The endpoints in `scrape.py` and `translate.py` will shrink to a fraction of their current size. They will call a single coordinating method and hand the structured output directly to the SQLAlchemy session or SSE connection.
- **Hypothetical Seams become Real Seams:** With both the scraper and the AI provider utilizing multiple concrete adapters, the codebase transitions to a robust production pattern where all network-bound complexity is cleanly isolated.

---

## Implementation Details (AI Translation Port & Adapter)
Implemented on **2026-05-18** as part of the Phase 14 structural upgrade.

### 1. Concrete Adapter Modules
All adapters implement [BaseAIProviderAdapter](file:///d:/code_xI/Translator_Web/backend/services/ai/base.py):
*   [LMStudioAdapter](file:///d:/code_xI/Translator_Web/backend/services/ai/lm_studio.py): Targets the local offline LM Studio server on standard ports (default: `http://localhost:1234`).
*   [OpenAIAdapter](file:///d:/code_xI/Translator_Web/backend/services/ai/openai.py): Integrates with cloud-based OpenAI HTTP endpoints (`https://api.openai.com/v1`).
*   [GeminiAdapter](file:///d:/code_xI/Translator_Web/backend/services/ai/gemini.py): Directly communicates with Google Gemini API via its OpenAI-compatible HTTP interface without adding bulky external Python package dependencies.

### 2. Provider Resolution Factory
Implemented in [AIProviderFactory](file:///d:/code_xI/Translator_Web/backend/services/ai/factory.py):
*   Resolves the target adapter dynamically using backend database settings.
*   Bypasses local url overrides when a custom provider like Google Gemini or OpenAI is explicitly selected.

### 3. Secure API Key Storage & Synchronization
*   Secrets are stored in the server-side, git-ignored `backend/.env` file via [secrets.py](file:///d:/code_xI/Translator_Web/backend/services/ai/secrets.py).
*   API keys sync seamlessly across client terminals (Laptop, iPhone, Android) on the same WiFi network without exposure to Git commits.

### 4. Interactive Settings UI
*   Incorporated a premium card-based layout in the front-end Settings page to toggle between **LM Studio**, **OpenAI**, and **Google Gemini** with inline API key visibility toggles, dynamic model selectors, and personal free-tier documentation guides.

### 5. Dynamic RPM Safety Guard & Model Expansion (Google AI Studio Free Tier Optimization)
Implemented on **2026-05-18** to allow safe, hands-off background and prefetch translations using Google AI Studio Free Tier without hitting HTTP 429 Rate Limit Exceeded boundaries.
*   **Model List Expansion:** Added native frontend and backend support for premium free-tier options including:
    *   `gemini-3.1-flash-lite` (15 RPM / 500 Daily Quota) - Recommended default.
    *   `gemma-4-31b` (15 RPM / 1,500 Daily Quota).
    *   `gemini-3-flash` (5 RPM / 20 Daily Quota).
    *   `gemini-2.5-flash-lite` (10 RPM / 20 Daily Quota).
    *   `gemini-2.5-flash` (5 RPM / 20 Daily Quota).
*   **Dynamic Pacing Throttler:** Built an elegant async sleep guard in the background translator pipeline. When a translation request is initiated, the engine checks the target model's RPM specifications and automatically introduces a localized dynamic pacing delay between API calls:
    *   `gemini-3.1-flash-lite` & `gemma-4-31b`: **4.2 seconds** delay (safety padded for 15 RPM).
    *   `gemini-2.5-flash-lite`: **6.2 seconds** delay (safety padded for 10 RPM).
    *   `gemini-3-flash`, `gemini-2.5-flash`, and others: **12.2 seconds** delay (safety padded for 5 RPM).
    *   Local/Custom models: **1.0 second** delay.
This prevents daily rate exhaustion under Soft Load sequential prefetching and ensures bulk operations run reliably in the background indefinitely ("ditinggal").
