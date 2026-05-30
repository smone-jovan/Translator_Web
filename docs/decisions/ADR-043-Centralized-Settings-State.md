# ADR-043: Centralized Settings State Management

## Status
Accepted

## Date
2026-05-30

## Context
Settings values (AI provider, model, language, token caps, prefetch range, theme, etc.) are currently read from `localStorage` independently in multiple components:
- `TranslatePage.tsx` reads provider/model for the translate form.
- `ReaderPage.tsx` reads prefetch range and token caps for streaming translation.
- `SettingsPage.tsx` reads and writes all settings.
- `ContextLibraryPage.tsx` reads max context terms.

This scattered approach causes:
1. **Sync issues** -- A setting changed in `SettingsPage` may not be immediately reflected in `ReaderPage` until the user navigates or refreshes.
2. **Duplicate logic** -- Each component has its own `localStorage.getItem()` + JSON parse + fallback logic.
3. **No type safety** -- Raw `localStorage` access bypasses TypeScript's type system.
4. **Hard to test** -- Settings logic is embedded in UI components, not testable in isolation.

The backend already has a `global_settings` table synced via `/api/settings`, but the frontend doesn't have a centralized state layer.

## Decision
Create a React Context-based settings provider that centralizes all settings state:

### Architecture
```
SettingsContext (React Context)
├── settings state (typed object)
├── updateSetting(key, value) -- optimistic update + sync to backend
├── refresh() -- re-fetch from backend
└── loading/error states
```

### Implementation
1. Create `src/contexts/SettingsContext.tsx` with a `SettingsProvider` component.
2. Define a `Settings` TypeScript interface matching the backend `global_settings` schema.
3. On mount, fetch settings from `GET /api/settings` and populate context.
4. Expose `updateSetting()` that updates local state immediately (optimistic) and calls `PUT /api/settings` in background.
5. Wrap the app root in `<SettingsProvider>` in `App.tsx`.
6. Replace all direct `localStorage.getItem()` calls with `useSettings()` hook.
7. Keep `localStorage` as a fallback cache for offline/fast-initial-load only.

### Settings Interface
```typescript
interface Settings {
  aiProvider: 'lm_studio' | 'openai' | 'gemini';
  model: string;
  targetLanguage: string;
  maxContextTerms: number;
  prefetchRange: number;
  chapterTokenCap: number | null;
  theme: 'obsidian' | 'black' | 'oled' | 'white' | 'sepia' | 'omni';
  // ... all other settings from global_settings table
}
```

## Alternatives Considered

### Zustand / Jotai (external state library)
- **Pros**: Purpose-built state management with devtools.
- **Cons**: Additional dependency for a single settings context; React Context is sufficient for this use case.
- **Rejected**: Over-engineering for a single global state slice.

### Keep localStorage + custom hook
- **Pros**: No context overhead, works offline by default.
- **Cons**: Still has sync issues between components; no optimistic update pattern.
- **Rejected**: Doesn't solve the core sync problem.

## Consequences
- **Positive:** Single source of truth for all settings across the app.
- **Positive:** Type-safe settings access via `useSettings()` hook.
- **Positive:** Settings changes propagate instantly to all consuming components.
- **Positive:** Testable in isolation -- can mock the context for unit tests.
- **Negative/Risk:** Requires wrapping the app in a provider (minimal boilerplate).
- **Negative/Risk:** Need to handle the initial load state (settings not yet fetched) gracefully.
