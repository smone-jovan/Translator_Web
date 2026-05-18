# ADR-034: Batch Reliability and Global Progress UX

## Status
Accepted

## Date
2026-05-18

## Context
Batch translation exposed several coupled reliability and UX issues:

- Gemini/Gemma streaming can return an empty stream while the non-streaming completion endpoint still returns a structured response.
- Gemini can block individual chapters with `content_filter: PROHIBITED_CONTENT`; these failures must be visible and must not be saved as successful empty translations.
- Provider selection drifted in logs because Gemini was active while the backend still passed `lm_model` values such as `qwen/qwen3-4b-2507` into batch/streaming routes.
- The batch progress widget only rendered inside Library, so users lost progress visibility after navigating to Translate, Context, Settings, or Reader detail pages.
- Returning from Reader recreated `Layout`, whose default tab was Translate, causing Back from a book to jump to the main Translate page instead of Library.

## Decision
Implement a reliability and navigation pass across backend batch execution and the React app shell.

### Backend
- `BackgroundTranslator._do_translate` now returns `bool` so the batch worker can accurately add failed chapter IDs to `failed_ids`.
- Final translated output is validated after stripping thinking blocks and translator notes. Empty output is marked `error`, not `done`.
- Empty streaming responses now retry once through non-streaming `chat_completion` before failing.
- Provider-aware model/base URL resolution lives in `backend/services/ai/settings.py`:
  - Gemini uses `GlobalSetting.gemini_model` and the Google Gemini OpenAI-compatible base URL.
  - OpenAI uses `GlobalSetting.openai_model` and `openai_url`.
  - LM Studio uses `GlobalSetting.lm_model` and `lm_url`.
- Incompatible requested models are ignored for the active provider. Example: if Gemini is active and a stale frontend payload sends `qwen/qwen3-4b-2507`, backend uses `gemini_model` instead.

### Frontend
- `BulkStatusCenter` is now mounted globally in `App.tsx`, not only in `LibraryPage`.
- The progress widget remains visible across Translate, Library, Context, Settings, and Reader book/detail list views.
- The progress widget is hidden while reading an individual chapter to avoid covering the reading surface.
- `BulkStatusCenter` uses `getApiUrl` so LAN/mobile access follows the same dynamic API base URL strategy as the rest of the app.
- `App.tsx` owns `activeTab`; `Layout` is now controlled. Opening a book sets the active tab to Library, so returning from Reader lands back on Library rather than Translate.

## Alternatives Considered

### Keep Empty Stream as Success
- Pros: Simpler control flow.
- Cons: Creates false `done` chapters with empty translations and hides real provider failures.
- Rejected because it caused chapter 2 to appear completed even though no translated content existed.

### Treat Gemini Content Filter as Retryable Forever
- Pros: Might eventually pass if provider behavior changes.
- Cons: Wastes quota/RPM, stalls batch, and obscures a real safety block.
- Rejected. Content-filtered chapters stay `error`; users can retry with LM Studio/local model or another provider.

### Keep Progress Widget in Library Only
- Pros: Smaller frontend change.
- Cons: Users navigate away during long batch jobs and lose status visibility.
- Rejected because batch translation is a global background job.

## Consequences
- Batch failures are explicit. A chapter cannot silently become `done` with empty content.
- Gemini/Gemma empty-stream behavior is handled without losing the batch.
- Logs now reflect the active provider's model after backend reload.
- Batch progress is visible globally while staying out of the chapter reading UI.
- Navigation preserves user intent: book Back returns to Library.

## Verification
- `py -m unittest backend.scratch.test_ai_settings backend.scratch.test_background_translator`
- `py -m py_compile backend/services/ai/settings.py backend/routers/batch.py backend/routers/translate.py backend/routers/threads.py backend/services/background_translator.py`
- `npm run typecheck`

## Known Follow-Up
- `npm run lint` still reports pre-existing lint issues in `src/components/reader/ChapterReader.tsx`, `src/pages/ReaderPage.tsx`, and `src/pages/SettingsPage.tsx`. These are not introduced by this ADR but should be cleaned before enforcing a zero-warning frontend gate.
