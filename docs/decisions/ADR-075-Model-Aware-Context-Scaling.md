# ADR-075: Model-Aware Context Scaling

## Status
Accepted

## Date
2026-06-13

## Context
Context truncation in `context_engine.py` is hardcoded to aggressive limits:
- `global_context`: 1000 characters
- `thread_context`: 2000 characters
- `style_guide`: 1000 characters

These limits were set conservatively for compatibility with local LLMs that have 8K–32K context windows. However, modern cloud models have vastly larger context windows:
- Gemini 2.5 Flash: 1M context
- Gemini 2.5 Pro: 1M context
- Claude: 200K context
- GPT-4o: 128K context

The current one-size-fits-all approach wastes capacity on large-context models — richer context (more lorebook entries, longer style guides, more chapter history) directly improves translation quality. Conversely, the current limits may still be too generous for very small local models (e.g., 8K context Llama variants), risking context overflow that silently degrades output.

## Decision
Add a model-context-window lookup table in `services/ai/settings.py` that maps model identifiers to their known context window sizes. The `build_translation_prompt()` method accepts an optional `model` parameter and scales truncation limits proportionally based on three tiers:

| Tier | Context Window | global_context | thread_context | style_guide |
|------|---------------|----------------|----------------|-------------|
| Conservative | < 100K tokens | 1,000 chars | 2,000 chars | 1,000 chars |
| Generous | 100K–500K tokens | 4,000 chars | 8,000 chars | 4,000 chars |
| Maximum | > 500K tokens | 8,000 chars | 16,000 chars | 8,000 chars |

Unknown models default to the Conservative tier to prevent context overflow. The lookup table includes all models currently supported by the system (Gemini variants, OpenAI variants, Claude variants, common local LLM families).

## Alternatives Considered

### Let Users Manually Set Limits
- Pros: Maximum flexibility, users know their hardware best
- Cons: Too technical for most users, easy to misconfigure and cause silent quality degradation or context overflow
- Rejected: Good defaults should handle 95% of cases — power users can still override via the style guide field

### No Limits at All (Send Everything)
- Pros: Simplest implementation, maximizes context for large models
- Cons: Breaks small-context local LLMs immediately, causes context overflow errors or silent truncation by the model's own tokenizer
- Rejected: Must support the full range of models from 8K local to 1M+ cloud

### Dynamic Measurement via Tokenizer
- Pros: Precise token counting, adapts to actual prompt content
- Cons: Requires loading model-specific tokenizers (different for each model family), adds latency to every translation call, tokenizer libraries are heavy dependencies
- Rejected: The added latency and complexity aren't justified — tier-based character limits are a good-enough approximation

## Consequences
- Better translation quality on large-context models due to richer lorebook, style guide, and chapter history context
- Safe defaults for local LLMs — no risk of context overflow for small models
- New models can be added to the lookup table with a single line of code
- The tiered approach is simple to understand and debug — no complex tokenization logic
- Character-based limits are an approximation (1 token ≈ 4 characters for English, ≈ 1.5 for Chinese) — this is acceptable for truncation thresholds
- Works in conjunction with ADR-064 (Local LLM Context Length Safeguards) — this ADR extends that concept to cloud models
