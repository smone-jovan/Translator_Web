---
trigger: always_on
---

# Translator Web — Safety Invariants

## Tooling Safety
- Never add Husky, lint-staged, Lefthook, pre-commit, commitlint, Git hooks, CI workflows, or package lifecycle hooks.
- Do not add, remove, upgrade, downgrade, or move npm/Python dependencies without explicit approval.
- Do not run npm install, npm update, npm audit fix, pip install, pip upgrade, or any command that rewrites lockfiles without approval.
- Do not mass-format files or add automatic write/fix scripts.
- Do not add `prettier --write .` or `eslint --fix` scripts.

## Change Control
- Read relevant code and existing tests before editing.
- Keep patches minimal and scoped to the approved task.
- Do not alter public API contracts, DB schema, migrations, authentication, workspace semantics, or frontend behavior without explicit approval.
- Do not push, merge, rebase, reset, stash, or delete files unless requested.
- If a task requires a dependency, hook, migration, or API-contract change: stop, explain impact and alternatives, and wait for approval.

## Filesystem Security
For every filesystem path derived wholly or partly from untrusted input (HTTP input, file metadata, import data, external content):
- Reject NUL bytes before filesystem access.
- Canonicalize using `Path.resolve()`.
- Verify containment using `candidate.is_relative_to(trusted_base)`.
- Never use string `startswith()` for path authorization.
- Return 403 for outside-base access and 404 for valid in-base missing files.

## Database Workspace Isolation
- Never use process-global mutable workspace selection.
- Workspace identity must be explicit and request/job-scoped.
- Background jobs must retain explicit workspace identity for their full lifecycle.
- Any workspace architecture change needs a call-site audit, approved plan, isolated commit, and concurrency regression tests.

## TypeScript Quality Gate
- Keep `typecheck` as `tsc -b --noEmit`.
- Keep `strict: true` enabled.
- Run `npm run typecheck`, `npm run lint`, and relevant pytest tests after applicable changes.
