# Contributing to ReadOmni AI

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

1. Fork and clone the repository
2. Follow the [Quick Start](README.md#quick-start) guide in the README
3. Create a feature branch: `git checkout -b feature/your-feature`

## Code Style

### Backend (Python)
- Follow PEP 8
- Use type hints for function signatures
- Keep functions focused and small
- Write docstrings for public functions

### Frontend (TypeScript/React)
- Use functional components with hooks
- Follow existing Tailwind CSS patterns
- Keep components under 300 lines
- Use TypeScript interfaces for props

## Testing

```bash
# Backend tests
cd backend
py -m pytest tests/ -v

# Frontend lint + build
npm run lint
npm run build
```

All changes must pass existing tests before submitting a PR.

## Commit Convention

Use conventional commits:

```
feat: add new feature
fix: fix a bug
docs: update documentation
refactor: refactor code
test: add or update tests
chore: maintenance tasks
```

## Pull Requests

1. Keep PRs focused on a single change
2. Include a clear description of what and why
3. Reference related issues if applicable
4. Ensure all checks pass

## Architecture Decisions

For significant changes, create an ADR in `docs/decisions/`:
- Use the existing ADR format (ADR-XXX)
- Document context, decision, and consequences
- Get review before implementing

## Questions?

Open an issue for discussion before starting large changes.
