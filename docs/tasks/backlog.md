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

### TASK-064 - Restore Live Announcement Scheduler

- Status: Done.
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
  `python -m mlb_irc_bot --dry-run` passes; the VPS deploy script rebuilt and
  restarted the container; the in-container dry-run passes.
- Live check: after deploy, scheduler logs showed stale first-poll suppression
  for final games and the live SF@CHC game, and `mlbotslop` answered private
  `@mlb *` checks in `#mlbtest`. No new channel alert appeared during the watch
  windows because the live feed still had only the same alert keys that were
  baselined at scheduler startup.

## Current

### TASK-065 - Add Alert Game Context And Calmer Formatting

- Status: Done.
- Goal: make live announcements more informative by appending quick game
  updates where the live feed exposes score, inning, and outs, then reduce
  formatting noise in dense command replies.
- Result: HR, scoring, win-probability, high-leverage, hard-hit/barrel,
  bases-loaded, no-hit, cycle, and immaculate-inning alerts now include a
  compact game update when available. Live `@mlb TEAM`, `@box`, `@help`, game
  logs, top performers, pitcher summaries, and stat-heavy replies use clearer
  section labels and calmer routine stat-value emphasis.
- Verification: `pytest` passes with 48 tests; `ruff check .` passes;
  `python -m mlb_irc_bot --dry-run` passes.
- Deployment: not deployed yet; live IRC preview and deploy remain available
  follow-ups.

## Next Candidates

- Preview TASK-065 formatting in real `#mlbtest`, especially `@help`, `@mlb *`,
  `@mlb TEAM`, `@box TEAM`, one stat-heavy command, and any live alert that
  fires naturally.
- Deploy TASK-065 to the VPS after preview approval.
- Add a Docker Compose config check to CI or another environment where Docker is
  available.
