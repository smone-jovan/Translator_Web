# ADR-047: Quality/Fast Translation Mode

## Status
Accepted

## Date
2026-05-30

## Context
Users employ different AI providers with vastly different capabilities:
- **Gemini 3.1 Flash Lite**: Cloud, 15 RPM free tier, high quality, handles long context
- **LM Studio (local)**: Unlimited RPM, lower quality, limited context window (~10K tokens)

A one-size-fits-all translation configuration wastes resources: sending a full 30-term glossary and style guide to a local 7B model adds latency without improving output, while capping Gemini at 10K tokens wastes its capability.

## Decision
Implement a Quality/Fast mode toggle that automatically adjusts all translation parameters:

### Quality Mode (Gemini-focused)
| Parameter | Value | Rationale |
|---|---|---|
| Token cap | Follows global setting (minimum 22K if safety cap disabled) | Gemini handles long outputs well |
| Glossary terms | Follows `max_context_terms` setting | Full context for consistency |
| Style guide | Injected into prompt | Leverages Gemini's instruction-following ability |
| Provider | User's configured Gemini model | Best quality available |

### Fast Mode (LM Studio-focused)
| Parameter | Value | Rationale |
|---|---|---|
| Token cap | 10K max (hard cap) | Protect local LLMs from context bloat |
| Glossary terms | Locked at 10 | Minimal context for speed |
| Style guide | Skipped | Reduces prompt overhead |
| Provider | User's configured LM Studio | Maximum speed |

### Token Safety Cap Interaction
- **Safety cap ENABLED**: Both modes respect the cap (e.g., 22K). Quality doesn't override it.
- **Safety cap DISABLED**: Quality mode uses no cap (unlimited). Fast mode caps at 10K.

### Context Limit Interaction
- **Quality mode**: Follows global `max_context_terms` setting (user controls depth).
- **Fast mode**: Locked at 10 terms regardless of global setting.

### UI Locations
- **Global default**: SettingsPage — "Default Translation Quality" toggle
- **Per-batch override**: BulkTranslateModal — "Translation Quality" toggle (reads default from localStorage)
- **Active model info**: BulkTranslateModal — shows current model + RPM

## Alternatives Considered

### Auto-detect provider and adjust silently
- **Pros**: No user decision needed.
- **Cons**: User may want Quality mode with LM Studio (for testing) or Fast mode with Gemini (for speed).
- **Rejected**: User control is preferred over automation.

### Per-model configuration profiles
- **Pros**: Fine-grained control for each model.
- **Cons**: Complex UI; most users have 1-2 providers; over-engineering.
- **Rejected**: Quality/Fast binary covers 95% of use cases.

### Separate token cap per mode (independent settings)
- **Pros**: Maximum flexibility.
- **Cons**: More settings to manage; confusing interaction with existing safety cap.
- **Rejected**: Reuse existing safety cap with mode-aware logic.

## Consequences
- **Positive:** Users get optimal configuration for their provider without manual tuning.
- **Positive:** Safety cap is always respected when enabled — no accidental token waste.
- **Positive:** Fast mode protects local LLMs from context bloat.
- **Negative/Risk:** Two places to set quality mode (Settings + Modal) — may confuse users.
- **Negative/Risk:** Mode logic adds complexity to prompt building and token cap calculation.
