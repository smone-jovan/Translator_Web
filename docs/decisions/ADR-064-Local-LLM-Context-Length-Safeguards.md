# ADR-064: Local LLM Context Length Safeguards and Fast/Quality TDD Verification

## Status
Accepted

## Date
2026-06-07

## Context
A critical bug occurred when using local LLMs (e.g., Qwen 3-4B via LM Studio) where the system attempted to generate translation prompts that exceeded the model's physical context length (`n_ctx`). 

The crash manifested as: `The number of tokens to keep from the initial prompt is greater than the context length (n_keep: 16324>= n_ctx: 14592)`.
This was caused by two compounding factors:
1. **Mathematical Payload Error:** The system hardcoded `max_tokens: 10000` (or `22000`) for API requests, tricking Llama.cpp into reserving memory it didn't have.
2. **Context Bloat:** The System Prompt itself (`n_keep`) ballooned to 16,324 tokens due to massive user-provided texts in `GlobalContext`, `ThreadContext`, and `Glossary Notes` (which are injected into the prompt).

Previously, the system had `fast` and `quality` translation modes. `fast` mode was supposed to limit Glossary entries to 10 to protect context windows. However, because it did not limit the *string length* of individual entries or the main context fields, a single massive entry could still crash the local LLM, bypassing the intended protection.

## Decision
1. **API Payload Fix:** For `LMStudioAdapter`, if `max_tokens` > 4096, it is clamped to `-1`. In the Llama.cpp engine, `-1` instructs the model to dynamically calculate and use the remaining context window rather than pre-allocating a fixed, impossible amount.
2. **Hard-Truncation for Safety Bounds:** To prevent raw prompt bloat, strict string slicing is applied to user-provided context before injection:
   - `GlobalContext` & `StyleGuide`: Capped at 1,000 characters.
   - `ThreadContext`: Capped at 2,000 characters.
   - `Lorebook Notes`: Capped at 150 characters per entry.
3. **TDD Verification for Modes:** To ensure that the hard-truncation does not invalidate the `fast` and `quality` logic (as feared by users), a formal TDD suite (`test_context_engine.py`) is mandated to verify that:
   - `fast` mode strictly caps entries to 10 and excludes `style_guide`.
   - `quality` mode respects the user's `max_context_terms` and includes the `style_guide`.
   - The safety truncations apply consistently across both modes to prevent hardware crashes without destroying semantic meaning.

## Consequences
- Local LLMs with small context windows (8K-16K) can now safely operate without crashing.
- Users who paste massive essays into the `ThreadContext` will find their text silently truncated to 2,000 characters.
- The distinction between `fast` and `quality` modes is preserved and scientifically verified via integration tests.
- Extracted glossary notes are forced to remain concise.
