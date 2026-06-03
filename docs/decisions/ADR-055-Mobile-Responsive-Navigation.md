# ADR-013: Mobile Responsive Navigation (Bottom Nav)

## Status
Accepted

## Date
2026-05-17

## Context
The application currently uses a sidebar-based navigation system. While functional, sidebar navigation (hamburger menus) on mobile devices often requires awkward top-screen reaches and obscures the main content when active. Modern mobile UX patterns favor "Bottom Navigation Bars" for core actions, as they are within the ergonomic reach of the thumb.

## Decision
Implement a dedicated `BottomNav` component for mobile viewports (widths < 768px). 

Key features:
- Display core navigation items: Library, Translate, History, and Settings.
- Persistent at the bottom of the screen with a glassmorphism effect (matching the existing design system).
- Hide the sidebar on mobile to prevent UI clutter.
- Integrate into the main `Layout` component.

## Alternatives Considered

### Floating Action Button (FAB)
- Pros: Simple, doesn't take up much space.
- Cons: Only allows for 1-2 primary actions; harder to use for full site navigation.
- Rejected: We need access to multiple pages (Library, Settings, Translate).

### Sidebar Hamburger Only
- Pros: Already implemented.
- Cons: Poor ergonomics on tall mobile screens.
- Rejected: Doesn't meet the "premium" and "mobile-friendly" objective.

## Consequences
- Better ergonomics for mobile users.
- Increased complexity in `Layout.tsx` to handle conditional rendering of navigation based on viewport.
- Need to ensure consistent active states between the sidebar (desktop) and bottom nav (mobile).
