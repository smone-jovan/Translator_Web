# ADR-013: Configurable Prefetch System (Range & Mode)

## Status
Accepted

## Date
2026-05-17

## Context
Currently, the system prefetches subsequent chapters to ensure a smooth reading experience. However, the range of prefetching (how many chapters ahead) is relatively fixed or opaque to the user. Different users have different reading speeds and server resource constraints (e.g., local LLM vs cloud API costs).

## Decision
Implement a user-configurable prefetch range (1-5 chapters) that is synchronized across the global settings and accessible within the reader interface.

### Key Components:
1. **Persistence**: Add a `prefetch_count` field to the `GlobalSetting` database model.
2. **Global Access**: Expose this setting in the main **Settings Page**.
3. **Contextual Access**: Add a slider for prefetch range inside the **Reader (Chapter View)** settings overlay for immediate adjustment during reading sessions.
4. **Prefetch Mode (Soft vs Hard)**:
   - **Soft Load (Sequential)**: Processes one chapter at a time in the background. Stable and resource-efficient.
   - **Hard Load (Parallel)**: Triggers simultaneous translation for all chapters in the range. Optimized for maximum speed.
5. **Real-time Feedback**: 
   - Implement automatic polling (5s) in the Reader UI when prefetching is active.
   - Show visual "Aggressive Prefetch" or "Translating" status indicators in the chapter list.

## Alternatives Considered
- **Client-only storage (localStorage)**: Rejected because prefetching is a core behavioral setting that should persist across devices (e.g., set on Desktop, respect on Mobile).
- **Infinite Prefetch**: Rejected to prevent uncontrolled token usage and server load.

## Consequences
- **User Experience**: Improved perceived performance for fast readers (higher prefetch) and better cost control for budget-conscious users (lower prefetch).
- **Server Load**: Potential increase in peak load if many users set it to 5, but managed by the existing background task queue.
