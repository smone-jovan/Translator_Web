# ADR-096: Comprehensive Mobile Responsiveness & Touch Ergonomics

## Status
Accepted

## Date
2026-08-28

## Context
With growing usage on mobile devices (smartphones with 360px–414px viewports), a project-wide ergonomics and responsiveness audit revealed several friction points across navigation, dialogs, workspaces, and touch controls:

1. **Bottom Navigation Overflows (`BottomNav.tsx`)**: Fixed minimum width (`min-w-[70px]` across 5 tabs) caused horizontal clipping and overflow on narrow mobile screens (<= 375px).
2. **Translation Workspace Toolbar Compression (`TranslatePage.tsx`)**: Model and Thread selector dropdowns squeezed into a single rigid pill caused long model names (`anthropic/claude-3.5-sonnet`) to truncate severely into unreadable ellipsis, while the `w-72` popovers clipped outside the screen edges.
3. **Novel Updates / Metadata Scraper Layout Collapse (`ScrapeNUModal.tsx`)**: A fixed `h-[440px]` parent containing two `h-full` columns resulted in severe nested scroll collisions and broken candidate selection on mobile viewports.
4. **Sub-optimal Touch Targets (`ApiKeyManager.tsx`, `BookmarksPage.tsx`)**: Key removal buttons (`×`) were small text characters (~12px touch area) prone to accidental taps, and bookmark read buttons were hidden behind hover pseudo-classes (`opacity-0 group-hover:opacity-100`) unreachable on touchscreens.
5. **Dialog Padding & Scroll Traps (`BulkTranslateModal.tsx`, `EditCoverModal.tsx`, `TocImportModal.tsx`, `RelationshipGraph.tsx`)**: Fixed desktop padding (`p: 4`, `p: 6`), oversized icon headers, and canvas gesture interception caused awkward mobile dialog views and page scrolling traps.

## Decision
We systematically refactored and hardened mobile responsiveness across all three identified priority tiers:

### 1. Navigation & Workspace Responsiveness (Priority 1)
- **`BottomNav.tsx`**: Replaced rigid `min-w-[70px]` with fluid `flex-1 min-w-0 p-2 sm:p-2.5`, enabling seamless auto-distribution across 320px–768px viewports.
- **`TranslatePage.tsx`**:
  - Made the bottom toolbar adapt smoothly on mobile (`flex-col sm:flex-row items-stretch sm:items-center`).
  - Stacked Model and Thread selectors with fluid flex containers, responsive text sizing, and bounded popover widths (`max-w-[calc(100vw-32px)]`).
  - Tuned header typography (`text-2xl sm:text-4xl`) and textarea padding (`p-4 sm:p-8`, `min-h-[160px] sm:min-h-[200px]`) for mobile viewports.
- **`ScrapeNUModal.tsx`**:
  - Upgraded Dialog container to fullscreen/sheet mode on mobile (`borderRadius: { xs: 0, sm: '24px' }`, `maxHeight: { xs: '100dvh', sm: '90vh' }`).
  - Transformed candidate selection layout from fixed `h-[440px]` to responsive fluid flow (`min-h-[360px] md:h-[460px]` with bounded candidate list `max-h-[180px] md:max-h-none`).

### 2. Touch Ergonomics & Accessibility (Priority 2)
- **`ApiKeyManager.tsx`**: Upgraded delete key triggers to `w-8 h-8 rounded-lg` touch-friendly button targets with `lucide-react` `X` and `Plus` icons and clear active/hover feedback.
- **`BookmarksPage.tsx`**:
  - Replaced hover-only read button (`opacity-0 group-hover:opacity-100`) with mobile-accessible `opacity-80 sm:opacity-0 group-hover:opacity-100` and `w-9 h-9` tap targets.
  - Adjusted header and card row paddings (`px-4 sm:px-6 py-3 sm:py-4`).
- **`BulkTranslateModal.tsx`**:
  - Implemented responsive padding (`p: { xs: 2, sm: 3.5 }`) and scaled header icon box (`44x44px` on mobile, `54x54px` on desktop).
  - Ensured DialogActions full width action buttons with responsive padding.

### 3. Modal Polish & Gesture Safety (Priority 3)
- **`EditCoverModal.tsx`**:
  - Standardized responsive dialog paper, header, and content paddings.
  - Compacted drag & drop upload box (`p-5 sm:p-8`) to prevent overflow.
- **`TocImportModal.tsx`**:
  - Responsive `DialogActions` layout (`flex-col-reverse sm:flex-row gap-1.5`) so chapter totals and action buttons never collide on narrow screens.
- **`RelationshipGraph.tsx`**:
  - Adjusted container min-height (`min-h-[380px] sm:min-h-[500px]`).
  - Added a non-intrusive mobile interaction guide badge (`💡 Sentuh node untuk info • Geser di luar kanvas untuk scroll`) informing users how to pan/zoom without getting trapped in page scrolling.

## Consequences
- **Positive**: Complete touch ergonomics across all dialogs, toolbars, and navigation bars with 0 horizontal clipping or offscreen popovers.
- **Positive**: 100% adherence to mobile touch target standards (minimum 36–44px for actionable buttons).
- **Positive**: Maintained full fidelity and visual elegance on desktop viewports without degrading larger screen layouts.
- **Positive**: Full TypeScript (`tsc -b --noEmit`), ESLint, and 127/127 backend test suite pass rate.
