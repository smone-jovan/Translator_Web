# ADR-102: Universal Bi-Directional Engine Load Mode Synchronization

## Status
Accepted

## Date
2026-09-03

## Context
The Engine Load Mode ("Soft Load" / Sequential Safety Mode vs "Hard Load" / Parallel Burst Mode) controls AI translation concurrency across Batch Translation and Reader Prefetch.

Users can choose this mode in three distinct surfaces:
1. **Batch Translation Modal (`BulkTranslateModal.tsx`)**: Sequential Mode (🛡️ SAFE) vs Parallel Mode (⚡ SPEED).
2. **Reader Prefetch Overlay (`SettingsOverlay.tsx`)**: SOFT vs HARD load mode.
3. **Global Settings Page (`SettingsPage.tsx`)**: Engine Concurrency Speed card & Shared Prefetch mode toggle.

### Problem
Previously, selecting Hard or Soft in `BulkTranslateModal` only mutated component-local state without persisting to `localStorage` or `POST /api/settings`. When the modal reopened or the page reloaded, it fetched `/api/settings` and reverted back to the old database global setting. Furthermore, changes in one surface did not notify other mounted components in real time, causing state divergence where Reader Prefetch and Batch Translation did not reflect selections made in other surfaces.

## Decision
Establish a **Universal Bi-Directional Synchronization Architecture** for Engine Load Mode:

1. **Centralized Sync Layer (`src/lib/settingsSync.ts`)**:
   - `getStoredEngineLoadMode()`: Reads from `localStorage` checking both `'load_mode'` and `'prefetch_mode'`.
   - `syncEngineLoadMode(mode)`:
     - Updates both `localStorage.setItem('load_mode', mode)` and `localStorage.setItem('prefetch_mode', mode)`.
     - Dispatches a custom window event (`'engine_load_mode_changed'`) and standard `'storage'` event.
     - Persists to backend via `POST /api/settings` with `{ load_mode: mode, prefetch_mode: mode }`.
   - `useEngineLoadMode()`: A reactive React hook that binds components to real-time load mode changes.

2. **Cross-Component Reactivity**:
   - `BulkTranslateModal.tsx`: Uses `useEngineLoadMode()`. Toggling immediately updates local state, `localStorage`, backend database, and dispatches real-time events.
   - `SettingsOverlay.tsx`: Uses `syncEngineLoadMode` on button clicks and listens to `'engine_load_mode_changed'` to update its active button state.
   - `ReaderPage.tsx`: Initializes from `getStoredEngineLoadMode()`, listens to `'engine_load_mode_changed'`, and updates `syncEngineLoadMode` when a batch is initiated.
   - `LibraryPage.tsx`: Calls `syncEngineLoadMode` when starting a batch from the library.
   - `SettingsPage.tsx`: Uses `syncEngineLoadMode` in `handlePrefetchModeChange` and listens to `'engine_load_mode_changed'` to keep its UI cards synchronized with modal selections.

3. **Backend Persistence Guarantee (`backend/routers/batch.py`)**:
   - When `/api/threads/{thread_id}/batch-translate` receives `load_mode`, it automatically updates `gs.prefetch_mode = req.load_mode` and commits to `GlobalSetting`, ensuring backend state is always synchronized even when batches are triggered via direct API calls.

## Consequences
- **Positive:** Selecting Soft or Hard in ANY location (Batch Modal, Reader Prefetch, or Global Settings) immediately updates and persists the choice across all surfaces and in the database.
- **Positive:** Zero reversion back to stale global settings when reopening modals or navigating.
- **Positive:** Zero latency cross-component UI updates without page reloads.
