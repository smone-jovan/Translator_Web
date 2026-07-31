# ADR-085: Mobile Screen-Sleep Recovery & Display Mode Persistence

## Status
Accepted

## Date
2026-08-01

## Context
When reading web novel chapters on mobile webviews (iOS Safari, Android Chrome, Opera Touch), putting the phone to sleep or locking the screen fires `visibilitychange` and suspends execution. Upon waking the device:
1. Chapter content vanished or rendered blank because `lastFetchedIdRef` prevented re-fetching when `chapterContent` state was lost/null on wake-up.
2. Display mode (`ORI`, `TRS`, `BOTH`) randomly reset to default `both` because clicking mode toggle buttons in `ChapterReader.tsx` did not persist the selection to `localStorage`.

## Decision
1. **Sync `displayMode` to `localStorage` Continuously**: Added a `useEffect` in `ReaderPage.tsx` and updated quick-toggle handlers in `ChapterReader.tsx` to save `localStorage.setItem('display_mode', mode)` on every selection change.
2. **Session Storage Chapter Caching**: Cache fetched chapter content in `sessionStorage` (`readomni_chapter_cache_${threadId}_${ch.id}`) for instant 0ms restoration upon waking from sleep.
3. **`chapterContent` Null Guard**: Require `chapterContent !== null` check before `lastFetchedIdRef` early-returns, ensuring data fetches automatically trigger if content is missing.
4. **Mobile Wake Recovery Listener**: Added a `visibilitychange` / `focus` event listener in `ReaderPage.tsx` to automatically re-verify and restore chapter content when the document becomes visible.

## Consequences
- Readers on mobile devices experience seamless screen-lock and sleep transitions without losing text or having display modes reset.
- 0ms instant text restoration from `sessionStorage` cache eliminates screen flicker.
