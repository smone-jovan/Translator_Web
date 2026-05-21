# ADR-036: Hallucination Audit and Garbled Output Cleanup

## Status
Accepted

## Date
2026-05-19

## Context
Long-form chapter translation can fail in two visible ways:

1. The model can enter repeated-word loops, producing the same token 10 times or more in sequence.
2. The model can emit corrupted hybrid garbage such as mixed-script symbol noise (`Shan! IV% Cold ⑦ Erliu 8 Shui #`) that is not valid narrative output.

These failures are hard to detect manually across large threads with dozens or hundreds of chapters. Users need a fast thread-level audit action and safer cleanup behavior in the translation pipeline.

## Decision
We add a lightweight hallucination defense in two layers:

1. **Thread-Level Audit Endpoint**
   - Add `/api/threads/{thread_id}/hallucination-check`.
   - The backend scans each translated chapter in the thread.
   - A chapter is flagged when the same word appears **10 or more times consecutively**.
   - The response includes per-chapter status, repetition count, and a short snippet for review.

2. **Garbled Output Cleanup**
   - Strengthen the system prompt to explicitly forbid mixed-script symbol-noise garbage.
   - Add backend post-processing that removes short lines dominated by suspicious corrupted tokens before saving/displaying final translated text.
   - Apply cleanup consistently to non-streaming translation, background translation persistence, and manual translation save.

3. **Per-Thread UI Trigger**
   - Add a `Check Hallucinate` action on each library thread card.
   - Show audit summary and chapter-by-chapter findings in a modal review surface.

## Alternatives Considered

### Database-Persisted Audit Table
- **Pros**: Historical audit snapshots, possible analytics.
- **Cons**: Extra schema, storage, migration, retention policy, stale results if chapters are retranslated.
- **Rejected**: On-demand audit is enough for current workflow and avoids persistence complexity.

### Full NLP Quality Scoring
- **Pros**: Could catch more subtle model failures.
- **Cons**: Heavier logic, more false positives, much harder to explain to users.
- **Rejected**: The repeated-word detector is simple, explainable, and directly targets an observed failure mode.

## Consequences
- Users can audit an entire thread quickly without reading every chapter manually.
- Repetition loops become visible with concrete chapter-level evidence.
- Garbled symbol-noise output is reduced both by prompt policy and backend cleanup.
- The cleanup remains conservative; subtle hallucinations can still require human review.
