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

1. Update `memory.md` with the task id, decisions, changed areas, and verification.
2. Update `docs/tasks/backlog.md` with the task status and next candidates.
3. Run the relevant tests/checks.
4. Commit with a focused `[TASK-###]` message.

## Deployment

Deploy `main` to the VPS with:

```powershell
.\scripts\deploy.ps1
```

The script pushes `main`, SSHes to `208.109.241.169`, fast-forwards
`/home/wolfb/mlbot`, rebuilds `mlb-irc-bot` with Docker Compose, restarts it,
and runs `python -m mlb_irc_bot --dry-run` inside the container. It fails if
the local or remote checkout has uncommitted changes.

Useful options:

```powershell
.\scripts\deploy.ps1 -SkipPush
.\scripts\deploy.ps1 -DryRun -AllowDirty
.\scripts\deploy.ps1 -DeployHost other-host -RemotePath /path/to/mlbot
```

## Live API Probes

Normal tests should not require network access. Use this opt-in command for MLB API drift checks:

```powershell
.\.venv\Scripts\mlb-api-probe --date 2026-05-31
```
