# ADR-042: UI Library Consolidation (MUI to Tailwind/shadcn)

## Status
Accepted

## Date
2026-05-30

## Context
The frontend currently uses two UI libraries simultaneously:
- **MUI v9** (`@mui/material`, `@mui/icons-material`, `@emotion/react`, `@emotion/styled`) -- used in `BulkStatusCenter.tsx`, `LibraryPage.tsx`, and other components for `Menu`, `IconButton`, `Paper`, `LinearProgress`, `Typography`, etc.
- **TailwindCSS v4 + shadcn/ui pattern** -- used everywhere else with `class-variance-authority` + `tailwind-merge` for `Button`, `Card`, `Textarea`, `AlertDialog`.

This dual-library approach causes:
1. **Bundle bloat** -- MUI's runtime + Emotion CSS-in-JS adds ~150KB+ to the bundle even for minimal usage.
2. **Inconsistent styling** -- Components use either `sx` prop (MUI) or Tailwind classes, making the codebase harder to maintain.
3. **Dependency churn** -- Two styling systems (`@emotion` vs Tailwind) with different specificity rules can cause style conflicts.
4. **Slower dev experience** -- MUI's `styled()` API and Emotion have different mental models from Tailwind utilities.

## Decision
Remove MUI entirely and replace all MUI components with Tailwind/shadcn equivalents:

| MUI Component | Replacement |
|---|---|
| `Menu` / `MenuItem` | Radix `DropdownMenu` (shadcn pattern) |
| `IconButton` | Custom `Button` variant (`variant="ghost"`, `size="icon"`) |
| `Paper` | `Card` or plain `div` with Tailwind `bg-*` + `rounded-*` |
| `LinearProgress` | Custom `Progress` bar with Tailwind |
| `Typography` | Native `<p>`, `<h1>`-`<h6>` with Tailwind text utilities |
| `Tooltip` | Radix `Tooltip` (shadcn pattern) |
| `CircularProgress` | Custom SVG spinner or `Loader2` from `lucide-react` |

### Implementation Plan
1. Add new shadcn/ui components as needed (`dropdown-menu`, `progress`, `tooltip`).
2. Replace MUI usages file-by-file, starting with the simplest (`BulkStatusCenter.tsx`).
3. Remove MUI packages from `package.json` and `vite.config.ts` optimized deps.
4. Run `npm run lint` and verify zero errors.

## Alternatives Considered

### Keep MUI for complex components only
- **Pros**: No migration effort for existing Menu/Tooltip usage.
- **Cons**: Still carries the full MUI runtime in the bundle; two styling systems remain.
- **Rejected**: The cost of maintaining two libraries outweighs the migration effort.

### Switch entirely to MUI (remove Tailwind)
- **Pros**: Single design system with comprehensive component coverage.
- **Cons**: MUI's `sx` prop is verbose; loses the utility-first workflow; MUI v9 is heavier than Tailwind + shadcn; contradicts existing project conventions.
- **Rejected**: The project already has extensive Tailwind investment (5 themes, glassmorphism utilities).

## Consequences
- **Positive:** ~150KB+ bundle size reduction by removing MUI runtime and Emotion.
- **Positive:** Single styling paradigm (Tailwind utilities) across all components.
- **Positive:** Faster iteration with utility-first CSS and shadcn component primitives.
- **Negative/Risk:** Short-term migration effort (~2-4 hours for all MUI usages).
- **Negative/Risk:** Need to recreate some MUI-specific behaviors (Menu positioning, Tooltip delays) with Radix primitives.
