# Development

## Setup

Use Python 3.12. The current `ircrobots` release pins AnyIO 2, so the project metadata intentionally excludes Python 3.13 while the compatible HTTPX pin still imports deprecated stdlib modules removed in 3.13.

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

Normal tests should not require network access. Use this opt-in command for MLB API drift checks:

```powershell
.\.venv\Scripts\mlb-api-probe --date 2026-05-31
```
