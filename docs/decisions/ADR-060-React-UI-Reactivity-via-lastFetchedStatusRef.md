# ADR-060: React UI Reactivity via lastFetchedStatusRef

## Status
Accepted

## Context
The React desktop interface for the reading page suffered from state synchronization issues. When background processes modified a chapter's status (e.g., a background prefetch transitioning a chapter from `idle` to `processing` and then to `done`), the UI did not reflect these changes automatically. Users had to manually refresh the page (F5) to see the updated translation text or status indicators, leading to perceived bugs ("matiin hide thoughts aja wajib di f5 makin rusak").

## Decision
We modernized the React component lifecycle for chapter fetching to inherently track and respond to status mutations:
1. **State Trigger**: Added a `lastFetchedStatusRef` (using `useRef` to track state across renders without causing infinite loops) in `ReaderPage.tsx`.
2. **Effect Dependency**: We integrated the chapter's `translation_status` into the dependency array of the main fetching `useEffect`.
3. **Automatic Re-render**: When the backend updates the chapter status, polling hooks or socket events (if applicable) update the local context. The effect detects the mismatch between the new `translation_status` and `lastFetchedStatusRef.current`, immediately triggering a silent data refetch and rendering the new translated text seamlessly.

## Consequences

### Positive
- Fully reactive UI. Changes to system settings (like Hide Thoughts) or background translation completions reflect instantly.
- Eliminates manual F5 refreshes, creating a modern SPA (Single Page Application) feel.

### Negative
- Increased backend API calls, as any status change strictly forces a fresh GET request to the chapter endpoint.
