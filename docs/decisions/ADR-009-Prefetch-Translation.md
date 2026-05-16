# ADR-009: Implement Prefetch Translation System

## Status
Accepted

## Date
2026-05-16

## Context
Users experience a "wait time" when finishing a chapter and moving to the next one because the translation starts from scratch. To provide a premium, seamless reading experience, the system should anticipate the user's progress and translate the next chapter in the background.

## Decision
1.  **Backend Trigger**: Modify `run_persistent_translation` in `translate.py`. Once a chapter finishes (`status="done"`), the task will check the `global_settings.prefetch_enabled` flag.
2.  **Chaining Logic**: If enabled, find the next chapter (by `order`) in the same `thread_id`. If the next chapter has no translation, trigger a new background task for it.
3.  **Concurrency Control**: Ensure only one prefetch task runs at a time to avoid overloading the local LLM.
4.  **UI Feedback**: Add a "Prefetch" toggle in the Reader settings so users can opt-out if they have limited hardware resources.

## Consequences
- Dramatically reduced wait time when navigating between chapters.
- Higher GPU/CPU utilization as the LLM works ahead of the user.
- Smoother "Next Chapter" transitions with immediate content availability.