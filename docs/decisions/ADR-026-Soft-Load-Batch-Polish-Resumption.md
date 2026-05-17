# ADR-026: Soft Load Batch Polish Resumption and Reset System

## Status
Accepted

## Date
2026-05-17

## Context
When performing title polishing on extremely large novels (often containing 1,000+ chapters), running a single bulk translation request would overwhelm local LLM token context limits and memory boundaries. To mitigate this, a **Soft Load** mechanism was introduced to batch polish requests (e.g. up to 100 chapters per batch).

However, an interaction issue arose in the frontend:
* The primary action button was configured to check if *any* single chapter was polished. If true, the action would transition to **Re-polish** (which maps to backend `repolish=true`).
* In Soft Load mode, passing `repolish=true` forced the backend to start scanning from Chapter `0` again, looking for the first 100 chapters to process.
* This created an infinite loop: clicking the button repeatedly would continuously re-polish chapters 0–99 over and over, while chapters from 100 onwards remained unpolished and unformatted.

## Decision
We implemented a dynamic, state-aware frontend progression logic combined with a decoupled manual reset action:

1. **Polish Remaining Mode:** If *some* chapters are polished but not *all*, the primary button dynamically shows **"Polish Remaining"** and runs with `repolish=false`. This instructs the backend to skip all already-polished chapters and immediately process the next batch starting from chapter 100, then chapter 200, etc.
2. **Re-polish All Mode:** The primary button only transitions to **"Re-polish All"** (with `repolish=true`) once *every* single chapter in the thread has been polished.
3. **Decoupled Reset Action:** Added a dedicated **"Reset & Re-polish All"** button within the Polish Settings popover. This allows users to intentionally clear and overwrite all polished titles from scratch, regardless of the current batch completion state.

## Alternatives Considered

### Stateful Page Offset Tracker
* **Pros:** Allows manual navigation through batches.
* **Cons:** Adds state complexity and user cognitive load; automated incremental "Polish Remaining" is more convenient and matches expected "continue where I left off" behavior.
* **Rejected:** In favor of the automated "Polish Remaining" progression logic.

### Pure Backend Auto-Offsetting on `repolish=true`
* **Pros:** Keeps frontend simple.
* **Cons:** Deprives the user of the ability to actually perform a full reset/re-translation when they genuinely want to change polish styles.
* **Rejected:** Separating the two modes in the UI is necessary to respect both use cases.

## Consequences
* **Seamless Batch Continuation:** Large novels can now be polished completely in multiple rapid increments.
* **GPU Memory Friendly:** Local LLMs remain responsive since each request is strictly capped by the Soft Load limit.
* **Flexible UX:** Users maintain full control over whether to resume a polish operation or force a total reset of the novel's titles.
