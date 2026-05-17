# ADR-023: Infinite Title Polish Settings & Dynamic Actions System

## Context & Problem Statement
When polishing novel chapter titles in bulk (Infinite Polish feature), processing hundreds or thousands of chapters simultaneously can overload the local LLM context window or degrade performance. The system required a configurable title polish strategy that allows toggling between a safe "Soft Load" limit (50-150 titles) and an aggressive "Hard Load" (unrestricted processing).

Furthermore, Chinese novel metadata scraped from external sites (SFACG, Novel Updates) often arrives with noisy original titles containing parenthetical descriptive tags (e.g. `（无女主，轻松，变百）` as defined in ADR-020) and untranslated Chinese descriptions/synopses. The title polish button was identified as the ideal operational touchpoint to trigger secondary cleanup actions on the novel's main metadata dynamically.

## Proposed Decisions
1. **Extend Settings Schema & Database Migrations**:
   - Add `polish_mode` (`VARCHAR(20)`, default `"soft"`) and `polish_soft_limit` (`INTEGER`, default `100`) columns to the `global_settings` SQLite table.
   - Implement automatic SQL migrations inside `init_db()` in `database.py` via SQLAlchemy inspectors to dynamically execute `ALTER TABLE` statements on application start.

2. **Enhance Polish API Endpoint & Dynamic Metadata Cleanup**:
   - Update `/threads/{thread_id}/translate-titles` in `threads.py` to fetch current global polish settings.
   - **Soft Load Truncation**: When bulk translation is triggered in `soft` mode, slice the list of chapter titles to process up to the `polish_soft_limit`.
   - **Original Title Beautification**: If bulk title polish is clicked, isolate the core Chinese title in `thread.original_title` using the local AI provider by automatically stripping tags/brackets per ADR-020 guidelines.
   - **Description/Synopsis Translation**: Detect if the novel description (`thread.synopsis`) contains Chinese Hanzi characters. If it does, automatically translate it into the user's selected target language (e.g., Indonesian or English) using the local AI model.

3. **Premium Theme-Aware Settings UI**:
   - Integrate a grid-aligned **Infinite Title Polish** configuration card on the **Settings** page next to/below the prefetch card.
   - Build custom control panels featuring HSL-harmonized slider selectors, state synchronization triggers, toggle buttons, and responsive grid layouts designed for both mobile and desktop viewports.

## Consequences
- **Improved Performance**: Users can customize title translation loads to suit their system's memory constraints and GPU speed.
- **Dynamic Metadata Enrichment**: Book synopses and noisy Chinese titles are automatically beautified and translated upon clicking the polish button, resulting in a cleaner, premium book shelve representation.
- **Robust Sync**: Settings are persisted server-side, enabling uniform state replication across multiple LAN-synchronized devices (PC, iOS, Android).
