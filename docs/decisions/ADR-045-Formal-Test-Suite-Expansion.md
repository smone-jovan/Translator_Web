# ADR-045: Formal Test Suite Expansion (pytest + Vitest)

## Status
Accepted

## Date
2026-05-30

## Context
The project currently lacks a formal test suite:
- Backend tests live in `backend/scratch/` (gitignored, developer-only scripts).
- Frontend has no test files (no Jest, Vitest, or React Testing Library setup).
- ADR-018 established TDD principles but only covered `test_context_engine.py` in scratch.

As the codebase grows, the risk of regressions increases:
1. AI provider adapter changes can break translation silently.
2. Database auto-migration logic has no regression tests.
3. Frontend component behavior relies entirely on manual testing.
4. Context engine prompt building has complex edge cases.

## Decision
Establish a formal test suite for both backend and frontend:

### Backend: pytest
- **Location:** `backend/tests/` (committed to git, not in scratch).
- **Framework:** `pytest` + `pytest-asyncio` + `httpx` (for FastAPI `TestClient`).
- **Database:** SQLite in-memory (same pattern as ADR-018).
- **Coverage target:** 70%+ for services layer.

#### Test Structure
```
backend/tests/
├── conftest.py              # Shared fixtures (test DB, test client, mock AI)
├── test_context_engine.py   # Prompt building, glossary injection, note stripping
├── test_ai_providers.py     # Factory resolution, model normalization, adapter contracts
├── test_database.py         # Model CRUD, auto-migration, WAL mode
├── test_background_translator.py  # Batch logic, RPM pacing, streaming queues
├── test_routers/
│   ├── test_translate.py    # Translation endpoints
│   ├── test_threads.py      # Thread CRUD
│   ├── test_lorebook.py     # Glossary CRUD
│   └── test_batch.py        # Batch translation
└── test_services/
    └── test_hallucination_detector.py  # Detection edge cases
```

### Frontend: Vitest + React Testing Library
- **Location:** `src/__tests__/` and co-located `*.test.tsx` files.
- **Framework:** `vitest` + `@testing-library/react` + `jsdom`.
- **Coverage target:** 50%+ for hooks and utility functions.

#### Test Structure
```
src/
├── __tests__/
│   ├── hooks/
│   │   └── useSettings.test.tsx    # Settings context logic
│   └── lib/
│       └── api.test.ts             # API_BASE resolution
├── hooks/
│   └── useConfirm.test.tsx         # Confirm dialog hook
└── components/
    └── reader/
        └── ChapterReader.test.tsx  # Reader rendering
```

### Configuration
- Add `vitest.config.ts` (extends `vite.config.ts`).
- Add `pytest.ini` or `pyproject.toml` pytest section.
- Add npm scripts: `"test": "vitest run"`, `"test:watch": "vitest"`.
- Add pip dev dependency: `pytest`, `pytest-asyncio`, `httpx`.

### CI Integration
- `npm run lint && npm test` for frontend.
- `pytest` for backend.

## Alternatives Considered

### Jest (frontend)
- **Pros**: Industry standard, mature ecosystem.
- **Cons**: Slower than Vitest; requires separate config from Vite; doesn't share Vite's plugin system.
- **Rejected:** Vitest shares `vite.config.ts` and is purpose-built for Vite projects.

### Playwright E2E only (no unit tests)
- **Pros**: Tests real user flows end-to-end.
- **Cons**: Slow feedback loop; can't test edge cases efficiently; flaky in CI.
- **Rejected:** Unit tests provide fast, deterministic feedback; E2E is complementary, not a replacement.

### Keep tests in scratch/
- **Pros**: No setup effort.
- **Cons**: Not committed to git; not run in CI; not discoverable by other developers.
- **Rejected:** Defeats the purpose of regression testing.

## Consequences
- **Positive:** Regressions caught before reaching production.
- **Positive:** Refactoring confidence -- can restructure code knowing tests will catch breakage.
- **Positive:** Tests serve as living documentation of expected behavior.
- **Positive:** AI provider adapters can be tested with mock responses without hitting real APIs.
- **Negative/Risk:** Initial setup effort (~2-3 hours).
- **Negative/Risk:** Test maintenance overhead as codebase evolves.
- **Negative/Risk:** Need to mock AI provider responses for deterministic testing.
