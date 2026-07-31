# ADR-078: Lowering Fidelity Ratio to Accommodate AI Paragraph Grouping

## Status
Accepted

## Date
2026-06-14

## Context
The `verify_translation_fidelity` checker (ADR-072) was initially configured with a `MIN_PARAGRAPH_RATIO` of 0.5. This meant that if the translated text had less than 50% of the paragraphs of the original text, a warning was triggered.

However, Chinese web novel authors frequently use highly fragmented, single-sentence paragraphs (pressing "Enter" after every sentence) to artificially inflate chapter length or for dramatic pacing on mobile devices. When high-tier LLMs translate this into English or Indonesian, they natively recognize that these short, related sentences should be grouped into cohesive, standard grammatical paragraphs.

This AI-driven paragraph grouping is correct and produces superior prose. But it routinely results in the final translated paragraph count being ~30-49% of the original Chinese paragraph count, which triggered false positive `fidelity_warning`s in the UI (e.g., 130 original lines becoming 64 translated paragraphs, ratio: 0.49).

## Decision
Lower the `MIN_PARAGRAPH_RATIO` threshold in `fidelity_checker.py` from `0.5` to `0.3`.

## Consequences
- The system will no longer penalize the AI for producing well-structured, cohesive paragraphs from fragmented source texts.
- True truncations (where the AI literally stops generating midway through a chapter) will still be caught, as massive truncations typically drop the ratio below 0.3.
- Combined with the regex `\n+` fix (ADR-077), the fidelity checker is now vastly more stable and produces almost zero false positives.
