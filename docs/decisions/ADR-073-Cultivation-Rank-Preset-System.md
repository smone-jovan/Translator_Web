# ADR-073: Cultivation Rank Preset System

## Status
Accepted

## Date
2026-06-13

## Context
Cultivation/xianxia novels use hierarchical rank systems (e.g., Qi Condensation → Foundation Establishment → Core Formation → Nascent Soul → Spirit Severing → Dao Seeking → etc.) that MUST be translated consistently across hundreds of chapters. Currently, the glossary/lorebook only captures terms ad-hoc from Translator Notes and AI extraction. This leads to inconsistency — the same rank might be translated as "Foundation Building" in chapter 10 and "Foundation Establishment" in chapter 50. Premium translations (DeathBlade's ISSTH, Er Gen's novels) maintain 100% consistent rank terminology, and readers consider inconsistent ranks a hallmark of low-quality machine translation.

The same problem applies to wuxia martial arts ranks (e.g., 后天 → Houtian/Postnatal, 先天 → Xiantian/Innate) and historical court hierarchies (e.g., 丞相 → Prime Minister/Chancellor, 太监 → Eunuch).

## Decision
Create `services/genre_presets.py` with pre-built lorebook templates for common cultivation systems, martial arts ranks, and court hierarchies. The module provides:

- **Xianxia Standard Cultivation Ranks**: The most common 9-stage cultivation system used in ISSTH, Against the Gods, etc.
- **Wuxia Martial Arts Ranks**: Houtian/Xiantian/etc. progression common in wuxia novels
- **Xuanhuan Power Levels**: Dou Qi, Star Rank, and other xuanhuan-specific systems
- **Imperial Court Hierarchy**: Common official titles and court positions for historical novels

Users can apply a preset to seed their thread's lorebook via a new API endpoint. Presets are **additive** — they add entries to the existing lorebook without overwriting user-customized entries. If a term already exists in the lorebook (matched by `original_term`), the preset entry is skipped.

Presets are stored as Python dictionaries in the module rather than external files.

## Alternatives Considered

### Let AI Discover Ranks Organically
- Pros: Zero setup, works for any novel regardless of rank system
- Cons: Fundamentally inconsistent — the AI may translate the same term differently in each chapter, especially across different translation sessions
- Rejected: Organic discovery produces the exact inconsistency problem we're trying to solve

### Hardcode Ranks into the Translation Prompt
- Pros: Simple, always available to the AI during translation
- Cons: Inflexible — can't be customized per thread, wastes context window for non-cultivation novels, can't handle multiple cultivation systems
- Rejected: The lorebook approach is more flexible and already integrated into the translation pipeline

### External JSON Files
- Pros: Easy to edit without code changes, can be shared between users
- Cons: Requires file I/O, path management, and error handling for missing/malformed files
- Rejected: Python dicts are simpler, type-checkable, and don't need file I/O — the preset data is small and changes infrequently

## Consequences
- One-click consistency for cultivation novels — users apply a preset and get hundreds of chapters with consistent rank terminology
- Presets are additive and safe — they never overwrite user-customized lorebook entries
- Can be extended by users by adding custom presets or modifying existing ones
- The preset system is genre-specific, complementing the genre-aware prompting in ADR-071
- New preset categories can be added without changing the API — only the `genre_presets.py` module needs updating
