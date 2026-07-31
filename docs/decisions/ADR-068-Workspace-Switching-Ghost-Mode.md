# ADR-068: Workspace Switching (Ghost Mode)

## Status
Accepted

## Date
2026-06-10

## Context
Users need the ability to maintain separate, private reading collections that are invisible during normal use. This is a privacy feature for users who share devices or want to keep certain reading material separate from their main library.

The system needs:
- Complete data isolation between workspaces (separate databases)
- PIN-protected switching to prevent accidental access
- Seamless transition without app restart
- All background processes (batch translations) must stop cleanly during switch

## Decision
Implement a dual-workspace system with PIN-authenticated switching via a new `system.py` router.

### Architecture
- **Two SQLite databases**: `main.db` (normal workspace) and a separate ghost workspace database
- **PIN protection**: A hardcoded PIN (`03697`) gates workspace transitions
- **API endpoints**:
  - `GET /api/system/workspace/current` — returns current workspace name
  - `POST /api/system/workspace` — switches workspace (requires PIN)
- **Safety**: `BackgroundTranslator.stop_all_batches()` is called before any switch to prevent data corruption from in-flight translations writing to the wrong database
- **UI trigger**: Long-press on profile icon reveals the PIN input

### Database Layer (`database.py`)
- `switch_workspace(name)` function swaps the active SQLAlchemy engine/session factory
- All subsequent requests use the new database until switched back

## Alternatives Considered

### Single Database with User/Profile System
- Pros: Standard multi-user pattern, no database switching
- Cons: Data is technically in the same file (forensically recoverable), more complex queries with user_id filtering
- Rejected: Physical database separation provides stronger privacy guarantees

### Encrypted Database for Ghost Mode
- Pros: Even stronger privacy (encrypted at rest)
- Cons: Requires SQLCipher or similar, performance overhead, key management complexity
- Rejected: Physical separation is sufficient for the threat model (casual device sharing)

## Consequences
- Complete data isolation between workspaces via separate SQLite files
- Background translations are safely stopped before workspace switch
- PIN is currently hardcoded — future improvement could allow user-configurable PINs
- Server restart resets to the default workspace
- No cross-workspace search or data sharing (by design)
