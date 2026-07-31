# ADR-083: Dynamic Ghost Mode PIN Authentication

## Status
Accepted

## Date
2026-07-26

## Context
ADR-068 established physical database separation for "Ghost Mode" private reading collections, with workspace switching authenticated by a hardcoded PIN (`03697`).

However, hardcoding the PIN in `backend/routers/system.py` prevented users from personalizing their PIN security. In addition, when switching between `app.db` and `ghost.db`, the PIN value needed to remain consistent across database transitions so users could seamlessly switch back and forth.

## Decision
1. Add `ghost_pin: Mapped[str] = mapped_column(String(100), default="03697")` to `GlobalSetting` in `backend/database.py`.
2. Add automatic SQLite schema migration in `init_db()` (`ALTER TABLE global_settings ADD COLUMN ghost_pin VARCHAR(100) DEFAULT '03697'`).
3. Update `switch_workspace()` to automatically sync `ghost_pin` from `app.db` to `ghost.db` whenever switching workspaces.
4. Refactor `switch_workspace_endpoint()` in `backend/routers/system.py` to dynamically load `ghost_pin` from `SessionLocalMain()` rather than relying on a hardcoded string.
5. Add UI settings in `SettingsPage.tsx` under *Privacy & Security* allowing users to inspect (with show/hide toggle) and update their Ghost Mode PIN.

## Alternatives Considered

### Storing PIN only in local environment / `.env`
- Pros: Simple text storage.
- Cons: Cannot be modified via Web UI without restarting backend server; inconsistent with other user settings.
- Rejected: Web UI configuration is preferred for usability.

### Hashing the PIN (e.g. bcrypt/argon2)
- Pros: Stronger cryptographic security against SQLite database inspection.
- Cons: Overhead for local personal reading tool threat model; PIN reset recovery is complex if forgotten.
- Rejected: Unhashed string in local SQLite database is sufficient for casual device-sharing threat model.

## Consequences
- Users can customize their Ghost Mode PIN at any time through the Settings page.
- Workspace switching validates against the dynamic PIN stored in SQLite.
- Standard default PIN (`03697`) is preserved for unconfigured installs.
- Multi-workspace database transitions automatically keep PIN settings synchronized.
