# ADR-072: Post-Translation Fidelity Verification

## Status
Accepted

## Date
2026-06-13

## Context
LLMs sometimes silently summarize, skip paragraphs, or truncate content during translation. The existing pipeline has no verification that the translation output is faithful to the input in terms of completeness. Premium translation standards (Wuxiaworld, volare novels) require every paragraph to be present — readers notice and complain when content is missing. This is especially problematic in batch translation workflows where hundreds of chapters are translated without human review, and truncated chapters may go unnoticed until a reader reports them.

## Decision
Create `services/fidelity_checker.py` with a `verify_translation_fidelity()` function that compares paragraph counts between original and translated text. The function:
- Splits both original and translated text on one-or-more-newline boundaries (`re.split(r'\n+', text)`) to count paragraphs — this handles both `\n\n` (web novels) and `\n` (EPUB) formats (see ADR-077)
- Computes the paragraph count ratio (translated / original)
- If the ratio is suspicious (< 0.3 or > 2.5), logs a warning and stores a `fidelity_warning` flag on the chapter record — threshold lowered from 0.5 to 0.3 to accommodate AI paragraph grouping (see ADR-078)
- Also checks character ratio, dialogue line ratio (ADR-079), and mid-sentence truncation (ADR-080)
- This is a **NON-BLOCKING** check — it warns but does not reject the translation

The ratio thresholds account for legitimate differences:
- Chinese paragraphs are often shorter than English paragraphs (ratio > 1.0 is normal)
- Some reformatting is expected (ratio up to 2.5 is acceptable)
- A ratio below 0.3 strongly suggests content was summarized or truncated

## Alternatives Considered

### Sentence-Level Alignment
- Pros: Much more precise, can identify exactly which sentences were skipped
- Cons: Extremely expensive (requires another LLM call or complex NLP), fragile across languages with different sentence structures
- Rejected: The cost and complexity outweigh the benefit for a warning-only system

### Character Count Comparison
- Pros: Simple to implement, no paragraph splitting needed
- Cons: Unreliable across languages — Chinese uses significantly fewer characters than English for the same content (a 1:3 ratio is typical)
- Rejected: The natural character count difference between Chinese and English makes thresholds meaningless

### Blocking on Mismatch
- Pros: Guarantees no truncated translations reach users
- Cons: False positives would block legitimate translations, breaks batch workflows, requires manual review queue
- Rejected: A non-blocking warning is more pragmatic — operators can review flagged chapters at their convenience

## Consequences
- Operators get visibility into potentially truncated or summarized translations via the `fidelity_warning` flag
- Batch translation workflows are not disrupted — the check is advisory only
- Can be extended later with automatic re-translation triggers for flagged chapters
- The paragraph-count approach is fast (no API calls) and works across all model backends
- False positive rate is expected to be low with the chosen thresholds, but may need tuning based on real-world data
