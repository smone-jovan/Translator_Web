# ADR-040: Context Capacity Expansion and Character Relationship Visualization

## Status
Accepted

## Date
2026-05-20

## Context
As users translate and read larger web novels, the Lorebook (Context) dictionary accumulates a massive amount of terms. The previous system had a hard cap of 150 terms. When this cap was reached, old terms were silently archived and removed from the active translation prompt. Additionally, auto-extracted terms were labeled with a generic "Auto-extracted" note, making it hard to identify their origin if the translation memory was cleared.

Furthermore, reading long-form web novels involves keeping track of intricate interpersonal relationships (e.g., Master/Disciple, Factions, Enemies). Users requested a way to visualize these connections automatically.

## Decision
We implemented a two-part solution addressing context capacity and relationship mapping:

### 1. Context Capacity Expansion & Archival Safety
- Increased `max_context_terms` global limit from 150 to a maximum of 1000.
- Updated `SettingsPage.tsx` to provide granular limit options: 20, 50, 100, 200, 300, 500, 750, 1000.
- Updated `ContextEngine.auto_save_glossary` so that auto-extracted terms now append the original source term to their notes (e.g., `Auto-extracted: [Term]`) instead of a generic string.

### 2. Character Relationship Extraction & Visualization
- Created a new database table `character_relationships` tied to a `Thread`.
- Added a new AI extraction pass (`ContextEngine.extract_relationships_pass`) that prompts the LLM to analyze text and output a JSON array of character connections (`source`, `target`, `type`, `notes`).
- Extracted relationships are completely independent of a term's `is_archived` status. Even if a character is archived from the active glossary, their historical connections remain intact in the database.
- Integrated `react-force-graph-2d` into `ContextLibraryPage.tsx` to visualize these relationships as an interactive, physics-based network graph.

## Consequences
- **Positive:** Users can now visualize complex character networks without manual entry.
- **Positive:** A 1000-term context limit allows for massive, detailed novel translations without aggressive term eviction.
- **Positive:** The system is more transparent about where auto-extracted terms came from.
- **Negative/Risk:** A 1000-term context dictionary consumes a massive amount of tokens per chapter request (~25k tokens just for the prompt). Users must be aware of their API costs or local VRAM constraints when using the maximum limit. The UI now explicitly warns about token estimates.
