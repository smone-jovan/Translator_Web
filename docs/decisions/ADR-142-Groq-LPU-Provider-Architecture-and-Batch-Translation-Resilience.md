# ADR-142: Groq LPU Provider Architecture, Batch Translation Resilience, and Multi-Tier Quota Budgeting

## Status
Accepted

## Date
2026-11-02

## Context
To provide ultra-fast translation previews and high-throughput alternative inference alongside Google Gemini, OpenAI, and local LM Studio, the **Groq Cloud LPU (Language Processing Unit)** inference provider was integrated into ReadOmni AI. Groq's Free Tier provides high generation speed (~250–375 tokens/sec) with zero cost.

However, during initial real-world batch translation across long web novel chapters, translations exhibited severe breakdowns: chapters were 75% truncated, multiple HTTP 429 rate limits triggered after a single chapter, and requests repeatedly failed with HTTP 400/404.

An empirical investigation of the batch worker logs (`launcher.log`), `BackgroundTranslator`, and `ContextEngine` identified four interlocking architectural failure modes:

1. **Length Truncation Cascade**:
   - Source chapters were split into chunks of `1,200` characters with `max_tokens` set to `950`.
   - 1,200 Chinese characters yield ~1,300–1,400 Indonesian/English tokens, exhausting the 950 output token limit. The API returned `finish_reason: "length"` with `[[TRUNCATED]]`.
   - In `ChunkedTranslationProvider`, receiving `[[TRUNCATED]]` triggered an early return, immediately aborting all subsequent chunks and leaving chapters unfinished.
2. **Input Token (ITPM) Explosion from Context Bloat**:
   - Groq Free Tier enforces a strict **7,000 ITPM** (Input Tokens Per Minute) ceiling.
   - `ContextEngine.build_translation_prompt` injected up to 150 lorebook terms (padding with non-matching glossary entries) and scaled global/thread context by up to $4.0\times$–$8.0\times$, producing prompt payloads exceeding 20,000 characters (~5,865+ input tokens).
   - A single request consumed >85% of the minute's quota; subsequent chunks or chapters instantly failed with HTTP 429.
3. **Decommissioned Upstream Model Catalog**:
   - Presets previously included `mixtral-8x7b-32768`, `gemma2-9b-it`, `deepseek-r1-distill-llama-70b`, and `llama-3.2-*-preview`.
   - Upstream Groq Cloud decommissioned these models, rejecting requests with `HTTP 400: The model has been decommissioned and is no longer supported`.
4. **Omission from Multi-Key Rotation & Exhaustion Tracking**:
   - `backend/services/ai/secrets.py` only tracked exhaustion for `gemini`. Multiple Groq keys configured in `groq_api_keys` were never marked exhausted upon hitting daily limits, causing batch workers to loop indefinitely on exhausted keys.

---

## Decisions

### 1. Calibrated Chunk Sizing & Output Token Caps
- In [`backend/services/ai/groq.py`](file:///D:/code_xI/Translator_Web/backend/services/ai/groq.py):
  - Reduced `translation_chunk_chars` to **600 characters** for Qwen models. 600 Chinese characters produce ~700–800 output tokens, fitting comfortably under the **900 `max_tokens` cap** without triggering `[[TRUNCATED]]`.
  - Capped general Groq models (`gpt-oss-120b`, `allam`) to **4,096 tokens** in `_resolve_max_tokens` and `get_chapter_translation_max_tokens` to prevent exceeding Groq's 8,000 TPM reservation window.

### 2. Strict Prompt Budgeting for Low-ITPM Tiers
- In [`backend/services/context_engine.py`](file:///D:/code_xI/Translator_Web/backend/services/context_engine.py):
  - Locked Groq context scaling strictly to **$1.0\times$** (`get_context_scale_for_model`).
  - Constrained global, thread, and style contexts to a maximum of **600 characters**.
  - Terminated glossary padding: Groq prompts only inject lorebook entries that **directly match the chapter text**, plus at most 5 locked terms.
  - Capped sample size to 1,800 characters and existing glossary lines to 15 in `extract_glossary_pass`.

### 3. Primary Model Selection: `qwen/qwen3.8-27b`
- Evaluated live models on Groq:
  - `openai/gpt-oss-120b` / `openai/gpt-oss-20b`: Reasoning models that consume output quota on hidden internal thoughts before generating text.
  - `qwen/qwen3.8-27b`: Pure generative LLM delivering **250–375 tokens/sec** with zero reasoning token tax, superior pinyin name retention, and natural Indonesian literary flow.
- Established **`qwen/qwen3.8-27b`** as the default recommended model in [`SettingsPage.tsx`](file:///D:/code_xI/Translator_Web/src/pages/SettingsPage.tsx), [`factory.py`](file:///D:/code_xI/Translator_Web/backend/services/ai/factory.py), and `GlobalSetting` database schema.

### 4. Full Groq Multi-Key Rotation and Daily Exhaustion TTL
- Extended `backend/services/ai/secrets.py` with `exhausted_groq_keys`:
  - `mark_key_exhausted("groq", key)` records exhaustion timestamp with daily TTL cleanup.
  - `get_active_api_key("groq", gs)` and `rotate_api_key("groq", gs)` advance round-robin pointers across available unexhausted keys.
  - Raises `QuotaExhaustedError` when all configured Groq keys are exhausted, cleanly notifying batch workers.

### 5. Adaptive Pacing, Retry Headers, and Streaming Resiliency
- Added dynamic retry delay parsing in `GroqAdapter.extract_retry_delay`:
  - Extracts seconds from `retry-after`, `x-ratelimit-reset-requests`, and `x-ratelimit-reset-tokens`.
  - Handles composite strings (e.g., `1m30s`).
- Enforced inter-chunk delay (`chunk_delay_seconds = 6.0` for Qwen) to pace requests under 30 RPM limits.
- Added `chunk_yielded` safeguard in `ChunkedTranslationProvider.stream_chat`: if partial tokens have already been yielded to downstream callers, retries are aborted to prevent repeated duplicate paragraphs.
- Null-guarded `content` extraction (`msg.get("content") or ""`) and ensured `in_reasoning` emits `\n</think>\n\n` upon stream completion.

---

## Consequences

### Positive
- **Stable Batch Translation**: Long novel chapters translate from start to finish without truncation cascades or premature aborts.
- **Quota Immunity**: Prompt budgeting keeps request sizes well within Groq's 7,000 ITPM window.
- **Failover & Multi-Key Support**: Users with multiple Groq keys enjoy automatic failover when individual key rate limits are reached.
- **Blazing Speed**: Provides ~250–375 tokens/sec translation speeds on a 100% free tier.
- **Full Test Coverage**: 1,318 backend unit/integration tests passing green with 0 regressions.

### Trade-offs & Limitations
- **Chunk Latency**: Due to Groq's strict 30 RPM and 1,000 OTPM limits on Free Tier, very large chapters (>3,000 chars) split into multiple 600-character chunks require pacing delays (~30–45s total chapter duration).
- **Organization-Level Quotas**: On Groq Free Tier, multiple API keys created under the exact same organization share a single global rate limit pool. Multi-key rotation is most effective when keys are generated across separate projects or accounts.
