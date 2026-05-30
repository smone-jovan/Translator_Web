# Quality vs Fast Translation Mode

## Problem Statement
How Might We let users trade translation quality vs speed when using different AI providers (Gemini for quality, LM Studio for speed), while automatically optimizing prompts, token caps, and context depth for each mode?

## Recommended Direction
Add a **Quality / Fast toggle** to the batch translate and single translate flows. The system auto-adjusts everything based on the selected mode:

### Quality Mode (Gemini-focused)
- **Provider:** Gemini 3.1 Flash Lite (or user-selected Gemini model)
- **Token cap:** 30K+ per chapter (no artificial limit)
- **Prompt depth:** Full — inject style guide, glossary with usage examples, previous chapter summary
- **Content-aware:** Detect chapter type (dialog/action/narration) and adjust prompt tone
- **Context injection:** Include top 30 glossary terms + last chapter summary
- **Speed:** ~15 RPM (Gemini free tier limit), sequential with smart pacing

### Fast Mode (LM Studio-focused)
- **Provider:** LM Studio (local)
- **Token cap:** 10K per chapter (safe for local models)
- **Prompt depth:** Minimal — basic translation instruction + top 10 glossary terms
- **Content-aware:** Skip (adds latency for marginal gain on smaller models)
- **Context injection:** Top 10 glossary terms only, no chapter summary
- **Speed:** Unlimited RPM, can parallelize

### UI
- Toggle button in BulkTranslateModal: "Quality" vs "Fast" with visual indicator
- Settings page: default mode selection
- Per-chapter override possible in reader

## Key Assumptions to Validate
- [ ] Gemini 3.1 Flash Lite actually follows style guide instructions consistently (test with 5 chapters)
- [ ] 10K token cap is sufficient for LM Studio to produce readable translations (test with short/medium/long chapters)
- [ ] Previous chapter summary improves translation coherence (A/B test with/without)
- [ ] Content-aware prompt selection doesn't add significant latency (benchmark)

## MVP Scope
**In:**
- Quality/Fast toggle in BulkTranslateModal
- Auto-adjust token cap based on mode (30K vs 10K)
- Auto-adjust glossary injection depth (30 terms vs 10 terms)
- Style guide field in Thread (textarea in ReaderPage settings)
- Style guide injection in Quality mode prompt

**Out (for now):**
- Previous chapter summary (needs separate API endpoint + DB field)
- Content-aware prompt selection (needs chapter classification logic)
- Glossary usage examples (needs schema change + UI)
- Multi-provider voting (complex, low ROI for personal use)

## Not Doing (and Why)
- **Multi-provider voting** — Overkill for personal use. Quality mode with Gemini is enough.
- **Previous chapter summary** — Valuable but requires new DB field + summary generation API. Defer to Phase 2.
- **Content-aware prompt selection** — Interesting but adds complexity. Style guide covers 80% of the value.
- **Glossary usage examples** — Schema change + UI work. Current glossary injection already works well enough.
- **Feedback-driven re-translate** — Nice-to-have but manual. User can just re-translate with overwrite.

## Open Questions
- Should Quality mode use 2-pass (draft + refine) or just better single-pass prompting? (2x API cost vs quality gain)
- How to handle chapters that exceed LM Studio's 10K cap in Fast mode? Split chapter? Truncate? Skip?
- Should the toggle be per-thread (stored in DB) or per-session (stored in localStorage)?
