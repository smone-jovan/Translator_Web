# ADR-043: Centralized Settings State Management

## Status
Accepted (partially implemented)

## Date
2026-05-30 (original) / 2026-06-15 (updated to reflect current state)

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

### Current Implementation Status
A React Context-based provider was **not** implemented. Instead, the codebase uses a **dual-persistence pattern**:
- **Frontend:** Component-local `useState` hooks in `SettingsPage.tsx` (lines 129-144, 186-200) with `localStorage` as persistence via `useEffect` hooks (lines 345-352)
- **Backend:** `POST /api/settings` (line 304-307) and `GET /api/global-context` (line 207) for server-side sync
- **Cross-component reads:** Other components (ReaderPage, TranslatePage, ContextLibraryPage) read settings directly from `localStorage`

This pattern works but has the sync limitations originally identified (components may read stale values until navigation/refresh).

### Original Implementation Plan
1. ~~Create `src/contexts/SettingsContext.tsx` with a `SettingsProvider` component.~~
2. ~~Define a `Settings` TypeScript interface matching the backend `global_settings` schema.~~
3. ~~On mount, fetch settings from `GET /api/settings` and populate context.~~
4. ~~Expose `updateSetting()` that updates local state immediately (optimistic) and calls `PUT /api/settings` in background.~~
5. ~~Wrap the app root in `<SettingsProvider>` in `App.tsx`.~~
6. ~~Replace all direct `localStorage.getItem()` calls with `useSettings()` hook.~~
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
- **Status: Not chosen** — localStorage + API pattern was retained instead.

### Keep localStorage + custom hook
- **Pros**: No context overhead, works offline by default.
- **Cons**: Still has sync issues between components; no optimistic update pattern.
- **Status: Current approach** — Each component reads settings from localStorage with component-local useState. Backend sync via POST/GET /api/settings.

## Consequences
- **Positive:** localStorage provides fast offline-first initial load
- **Positive:** Backend API sync ensures settings persist across devices/sessions
- **Negative:** No shared reactive state — settings changes in SettingsPage may not be immediately reflected in other components until navigation/refresh
- **Negative:** Each component has its own localStorage.getItem() + JSON parse + fallback logic (duplicate code)
- **Negative:** No TypeScript type safety for raw localStorage access
- **Negative/Risk:** React Context-based centralization (original plan) remains a future improvement opportunity
