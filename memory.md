# Project Memory

## 2026-05-31 - Iteration 1: Initial Scaffold

- Goal: implement a Dockerized Python async IRC bot for a single MLB channel.
- Decisions: use direct MLB Stats API calls, `ircrobots`, `httpx`, `pydantic-settings`, `aiosqlite`, SQLite state, and command prefix `@`.
- Scope locked: no per-team alert toggles; alerts are channel-wide and controlled by env/config.
- Git: created branch `codex/mlb-irc-bot` from the unborn repository.
- Files: adding project scaffold, package layout, Docker config, docs, and test directories.
- Verification: pending after scaffold commit.

## 2026-05-31 - Iteration 2: Core Bot Implementation

- Goal: implement the command, MLB API, alert, scheduler, storage, and IRC service layers.
- Decisions: keep command handlers independent from IRC transport; use direct `/api/v1` MLB endpoints with schedule hydration centralized in `mlb/hydrate.py`; persist alert dedupe in SQLite.
- Commands: implemented `@mlb`, `@standings`, `@wildcard`, `@sstats`, `@leaders`, and `@help`.
- Alerts: implemented pure detectors for home runs, scoring plays, bases-loaded situations, finals, no-hit bids, cycle watch/completion, and immaculate innings.
- Files: added core modules under `src/mlb_irc_bot/`.
- Verification: `python -m compileall src` passes.
