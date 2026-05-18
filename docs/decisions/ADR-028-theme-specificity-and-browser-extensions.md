# ADR-028: High Specificity Theming & Browser Auto-Dark Mitigations

## Status
Accepted

## Date
2026-05-18

## Context
The application utilizes a custom HSL-based design token system to provide five premium visual themes (Black, OLED, White, Sepia, Omni). The transition to TailwindCSS v4 natively supports dynamic color mappings via the `@theme` block, but we observed severe visual corruption (e.g., Sepia theme appearing with a black background and white text, or White theme appearing dark grey) on certain user configurations, alongside intermittent layout shifts in the desktop sidebar causing it to "flicker" or disappear.

Investigation confirmed that the visual corruption was **not** a CSS mapping failure, but rather the result of browser-level auto-inversion engines—specifically **Opera GX "Force Dark Pages"** and the **Dark Reader** extension. These tools inject heuristic-based DOM inversions that forcefully override our custom light themes (White, Sepia).

## Decision
1. **Tailwind v4 `@theme` Integration:** Refactor `index.css` to use the native Tailwind v4 `@theme` block (e.g., `--color-background: var(--background);`) to ensure proper utility class generation.
2. **Elevated CSS Specificity:** Move all `[data-theme="*"]` declarations completely outside of `@layer base`. This guarantees they carry the absolute highest CSS specificity and cannot be overwritten by default Tailwind dark modes or standard user-agent styles.
3. **Browser Engine Mitigations:** Add `<meta name="color-scheme" content="light dark" />` and `<meta name="darkreader-lock" />` to `index.html` to instruct compatible extensions to disable auto-inversion.
4. **Desktop Navigation Simplification:** Completely remove the `translate-x` transitioning logic from `Sidebar.tsx`. Since mobile screens use `BottomNav.tsx`, the desktop sidebar is now permanently rendered using standard `hidden md:flex shrink-0`, eliminating responsive layout flickering entirely.

## Consequences
- **Theme Stability:** The CSS variables are now highly resilient and correctly mapped. 
- **Known Gotcha (Opera GX):** Some deep browser features like Opera GX's "Force Dark Pages" operate at the renderer level and aggressively ignore meta tags. **Users must manually disable these extensions/features for `app.readomni.com` (or localhost) for the White and Sepia themes to render correctly.**
- **Layout Stability:** The desktop sidebar is now bulletproof across all viewport resizing events without hydration or animation artifacts.
