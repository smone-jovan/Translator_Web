# ADR-063: Context Engine Glossary Prompt Fix

## Status
Accepted

## Date
2026-06-06

## Context
The user reported that the Context Engine stopped injecting glossary terms into the translation process ("saat translate dia nggak ngambil context lagi ya").
Upon investigation, the root cause was traced to a recent hardening of the translation system prompt:
`TRANSLATION TASK - CRITICAL OUTPUT LANGUAGE: You MUST write the final translation in {lang_name} only. No Chinese characters or pinyin allowed in the output.`

Because this rule was strictly enforced, the AI stopped outputting Chinese characters entirely, including in the `### TRANSLATOR NOTES:` section. The AI either omitted the original Chinese term or wrote the term in English/Pinyin. 
Consequently:
1. `auto_save_glossary` explicitly demands that the `original_term` contains a valid Chinese character using a regex (`[\u4e00-\u9fff]`). Without it, no new terms were saved.
2. For terms already in the database, `reactivate_referenced_archived_terms` uses a case-sensitive substring match (`entry.original_term in original_text`) against the raw Chinese chapter text. If the AI outputted English in the translator notes, the extracted term became English, and the substring match failed forever.
3. This resulted in the active glossary pool (`is_archived = False`) becoming empty, preventing the system from injecting the `[STRICT GLOSSARY / LOREBOOK - MANDATORY]` section.

Additionally, `extract_glossary_pass` was failing to inject terms because its prompt did not explicitly instruct the AI to emit the `### TRANSLATOR NOTES:` header, causing the regex in `auto_save_glossary` to silently reject the output.

## Decision
1. **Relaxed the "No Chinese" rule:** We updated the `build_translation_prompt` to allow Chinese characters *exclusively* in the Translator Notes section.
   - Old: `No Chinese characters or pinyin allowed in the output.`
   - New: `No Chinese characters or pinyin allowed in the story output. (Exception: You MAY use Chinese characters in the Translator Notes at the very end).`
2. **Explicit Header in Extraction Pass:** We updated the `sys_prompt` in `extract_glossary_pass` to forcefully require the exact header string `### TRANSLATOR NOTES:` before the list of extracted terms.

## Consequences
- **Restored Term Extraction:** The AI will now reliably output the `### TRANSLATOR NOTES:` header with original Chinese characters, allowing `auto_save_glossary` to successfully scrape and save new terms.
- **Restored Context Injection:** Because `original_term` now correctly stores Chinese characters again, `reactivate_referenced_archived_terms` will successfully find them in the raw chapter text, keeping the terms active and injecting them into future translation prompts.
- **Improved Extraction Reliability:** The `extract_glossary_pass` will now successfully capture terms before translation even begins, improving the quality of the first translated chapter.
