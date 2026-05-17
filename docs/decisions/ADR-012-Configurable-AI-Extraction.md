# ADR-012: User-Configurable AI Extraction Windows

## Status
Accepted

## Date
2026-05-17

## Context
As the novel grows, a fixed extraction window (e.g., only the first chapter or a hardcoded 25 chapters) becomes inefficient. Users with different hardware or API limits need the ability to control how much context is sent to the AI to manage token costs and extraction depth.

## Decision
Implement a Dual-Mode AI Extraction Setting system in the Context Library.

### UI Implementation
- **Easy Mode**: Three standardized presets (Quick, Normal, Deep) to simplify the UX for most users.
- **Advanced Mode**: Manual inputs for `Chapter Count` (how many chapters ahead to scan) and `Sample Size` (how many characters to take from each chapter).
- **Token Transparency**: Real-time display of estimated input tokens based on the formula `(Chapter Count * Sample Size) / 4`.

### Backend Implementation
- Updated `POST /api/threads/{id}/extract-context` to accept `chapter_count` and `sample_size` parameters.
- Logic uses `UserBookmark` to determine the starting chapter (Last Read) and offsets from there.

## Consequences
- **User Empowerment**: Users can tailor the AI behavior to their specific model constraints (e.g., 8k context window vs 128k).
- **Cost/Resource Efficiency**: Prevents accidental large requests to local or cloud LLMs.
- **Improved Accuracy**: Allows for "Deep Scans" across many chapters to find recurring terms that might be missed in a single-chapter scan.
