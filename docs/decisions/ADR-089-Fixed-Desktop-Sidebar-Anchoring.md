# ADR-089: Fixed Desktop Sidebar Anchoring & Mobile Navigation Isolation

## Status
Accepted

## Date
2026-08-07

## Context
On desktop viewports, users reported two visual and behavioral navigation issues:
1. `BottomNav.tsx` was displayed centered at the bottom of the screen simultaneously with the left desktop sidebar, creating visual clutter and duplicate controls.
2. `Sidebar.tsx` used `sticky top-0 h-screen`, which evaluated sticky positioning relative to its parent container height. When scrolling down long pages, the logo and top navigation items (Translate, Library, Context) scrolled up off-screen, making the sidebar appear "stuck" or partially scrolled away.

## Decision
1. **Explicit Viewport Scoping for `BottomNav.tsx`**: Add `md:hidden` back to `BottomNav.tsx` so floating bottom navigation is strictly rendered on mobile viewports (`< 768px`).
2. **Fixed Viewport Anchoring for `Sidebar.tsx`**: Change `Sidebar.tsx` positioning to `fixed top-0 left-0 h-screen h-[100dvh] z-50 w-20`.
3. **Layout Padding Compensation**: Add `md:pl-20` to `<main>` in `Layout.tsx` so main page content flows smoothly alongside the fixed 80px sidebar without overlap.

## Consequences
- Desktop navigation is clean, unified, and free of redundant bottom bars.
- The left sidebar remains 100% permanently anchored to the screen viewport (`top: 0`, `left: 0`) regardless of how far down the page is scrolled.
- Logo, navigation icons (Translate, Library, Context, Settings), and profile controls stay accessible at all times.
