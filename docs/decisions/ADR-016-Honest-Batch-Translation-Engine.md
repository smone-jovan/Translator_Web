# ADR-016: Honest Batch Translation Engine with VRAM Safety

## Status
Accepted

## Date
2026-05-17

## Context
Following the initial design of Batch Translation Studio, users observed:
1. Simulating bulk progress was prone to race conditions and didn't reflect true background execution.
2. Custom and manual selections were complex, and the distinction between Easy and Advanced modes needed streamlining.
3. Token estimation was inaccurate, underrepresenting output tokens and glossary scanning costs.
4. Single-threaded execution was safe but could be slow on high-end hardware, while full concurrent execution risked GPU VRAM Out-Of-Memory (OOM) failures.

## Decision
Refine the engine into a state-aware, background-tracked **Honest Batch Translation Engine**:

1. **State-Aware Background Queue**:
   - The backend tracks the active batch thread inside global state (`_active_batch_job`).
   - If an active job is detected, it returns progress (`completed`, `total`, `active`, `chapter_title`) via `/api/threads/active-batch`.
   - The frontend's `BulkStatusCenter` polls `/api/threads/active-batch` directly rather than simulating timers, making it bulletproof against page reloads.

2. **VRAM Safety Engine Settings**:
   - **Sequential Mode (Soft Load) 🛡️**: Processes one chapter at a time. The safest option, highly recommended for budget/standard GPUs. Implemented via a global asyncio Lock (`translation_lock`) that forces all background, manual, and prefetch translations to wait in line, guaranteeing only 1 AI request runs concurrently on the local LLM.
   - **Parallel Mode (Hard Load) ⚡**: Initiates all translations concurrently, pushing maximum throughput on high-end GPUs at the cost of transient VRAM spikes. Bypasses the lock.

3. **Honest Multi-Dimensional Token Estimation**:
   - Corrected the glossary extraction input/output formula: 15 chapters = ~3,750 tokens (~250 tokens per chapter).
   - Added context input + segment translation output estimates: ~6,500 tokens per chapter.
   - Dynamically calculates totals based on selections and displays safe vs warning color-coded badges matching the VRAM load strategies.

4. **Improved Selectors**:
   - **Easy Selection**: Combines an interactive chapter-quantity slider (targeting next untranslated chapters first) with the core safety speed toggles.
   - **Custom Checkbox Selection**: Streamlined with quick actions ("Untranslated Only", "Select All", "Clear All") and a high-performance scrollable check list.

## Consequences
- High-end users can harness full GPU capability safely using Parallel Mode, while budget users remain protected under Sequential Mode.
- No more simulated or fake timers; all batch progress indicators represent true database records.
- Accurate context size indicators prevent token overflow bugs during heavy translate sessions.
- **VRAM Spikes Prevented**: Under soft prefetching/sequential loads, even if multiple prefetch or manual clicks happen, tasks queue up gracefully on the server instead of bombarding the local LLM concurrently.
