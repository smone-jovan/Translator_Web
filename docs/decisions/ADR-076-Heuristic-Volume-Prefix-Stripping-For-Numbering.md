# ADR-076: Heuristic Volume Prefix Stripping For Numbering

## Status
Accepted

## Date
2026-06-14

## Context
The "Numbering Polish" feature includes an "Auto-detect starting number" option. This works by scanning the original title of the first imported chapter using regex patterns (e.g., matching `chapter \d+` or falling back to raw digits `\d+`). 

However, many raw EPUB imports include volume labels in the title string (e.g., `v1_2.弄个潮先` or `Volume 1 Chapter 2`). When the user intentionally skips or cuts the first few chapters of an EPUB, the auto-detect logic would mistakenly match the `1` from the volume prefix instead of the actual chapter number (e.g., `2`). This resulted in the system forcing the chapter numbering to reset back to `01`, overriding the user's intent.

## Decision
Strip common volume prefixes from the title string using a case-insensitive regex substitution *before* executing the chapter number detection regex.

**Current implementation** (`polish.py:229`):
```python
title_to_parse = re.sub(r'(?i)^v\d+[-_]?', '', first_ch.title_original).strip()
```

This strips the abbreviated form `v\d+[-_]?` (e.g., `v1_`, `v2.`) before auto-detection. The full-word form `Volume \d+` is stripped separately in `clean_and_format_chapter_title()` (line 35) for title display, but is **not** stripped in the auto-detection block (lines 228–246). This is acceptable because the auto-detection regex at line 231 matches `volume\s*(\d+)` as a named pattern, which naturally skips the volume number and captures the chapter number.

## Alternatives Considered

### Prompting the LLM to extract the number
- Pros: Highly accurate, can handle complex natural language.
- Cons: Adds API latency and cost just to find a starting number.
- Rejected: Regex is instantaneous and free.

### Forcing the user to manually input the starting number
- Pros: Zero code complexity.
- Cons: Degrades UX; defeats the purpose of an "Auto-detect" feature.
- Rejected: We want the system to be as automated as possible.

## Consequences
- Auto-detect accurately ignores volume numbers and successfully extracts the true chapter number.
- Batch processing of EPUBs with volume prefixes in their filenames/titles is now seamless.
- If a novel actually uses `v1` as the chapter format without the word "chapter", this strip might accidentally remove it, but this is a very rare edge case in web novel naming conventions.
