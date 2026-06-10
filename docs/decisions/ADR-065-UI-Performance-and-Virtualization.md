# ADR-065: UI Performance Optimization and Virtualization

## Status
Accepted

## Date
2026-06-10

## Context
As the application scales, users manage novels with thousands of chapters and hundreds of glossary terms. Recent feedback indicated severe UI lag ("freeze" and "stutter") in two primary areas:
1. **Bulk Translate Modal:** Dragging the selection slider or checking a single chapter caused a massive re-render of all 1,000+ chapter checkboxes, blocking the main thread. Furthermore, simply scrolling the list of 1,000+ DOM nodes caused layout thrashing and severe scrolling lag.
2. **Context Library Page:** Loading the page or typing in the search bar caused the application to render hundreds of heavy Term Cards (containing icons, tooltips, and badges) simultaneously, resulting in significant input lag and rendering delays.

## Decision
We decided to implement targeted rendering optimizations to ensure the UI remains "butter-smooth" even with extreme data sizes:

1. **Memoization for Expensive Subtrees (`React.memo` & `useMemo`):**
   - The heavy Markdown rendering engine in `ChapterReader.tsx` was wrapped in `useMemo` so that scrolling the page (which updates a scroll progress percentage state) no longer re-evaluates and re-renders the huge text body.
   - List items in the `BulkTranslateModal` were extracted into a `React.memo` component (`ChapterItem`). We derived a `Set` for `selectedIds` to ensure `O(1)` lookup. This guarantees that toggling a checkbox only re-renders the specific item that changed, rather than all 1,000+ items.

2. **DOM Virtualization (`react-virtuoso`):**
   - We installed `react-virtuoso` to virtualize the manual chapter selection list in the `BulkTranslateModal`.
   - Instead of rendering all chapters into the DOM, the modal now only renders the ~10 items visible in the scroll container. This completely eliminated the scrolling layout lag.

3. **Progressive Rendering / Pagination (Slicing):**
   - For the `ContextLibraryPage`, implementing a grid virtualizer is often clunky. Instead, we implemented a simple "Load More" pagination system.
   - The page now only renders the first 50 matched terms by default. If the user scrolls down, they can click a button to reveal the next 50. This keeps the initial DOM extremely light and ensures instant search input responsiveness.

## Consequences
- **Positive:** The UI is now perfectly smooth regardless of how many chapters or glossary terms exist in the database.
- **Positive:** Memory consumption on the client is drastically reduced because thousands of React Elements and DOM nodes are no longer instantiated at once.
- **Negative:** We added a new dependency (`react-virtuoso`) to the frontend.
- **Negative:** The Context Library now requires clicking "Load More" to view all terms at once, though searching remains instant and filters the entire dataset before slicing.

## Dependencies Added
- `react-virtuoso` (Frontend package for virtualization)
