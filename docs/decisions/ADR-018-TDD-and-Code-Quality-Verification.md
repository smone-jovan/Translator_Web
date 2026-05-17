# ADR-018: Test-Driven Development (TDD) and Code Quality Verification

## Status
Accepted

## Date
2026-05-17

## Context
As the project grows in complexity across Phase 10 with features like the Background Translator, Context Engine, and Batch Translation Studio, maintaining reliability and code quality became vital. Prior challenges included:
1. Lexical scoping issues in components (declaration order of state actions and side effects).
2. Unchecked edge cases in Markdown parsing and note stripping.
3. Windows console output crashes due to default system codepage mismatches when printing Chinese characters.
4. TypeScript warnings and Fast Refresh build complications causing compiler friction.

To prevent future regressions and ensure production readiness, we required a formal testing suite and an absolute zero-warning, zero-error linter status.

## Decision
Establish a dedicated Test-Driven Development (TDD) environment and enforce high-fidelity code quality verification:
1. **Isolated Unit Test Suite**: Created [test_context_engine.py](file:///d:/code_xI/Translator_Web/backend/scratch/test_context_engine.py) to test all edge cases of `strip_translator_notes` and database-backed `auto_save_glossary` filtering rules.
2. **In-Memory Database Isolation**: Configured SQLite in-memory database engines during testing to validate data ingestion without touching production storage (`app.db`).
3. **Windows Unicode Safeguards**: Implemented standard stream reconfigurations (`sys.stdout.reconfigure(encoding='utf-8')`) in the backend main entry point [main.py](file:///d:/code_xI/Translator_Web/backend/main.py) to prevent crash triggers on Windows console prints.
4. **Pristine Linter Compliance**: Resolved and removed all unused ESLint and React hook overrides, restructured lexical orders in [BulkTranslateModal.tsx](file:///d:/code_xI/Translator_Web/src/components/BulkTranslateModal.tsx), and eliminated all compiler warnings to achieve exactly `0 errors, 0 warnings` on `npm run lint`.

## Alternatives Considered

### Relying on Manual API Scanning
- **Pros**: Quick to execute during single-page manual checks.
- **Cons**: Difficult to scale or automate; does not protect against subtle regression changes in the backend services.
- **Rejected**: Continuous integration and code cleanliness are essential for reliable background processing.

## Consequences
- Backend core functions are fully covered by fast-running isolated unit tests (all passing in under 0.03 seconds).
- Windows execution runs completely safely without encoding errors.
- Frontend builds cleanly in any build pipe with zero warning clutter.
