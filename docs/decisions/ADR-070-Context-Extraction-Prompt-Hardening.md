# ADR-070: Context Extraction Prompt Hardening

## Status
Accepted (supersedes parts of ADR-063)

## Date
2026-06-12

## Context
The AI glossary extraction system (`extract_glossary_pass()` in `context_engine.py`) was producing low-quality entries with several recurring problems:

1. **Generic context**: Entries like `宁凡 → Ning Fan (A character)` with no meaningful relationship information
2. **Missing context parentheses**: Entries like `天云宗 → Heavenly Cloud Sect` with no parenthetical description at all
3. **Trailing punctuation bug**: AI outputs like `(An ancient artifact).` caused the parser to fail at splitting `translated_term` from `notes`, because `desc.endswith(")")` returned `False` when a period followed the closing parenthesis. This resulted in the entire description being stored as `translated_term` and notes defaulting to a useless `"Auto-extracted: 原术语"`
4. **Multi-line entries**: Some models produced multi-line descriptions that broke the line-by-line parser

## Decision

### Prompt Improvements (`extract_glossary_pass`)
- Added 4 explicit mandatory rules:
  1. Context is REQUIRED — every entry MUST have parenthetical description
  2. NEVER use generic context like "(mentioned in the text)" or "(a character)"
  3. Close parenthetical context with `)` as the LAST character — NO trailing period
  4. Keep ONE entry per line — no multi-line entries
- Added 3 GOOD examples with detailed, relationship-rich context
- Added 3 BAD examples showing exactly what NOT to do (too vague, missing context, trailing period)
- This "good/bad example" pattern significantly improves instruction-following across model sizes

### Parser Fix (`auto_save_glossary`)
- Added `desc.rstrip('.!;,。！ ')` before checking `desc.endswith(")")` to handle trailing punctuation
- This ensures entries like `Ning Fan (Protagonist of the story).` are correctly split into:
  - `translated_term`: "Ning Fan"
  - `notes`: "Protagonist of the story (Auto-extracted)"

## Alternatives Considered

### Regex-Based Parenthetical Extraction
- Pros: More robust than `endswith()` check
- Cons: Complex regex for nested parentheses, harder to maintain
- Rejected: The `rstrip()` + `endswith()` approach is simpler and covers all observed failure cases

### Structured JSON Output from AI
- Pros: Eliminates all parsing ambiguity
- Cons: Many smaller models struggle with valid JSON output, higher token usage, harder to debug
- Rejected: The current line-based format is more robust across model sizes

### Post-Processing Quality Filter
- Pros: Could reject low-quality entries after parsing
- Cons: Wastes AI tokens generating entries that get discarded
- Rejected: Better to fix the prompt so AI generates quality entries in the first place

## Consequences
- New glossary entries will have significantly richer, more useful context descriptions
- The trailing punctuation bug is fixed — no more entries with the entire description crammed into `translated_term`
- Existing low-quality entries in the database are NOT retroactively fixed (would require manual cleanup or re-extraction)
- The good/bad example pattern can be applied to other AI prompts in the system
- Per-novel style guides (injected via `thread.style_guide`) provide additional quality control for translation prompts
