# ADR-079: Audit-Driven Minor Improvements

## Status
Accepted

## Date
2026-06-14

## Context
A comprehensive project audit (comparing the translation pipeline against premium Chinese web novel translation standards from Wuxiaworld, Volare Novels, and DeathBlade) identified four minor gaps that could be trivially addressed to push the system from 9.5/10 to 10/10 compliance.

## Decision
Implement all four recommendations in a single batch:

### 1. Expanded Genre Keywords
Added `纯爱`, `恋爱`, `嫁人` to the `romance` genre keywords, and `日常`, `slice of life`, `slice-of-life` to the `urban` genre keywords. This ensures novels tagged with common Chinese web novel tags (like `纯爱` for "pure love" BL/GL, or `日常` for slice-of-life) are correctly detected by the genre-aware prompt system (ADR-071).

### 2. Onomatopoeia Handling Rule
Added Core Rule #5 to the translation prompt: "Onomatopoeia & Sound Effects" with specific Chinese-to-English examples (哈哈→Haha, 嘶→*hiss*, 噗→*pfft*, 咔哒→*click*, 砰→*bang*, etc.). Instructs the AI to use italics with asterisks for non-verbal sounds, matching standard web novel formatting.

### 3. Poetry/Verse Instructions for Historical Genre
Added two new rules to the `historical` genre prompt fragment:
- Embedded poetry (诗词): translate with attention to rhyme, meter, and literary elegance. Preserve verse structure.
- Classical Chinese (文言文) passages: translate naturally into modern prose but keep the elevated, archaic tone.

### 4. Dialogue Line Fidelity Metric
Added a third fidelity check in `fidelity_checker.py`: dialogue line counting. The system now counts lines starting with dialogue markers (`"`, `"`, `「`, `『`, `'`, `—`) in both original and translated text. If the original has ≥5 dialogue lines and the translation preserves less than 20% of them, a warning is triggered. This catches cases where the AI might omit dialogue-heavy sections.

## Alternatives Considered
Not applicable — these are all additive, non-breaking enhancements identified by audit.

## Consequences
- Novels with `纯爱`/`恋爱`/`日常` tags are now correctly routed to genre-specific prompts.
- Onomatopoeia in Chinese novels will be translated more naturally and consistently.
- Historical novels with embedded poetry will receive specialized formatting instructions.
- The fidelity checker now has a 3-metric system (paragraphs, characters, dialogue) providing more granular detection of translation anomalies.
- All 84 existing tests continue to pass.
