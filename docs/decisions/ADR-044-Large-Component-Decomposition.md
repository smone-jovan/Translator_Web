# ADR-044: Large Component Decomposition

## Status
Accepted

## Date
2026-05-30

## Context
Several page components have grown excessively large:
- `ReaderPage.tsx` -- ~855 lines, ~30 `useState` hooks
- `LibraryPage.tsx` -- ~732 lines
- `SettingsPage.tsx` -- ~1000+ lines

These large components cause:
1. **Hard to navigate** -- Finding specific logic requires scrolling through hundreds of lines.
2. **Hard to test** -- Business logic is coupled to UI rendering, making unit testing impossible.
3. **Re-renders cascade** -- State changes in unrelated sections trigger re-renders across the entire page.
4. **Merge conflicts** -- Multiple developers editing the same large file increases conflict probability.
5. **Cognitive load** -- Understanding the full component requires holding 1000+ lines in working memory.

## Decision
Decompose large page components using a layered extraction strategy:

### Extraction Strategy
1. **Custom hooks** -- Extract stateful logic into `useXxx()` hooks.
   - `ReaderPage` → `useChapterNavigation()`, `useStreamTranslation()`, `useScrollProgress()`, `useReaderSettings()`
   - `LibraryPage` → `useBookGrid()`, `useBatchTranslate()`, `useHallucinationAudit()`
   - `SettingsPage` → `useAIProviderConfig()`, `useThemeConfig()`, `usePrefetchConfig()`

2. **Sub-components** -- Extract visual sections into dedicated components.
   - `ReaderPage` → `ChapterReader`, `ChapterGrid`, `ChapterListControls`, `NovelHeader`, `SettingsOverlay` (already partially done in `src/components/reader/`)
   - `LibraryPage` → `BookCard`, `BookGrid`, `ContinueReadingCarousel`, `BatchTranslateSection`
   - `SettingsPage` → `AIProviderCard`, `ThemeSelector`, `TokenCapSelector`, `PrefetchSlider`

3. **Colocation** -- Place hooks and sub-components in a co-located folder:
   ```
   src/pages/ReaderPage/
   ├── index.tsx              # Slim orchestrator (< 200 lines)
   ├── useChapterNavigation.ts
   ├── useStreamTranslation.ts
   ├── useScrollProgress.ts
   └── ...sub-components
   ```

### Target Metrics
| Component | Current | Target |
|---|---|---|
| `ReaderPage.tsx` | ~855 lines, ~30 useState | < 200 lines, < 5 useState |
| `LibraryPage.tsx` | ~732 lines | < 200 lines |
| `SettingsPage.tsx` | ~1000+ lines | < 300 lines |

### Implementation Order
1. `ReaderPage` first (most complex, most state hooks).
2. `SettingsPage` second (largest file).
3. `LibraryPage` third.

## Alternatives Considered

### UseReducer instead of multiple useState
- **Pros**: Single dispatch function, easier to group related state updates.
- **Cons**: More boilerplate for simple state; doesn't solve the file size problem alone.
- **Rejected as sole solution:** Useful as a complement to decomposition, not a replacement.

### Split into separate routes (e.g., /reader/chapters, /reader/settings)
- **Pros**: Smaller page files by definition.
- **Cons**: Changes the UX -- the current overlay/modal pattern for settings in reader is intentional.
- **Rejected:** The current UX is a deliberate design choice (ADR-033).

## Consequences
- **Positive:** Each file is focused on a single responsibility.
- **Positive:** Custom hooks are independently testable.
- **Positive:** Sub-components can be memoized individually to reduce re-renders.
- **Positive:** Smaller files reduce merge conflict surface area.
- **Negative/Risk:** More files to navigate (mitigated by folder colocation).
- **Negative/Risk:** Extraction effort is non-trivial (~4-6 hours total across all three pages).
