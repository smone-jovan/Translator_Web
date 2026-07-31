# ADR-077: Robust Paragraph Detection For EPUBs

## Status
Accepted

## Date
2026-06-14

## Context
The `verify_translation_fidelity` function (ADR-072) counts paragraphs to ensure the LLM didn't truncate or hallucinate content. Originally, it counted paragraphs by splitting the text strictly on double newlines (`\n\n`), which is the standard format for translated web novels.

However, raw Chinese EPUB files often use single newlines (`\n`) for paragraph breaks. This caused the fidelity checker to treat an entire EPUB chapter as a single massive paragraph. When compared against the AI's correctly formatted output (which uses `\n\n` and has 50-100 paragraphs), the system calculated extreme paragraph ratios (e.g., 80.0x) and incorrectly flagged hundreds of chapters with `fidelity_warning`s, severely degrading the feature's usefulness.

## Decision
Change the paragraph counting logic in `fidelity_checker.py` to use a regular expression that splits on one or more newlines (`re.split(r'\n+', text)`).

## Alternatives Considered

### Normalizing all text to `\n\n` before saving to DB
- Pros: Consistent database formatting.
- Cons: Mutating the `content_original` means we lose the exact source text, which violates the principle of keeping raw data pristine.
- Rejected: We should adapt the checker, not mutate the source.

### Using separate `\n` logic just for EPUBs
- Pros: Keeps strict `\n\n` rules for web scraping.
- Cons: Requires passing the `source_type` through the entire translation pipeline down to the fidelity checker, increasing coupling.
- Rejected: `\n+` safely handles both formats natively without needing to know the source.

## Consequences
- The fidelity checker robustly handles both single-spaced and double-spaced content.
- Over 500 false positive warnings were eliminated from the database.
- Future batch imports from EPUBs will not trigger false warnings.
