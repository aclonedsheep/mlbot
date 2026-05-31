# Development

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

## Checks

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
docker compose config
```

## Checkpoints

Before every substantial git checkpoint:

1. Update `memory.md` with the iteration, decisions, changed areas, and verification.
2. Run the relevant tests/checks.
3. Commit with a focused message.

## Live API Probes

Normal tests should not require network access. Add opt-in probes for MLB API drift checks and keep recorded fixtures for deterministic tests.
