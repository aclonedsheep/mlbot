# Release Readiness Backlog

This backlog is the numbered task ledger for release-readiness cleanup. Earlier
project history is recorded in `memory.md`.

Note: this file was restored during TASK-062 because the 2026-06-07 handoff
prompt expected `docs/tasks/backlog.md`, said TASK-061 was complete, and the
checkout did not contain the backlog file.

## Completed

### TASK-061 - Restore Pregame Alert Announcements

- Status: Done.
- Source: 2026-06-07 handoff prompt and `memory.md` Iteration 15.
- Result: pregame announcements were restored by polling near-start games and
  starting scheduling only after the bot confirms its configured-channel join.

### TASK-062 - Restore Release Workflow Breadcrumbs

- Status: Done.
- Goal: make continuation sessions self-sufficient by restoring agent handoff
  files, a task backlog, and local ignore rules for test scratch directories.
- Verification: `pytest` passes with 44 tests; `ruff check .` passes;
  `python -m mlb_irc_bot --dry-run` passes.

### TASK-063 - Validate Release Workflow

- Status: Done.
- Goal: run the restored release-readiness workflow locally and document any
  deployment dry-run limitations.
- Result: added Windows execution-policy-safe deployment dry-run docs and
  confirmed the local release checks still pass.
- Verification: `pytest` passes with 44 tests; `ruff check .` passes;
  `python -m mlb_irc_bot --dry-run` passes; the documented process-scoped
  PowerShell deployment dry run prints the intended SSH deploy command without
  pushing or connecting.
- Gap: `docker compose config` is still blocked on this machine because
  `docker` is not installed on PATH.

## Current

### TASK-064 - Restore Live Announcement Scheduler

- Status: Ready for deploy.
- Goal: restore live IRC announcements after the bot remained connected and
  command-responsive but stopped posting channel alerts.
- Finding: direct VPS/container checks showed `mlbotslop` answering commands in
  `#mlbtest`, but a scheduler probe found fresh unseen alerts while the SQLite
  alert store had no rows after the previous deploy window.
- Result: the live scheduler now logs and survives poll failures, skips only a
  broken game's alert collection, and does not let one failed IRC send terminate
  the scheduler task. Scheduler restarts also baseline already-live/final games
  so old plays are not dumped into the channel as backfill.
- Verification: `pytest` passes with 47 tests; `ruff check .` passes;
  `python -m mlb_irc_bot --dry-run` passes.
- Pending: VPS deploy health check and focused `#mlbtest` confirmation that
  channel alerts resume.

## Next Candidates

- Audit top-level `@help` output against `docs/COMMANDS.md` for newer commands.
- Add a Docker Compose config check to CI or another environment where Docker is
  available.
- Push and deploy the accumulated `main` release commits when ready.
