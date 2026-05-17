# ADR-013: Batch Loading Strategy - Soft vs Hard Load

## Status
Accepted

## Date
2026-05-17

## Context
As the "Batch Translation Studio" evolves, we need a clear strategy for handling different translation volumes and stability requirements. Large-scale bulk processing (10+ chapters) can strain LLM context windows or VRAM if not managed carefully, while single-chapter updates need to be precise.

The user requires a distinction between "Soft Load" (stability-focused) and "Hard Load" (performance-focused), both of which must enforce terminology consistency through mandatory overwriting.

## Decision
Implement a two-tier loading strategy within the Batch Translation Studio:

1.  **Soft Load (Sequential/Safety)**:
    *   **Volume**: Limited to 1 chapter at a time.
    *   **Behavior**: Enforced sequential processing.
    *   **Overwrite**: Mandatory (`overwrite: true`).
    *   **Goal**: Maximum stability and focus on term extraction for a specific single context.

2.  **Hard Load (Bulk/Performance)**:
    *   **Volume**: Adjustable via slider (3 to 20+ chapters).
    *   **Behavior**: High-volume batch processing.
    *   **Overwrite**: Mandatory (`overwrite: true`).
    *   **Goal**: Rapid processing of entire book segments while maintaining terminology consistency across all chapters.

## Alternatives Considered
### Option 1: Automatic Switching
*   Automatically switch to Soft Load if VRAM is low.
*   **Rejected**: Complexity in detecting backend hardware state from frontend; user prefers manual control.

### Option 2: Selective Overwrite
*   Only overwrite if terminology has changed.
*   **Rejected**: Determining "change" in terminology is computationally expensive; forcing overwrite is safer for consistency as per user request.

## Consequences
*   The UI must visually differentiate these modes (e.g., locking the slider in Soft Mode).
*   Backend must respect the `overwrite` flag in the `/batch-translate` endpoint.
*   Users gain clear mental models: "Soft" for one-by-one precision, "Hard" for massive updates.
