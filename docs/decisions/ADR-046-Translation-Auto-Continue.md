# ADR-046: Translation Auto-Continue on Truncation

## Status
Accepted

## Date
2026-05-30

## Context
When translating long chapters, the AI provider may hit `max_tokens` and truncate the response mid-sentence. Previously, all three streaming adapters (Gemini, OpenAI, LM Studio) completely ignored `finish_reason` from the API response. A truncated translation was silently saved as "done" with no indication it was incomplete.

Additionally, Gemini's content safety filters can reject chapters with `finish_reason: "prohibited"`, which was also silently ignored — the partial or empty response was saved as a valid translation.

## Decision
Implement a three-layer robustness system for translation output:

### 1. Truncation Detection (`TRUNCATED_MARKER`)
- All streaming adapters now check `finish_reason` in the final SSE chunk.
- When `finish_reason == "length"`, adapters yield a `TRUNCATED_MARKER` sentinel (`"[[TRUNCATED]]"`) at the end of the stream.
- The background translator detects this marker and enters an auto-continue loop.

### 2. Auto-Continue Loop
- When truncation is detected, the translator sends a continuation prompt: the original system prompt + the full translated text so far + a user message asking the AI to continue from where it stopped.
- Maximum 3 continuation rounds per chapter to prevent infinite loops.
- Each round's output is appended to the accumulated translation.
- Periodic saves every 20 chunks ensure partial progress is preserved even if the connection drops.

### 3. Prohibited Content Handling (`PROHIBITED_MARKER`)
- Adapters detect `finish_reason` values in `{"prohibited", "content_filter", "safety", "blocked"}`.
- When detected, yields `PROHIBITED_MARKER` sentinel (`"[[PROHIBITED]]"`).
- The translator resets the chapter to `"idle"` status and returns `False` — no translation is saved.

## Alternatives Considered

### Increase max_tokens globally
- **Pros**: Simple, no code changes needed.
- **Cons**: Wastes tokens on short chapters; some providers have hard limits; doesn't solve the prohibited content issue.
- **Rejected**: Doesn't address the root cause.

### Split chapters into parts for translation
- **Pros**: Guarantees each part fits within token limits.
- **Cons**: Complex chapter splitting logic; may break paragraph boundaries; context loss between parts.
- **Rejected**: Auto-continue is simpler and preserves context.

### Use non-streaming only for long chapters
- **Pros**: Easier to detect truncation (single response object).
- **Cons**: Loses real-time streaming UX; no progress feedback for long translations.
- **Rejected**: Streaming is essential for user experience.

## Consequences
- **Positive:** Long chapters are now fully translated through automatic continuation rounds.
- **Positive:** Prohibited content is handled gracefully — chapter resets to idle instead of storing garbage.
- **Positive:** Users see real-time progress as continuation rounds stream in.
- **Negative/Risk:** Continuation prompts increase API usage (up to 3x for very long chapters).
- **Negative/Risk:** The continuation context (full translated text) may approach context window limits for very long chapters.
