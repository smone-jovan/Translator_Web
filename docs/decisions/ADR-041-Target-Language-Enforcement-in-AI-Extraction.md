# ADR-041: Target Language Enforcement in AI Extraction Prompts

## Status
Accepted

## Date
2026-05-22

## Context
The AI extraction pipeline contains three distinct passes that analyze novel text and output structured data:

1. `extract_thread_context` — Extracts a global context/summary for the thread.
2. `extract_glossary_pass` — Extracts character names and terms into the Lorebook.
3. `extract_relationships_pass` — Extracts character relationship connections.

All three passes use an LLM under the hood. However, none of the system prompts previously specified an output language. As a result, when a user's source material was in Chinese (the most common use case), the LLM would output notes, context summaries, and relationship descriptions **in Chinese** — even when the user's `target_language` setting was set to English or Indonesian.

This caused the Lorebook notes, thread context summaries, and relationship `notes` fields to be filled with unreadable Chinese text for non-Chinese readers, defeating the purpose of translation-first extraction.

## Decision
All three extraction pass functions were updated to accept and inject the user's `target_lang` setting from `GlobalSetting` directly into their respective system prompts.

### Changes Made
- `ContextEngine.extract_thread_context`: System prompt now includes `"Output all content in {target_lang}."`
- `ContextEngine.extract_glossary_pass`: System prompt now includes `"All notes and descriptions must be written in {target_lang}."`
- `ContextEngine.extract_relationships_pass`: System prompt now includes `"All relationship notes must be written in {target_lang}."`

The `target_lang` value is resolved from `GlobalSetting.target_language` at the time the extraction is triggered. All three callers (`context.py` router) were updated to pass the resolved language string down to the engine methods.

## Consequences
- **Positive:** Lorebook notes, thread context summaries, and relationship descriptions are now consistently written in the user's configured target language (e.g., English, Indonesian).
- **Positive:** Fixes a long-standing UX confusion where extracted notes were unreadable after translating Chinese novels.
- **Positive:** Zero breaking changes — only the system prompt string is modified; the output JSON structure is unchanged.
- **Neutral:** If a user switches their `target_language` after extraction, older notes will remain in the previously-extracted language. A manual re-extraction is required to refresh them.
- **Risk:** LLMs with weak multilingual instruction-following (e.g., very small local models) may still partially output in the source language despite the explicit instruction. This is an LLM capability limitation, not a code defect.
