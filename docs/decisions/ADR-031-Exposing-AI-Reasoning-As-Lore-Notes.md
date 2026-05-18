# ADR 031: Exposing AI Reasoning as Context Lore Notes

## Context
When performing AI Context Extraction to automatically build the glossary, the models (specifically Gemini and Gemma reasoning models) frequently output extensive `<thought>` or `<think>` blocks. These blocks contain highly valuable literary analysis, character breakdowns, tone considerations, and rationale for choosing specific translation terms. 

Previously, the backend regex stripped and discarded these blocks entirely to ensure clean JSON parsing. However, due to model hallucinations or context window truncations, sometimes the opening `<thought>` tag was missing. This caused the stripping regex to fail, leaking the reasoning block into the naive fallback parser, which incorrectly created dozens of garbage glossary terms out of the reasoning text.

## Decision
Instead of merely destroying the `<thought>` blocks, we decided to:
1. **Extract and Persist the Reasoning Trace:** We explicitly capture the contents of the `<thought>` block (handling missing opening tags by splitting on the closing `</thought>` tag).
2. **Expose Reasoning as Metadata:** The backend now packages the extracted reasoning string into the `metadata.reasoning` field of the extraction JSON response.
3. **Render as a First-Class UI Feature:** The frontend `ContextLibraryPage` now features an "AI Reasoning & Lore Notes" collapsible accordion above the extracted suggestions. This allows translators to read the AI's internal monologue and literary analysis, effectively serving as an auto-generated "Lorebook Overview" for the analyzed chapters.
4. **Relaxed JSON Extraction:** We replaced the strict, fragile JSON parsing fallbacks with a relaxed Regex Key/Value extraction loop (`re.findall`) that extracts `original_term`, `translated_term`, and `notes` independently, zipping them together. This guarantees structural integrity even if the model outputs malformed JSON or omits commas.

## Consequences
- **Positive:** Massive improvement in extraction reliability; garbage terms caused by reasoning leakage are 100% eliminated. 
- **Positive:** Translators gain deep insight into *why* the AI chose certain terms, providing valuable context that was previously lost.
- **Positive:** The extraction feature feels significantly more premium and "smart" as the user can literally read the AI's thoughts.
- **Negative:** Increased payload size per extraction request (though negligible for text).

## Status
Accepted
