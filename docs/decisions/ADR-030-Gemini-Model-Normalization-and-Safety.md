# ADR-030: Gemini Model Normalization and Safety Filter Handling

## Status
Accepted

## Date
2026-05-18

## Context
Our application supports swappable LLM adapters (ADR-029) including local offline models (LM Studio), OpenAI, and Google Gemini.
A core challenge arises when utilizing the Gemini provider:
1. **Model Name Ambiguity:** Users often input shorthand or generalized model names (e.g., `gemini-3-flash`, `gemma-4-31b`, `gemini-1.5-pro`) in the frontend UI or inherit model configurations saved previously under LM Studio. However, the Gemini API requires precise model endpoint strings (e.g., `gemini-3-flash-preview`, `gemma-4-31b-it`, `gemini-1.5-pro-latest`) and throws a generic `HTTP 404: Model not found` error if an exact match isn't provided.
2. **Safety Filter Responses:** The Gemini API has strict content filters (especially affecting the `gemma-4-31b-it` instruction-tuned models). When a web novel's text violates safety filters, the Gemini API responds with `HTTP 200` but completely omits the `message` key from the `choices` block, replacing it with a `finish_reason` such as `content_filter: PROHIBITED_CONTENT`. The previous implementation assumed the `message` key was always present on a `200 OK` response, resulting in a cryptic backend crash (`KeyError: 'message'`).

## Decision
1. **Intelligent Model Normalization (Backend Adapter Layer):**
   - The `GeminiAdapter` initialization process has been enhanced to intercept incoming model names.
   - We implemented a direct mapping strategy:
     - `gemma-4-31b` -> `gemma-4-31b-it`
     - `gemini-3-flash` -> `gemini-3-flash-preview`
     - `gemini-3.1-flash-lite` -> `gemini-3.1-flash-lite-preview`
     - (And similar mappings for legacy/experimental models).
   - This mapping guarantees that user-selected UI models are seamlessly translated to strict Gemini API identifiers before the network request is initiated.

2. **Database Fallback for Incompatible Models:**
   - If the active provider is Gemini but the requested model is fundamentally incompatible (e.g., a local model like `qwen/qwen3-4b-2507`), the `AIProviderFactory` intercepts the request, ignores the incompatible model, and falls back to the database-configured `gemini_model`.

3. **Robust Finish Reason Parsing (Safety Filters):**
   - We updated the `GeminiAdapter.chat_completion` logic. Before attempting to access `data["choices"][0]["message"]["content"]`, we check if `"message"` exists.
   - If `"message"` is absent but `"finish_reason"` is present, we raise a highly specific exception: `Request blocked or stopped by Gemini API filters. Finish reason: {reason}`.
   - Streaming endpoints (`GeminiAdapter.stream_chat`) were also hardened with `KeyError` try-catch blocks over parsed deltas, ensuring graceful degradation if specific streamed chunks omit expected keys.

## Alternatives Considered

### Frontend-side Normalization
- **Pros:** Prevents incorrect model names from ever reaching the backend API.
- **Cons:** Unreliable. Legacy configurations saved in the database or `localStorage` would bypass the mapping. It also complicates the UI logic unnecessarily.
- **Rejected:** The backend adapter is the most secure and appropriate layer for provider-specific data transformation.

### Generic Catch-All Exception Handling for 'message' Missing
- **Pros:** Quick fix to prevent a 500 internal server error.
- **Cons:** A generic `KeyError` or "Invalid Response" error obscures the real reason (safety filter). Without knowing the `finish_reason`, the user cannot rectify the issue (e.g. by altering the text chunk or prompt).
- **Rejected:** Transparency is essential; the frontend must be aware if a prompt was explicitly blocked for content violation.

## Consequences
- **High Compatibility:** Users can seamlessly use shorthand model names like `gemma-4-31b` or `gemini-3-flash` without seeing 404 errors.
- **Improved Observability:** Instead of mysterious backend crashes during context extraction on violent/explicit novel chapters, users (and logs) receive clear `content_filter` block notifications.
- **Decoupled Architecture:** The UI dropdown lists stay clean and simple, completely unaware of the underlying strict API endpoints required by Google.
