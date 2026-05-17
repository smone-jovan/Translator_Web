# ADR-027: Stateful Volume Transition Guards for Sequential Web Novel Layouts

## Status
Accepted

## Date
2026-05-17

## Context
In sequential novels translated from sources like SFACG, chapters are structured into volumes. Automatic volume detection works by looking for sequential chapter resets (e.g. going from Chapter 99 to Chapter 1). 

However, this automatic transition logic was fragile when encountering prologues or epilogues:
1. When the novel reaches a prologue, the volume transition is correctly triggered because prologues are parsed as separate boundaries.
2. The subsequent chapter resets back to `1` (or `01`).
3. Because Chapter 1 has a lower numerical value than the prologue chapter's order/sequence number, the sequential drop detector (`raw_num < prev_raw_num`) fired *again* on the very next chapter.
4. This created a "double volume increment" on back-to-back chapters (e.g. transitioning directly from Volume 1 to Volume 3, skipping Volume 2 entirely).

## Decision
We updated the `VolumeTransitionManager` in [threads.py](file:///d:/code_xI/Translator_Web/backend/routers/threads.py) to incorporate stateful guards and explicit prologue parsing:

1. **Stateful Double-Increment Guard (`volume_just_incremented`):** A stateful boolean flag was added to tracking sweeps. If a volume increment was just triggered on chapter $n$, the sequential numerical drop detector is temporarily suppressed on chapter $n+1$. This gives the new sequence number space to stabilize (typically resetting to `1`) without double-triggering.
2. **Dedicated Prologue Keywords Matching:** Added native parsing of Chinese and English prologue indicators (`序章`, `楔子`, `prologue`, etc.). If a prologue is hit past the start of the thread:
   * The volume number is incremented.
   * The chapter number is set to `0`.
   * The double-increment guard is activated for the successor chapter.

## Alternatives Considered

### Disabling Automatic Transition for Prologues
* **Pros:** Simpler sequence parsing.
* **Cons:** Prologues would be lumped into the previous volume incorrectly, degrading the premium reader experience.
* **Rejected:** In favor of native prologue handling.

### Purely Manual Volume Splits
* **Pros:** Extremely predictable.
* **Cons:** Puts the burden of configuring exact chapter numbers (e.g. inputting `[100, 200, 305]`) entirely on the user.
* **Rejected:** Automatic volume detection is a premium feature that should work seamlessly without user intervention.

## Consequences
* **Accurate Layouts:** Sequential novels with prologues are now beautifully divided into volumes automatically.
* **Zero Intervention:** Users no longer need to debug volume increments or manually override chapters.
* **Robust Sequencing:** Resilient to arbitrary numbering schemas common in Chinese web novel translations.
