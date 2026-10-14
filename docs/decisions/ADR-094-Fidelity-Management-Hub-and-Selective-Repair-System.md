# ADR-094: Fidelity Management Hub & Selective Repair System

## Status
Accepted

## Date
2026-08-25

## Context
Following the implementation of [ADR-072](ADR-072-Post-Translation-Fidelity-Verification.md) (Post-Translation Fidelity Verification) and [ADR-080](ADR-080-Unified-Fidelity-And-Truncation-Detection.md) (Unified Fidelity & Truncation Detection), the system successfully flagged chapters with structural and truncation warnings in the SQLite database (`chapters.fidelity_warning`).

However, managing flagged chapters presented several UX and operational friction points:
1. **Lack of Centralized Visibility**: Users had to browse through hundreds of chapters across the grid to spot amber warning badges.
2. **All-or-Nothing Recovery**: The only automated tool was `POST /api/threads/{id}/fix-truncated`, which indiscriminately wiped all mid-sentence truncated translations to `idle` without granular user inspection or selection.
3. **Inability to Dismiss Minor False-Alarms**: For translations with minor paragraph grouping variations (e.g., ratio 0.8–0.9) where the translation was actually natural and complete, users had no way to clear the warning banner from the reader interface.
4. **No Bulk Selective Re-translation**: Translating flagged chapters required manually navigating into each chapter and clicking translate one by one.

## Decision
We designed and implemented a comprehensive **Fidelity Management Hub & Selective Repair System** spanning the backend and frontend:

1. **Backend Endpoints (`backend/routers/threads.py`)**:
   - `GET /api/threads/{thread_id}/fidelity-issues`:
     - Queries all flagged chapters (`fidelity_warning IS NOT NULL`).
     - Performs lightweight dynamic evaluation via `verify_translation_fidelity()` and `is_truncated_mid_sentence()`.
     - Categorizes issues into severity tiers (`critical`, `medium`, `minor`) and issue types (`truncated`, `empty`, `severe_drop`, `paragraph_drop`, `dialogue_drop`, `minor_ratio`).
     - Returns `ThreadFidelityAuditOut` containing complete diagnostic metrics (original/translated paragraph counts, ratio, truncation flag).
   - `POST /api/threads/{thread_id}/fidelity/dismiss`:
     - Accepts a list of `chapter_ids` to clear `fidelity_warning = NULL` in bulk without modifying existing translations.
   - `POST /api/threads/{thread_id}/fidelity/retranslate`:
     - Accepts a list of `chapter_ids`, resets their status to `idle`, clears `fidelity_warning` and `content_translated`, and queues them into `BackgroundTranslator.start_batch()` with existing RPM rate-limiting protections.
   - `POST /api/threads/{thread_id}/chapters/{chapter_id}/dismiss-fidelity`:
     - Single-chapter quick dismiss endpoint.
   - `POST /api/threads/{thread_id}/chapters/{chapter_id}/retranslate-fidelity`:
     - Single-chapter quick retranslate endpoint.

2. **Frontend Fidelity Management Hub (`src/components/FidelityManagementModal.tsx`)**:
   - **Interactive Checklist Grid**: Table with per-row checkboxes, master select/deselect toggle, and real-time search filtering.
   - **Severity Categorization Filter Tabs**:
     - `Semua (All Issues)`
     - `Kritis: Terpotong (Critical: Truncation / Empty / Severe Drop)`
     - `Sedang (Medium Drop / Dialogue Drop)`
     - `Ringan: 0.8–0.9 (Minor Structural Variations)`
   - **1-Click Quick Select**: Added a *"Pilih Semua Ringan"* button allowing users to instantly select all 0.8–0.9 ratio chapters and dismiss them en masse.
   - **Bulk Action Bar**:
     - *"Abaikan yang Dipilih (Dismiss)"*: Instantly clears warnings in bulk.
     - *"Perbaiki yang Dipilih (Re-translate)"*: Automatically launches sequential background translation for selected chapters.

3. **In-Reader & Control Integrations (`ChapterListControls.tsx` & `ChapterReader.tsx`)**:
   - **Chapter List Controls Toolbar**: Displays a dynamic `⚠️ {count} Issues` badge button when flagged chapters exist, opening the management modal.
   - **Reader Banner Quick Actions**: Upgraded the in-reader orange warning banner with three inline action buttons:
     - `[✓ Abaikan]`: Instantly dismisses the active chapter's warning.
     - `[↻ Perbaiki]`: Instantly resets and queues re-translation for the active chapter.
     - `[Kelola Semua]`: Opens the Fidelity Management Hub.

4. **Automated Test Suite (`backend/tests/test_routers/test_fidelity_management.py`)**:
   - Full test coverage for clean threads, multi-issue categorization, batch dismiss, single dismiss, and batch re-translation queuing.

## Consequences
- **Positive**: Operators and readers have complete visibility and granular control over translation quality anomalies.
- **Positive**: Minor variations (0.8–0.9 ratio) can be dismissed in seconds with 1 click.
- **Positive**: Critical truncations can be selected and batch re-translated with zero manual copy-pasting.
- **Positive**: Zero breaking changes to existing translation or database contracts; 100% backward compatible.
