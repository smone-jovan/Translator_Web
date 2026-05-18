# ADR-035: Chapter-Level AI Token Safety Cap

## Status
Proposed

## Date
2026-05-18

## Context
Long single-chapter translations can degrade model reliability even when the source chapter itself is still within the current content import guardrails. In recent reading sessions, the translator began hallucinating and drifting off-task on long chapter requests despite the existing chapter-length constraint of roughly 5,000 Chinese words.

The current risk is not only source length. Real prompt size also includes:

- system prompt and translation instructions
- lorebook/context injections
- provider-specific hidden reasoning overhead
- translated output expansion relative to source length

This means a chapter that looks "safe" by raw source length can still push the effective request budget high enough to reduce translation quality.

## Decision
Add a configurable chapter-level AI safety cap for translation requests:

- Add a global toggle to enable or disable chapter token safety caps.
- Add global preset caps of `7000`, `15000`, `22000`, and `30000` tokens per chapter.
- Default to `enabled = true` and `chapter_token_cap = 22000`.
- When enabled, apply the selected cap to chapter translation requests only.
- When disabled, send no chapter token cap at all.
- Keep the existing source-side chapter guardrail of approximately `<= 5000` Chinese words.

This cap exists to reduce hallucination drift, runaway verbosity, and wasted token burn on long chapter translations while still allowing power users to opt into larger or uncapped runs.

## Alternatives Considered

### Keep Current Chapter-Length Guard Only
- Pros: No extra implementation complexity.
- Cons: Raw chapter length alone does not control full prompt budget.
- Rejected because real failures already occurred inside current chapter size limits.

### Use Provider-Specific Caps Only
- Pros: More exact tuning per provider/model family.
- Cons: Adds config complexity, increases maintenance, and makes behavior harder to reason about.
- Rejected for now. Start with one app-level default ceiling first.

### Keep a Hardcoded 7000 Cap
- Pros: Simpler implementation and safer lower ceiling.
- Cons: Too rigid for users with unusually large chapters or models that can still behave well at higher limits.
- Rejected because the app needs a safe default plus an escape hatch for advanced users.

## Consequences
- Single-chapter translation becomes more predictable under long-context conditions.
- Users can trade safety vs. uninterrupted long output without editing code.
- Provider behavior remains easier to reason about because the app exposes a small fixed preset set instead of freeform values.
- Some chapters may still require chunked translation when glossary/context load becomes too large.
- Users who disable the cap entirely accept higher risk of hallucination drift and token waste.

## Implementation Notes
- Apply the cap in the backend translation pipeline before provider execution.
- Apply it to chapter translation paths only: manual translate, re-translate, streaming chapter translate, background translate, and batch-per-chapter translate.
- Count not only source chapter text, but also prompt/context payload size where feasible.
- If exact token counting is unavailable for a provider, use provider `max_tokens` support with the configured preset.
- Overlong or rambling output should not silently count as a good translation result.

## Follow-Up
- Implement chunked chapter translation fallback once cap-based truncation becomes measurable.
- Consider provider/model-specific overrides only after the default preset system proves insufficient.
