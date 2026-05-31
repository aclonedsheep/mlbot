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

## 2026-05-31 - Iteration 3: Tests, Compatibility, And Probe

- Goal: add deterministic test coverage and finish project verification.
- Decisions: pin project runtime to Python 3.12 because `ircrobots` 0.7.2 pins AnyIO 2, requiring an older HTTPX/RESPX pair that is not Python 3.13 compatible.
- Added tests: command routing, team aliases, config overrides, alert detectors, SQLite alert dedupe, schedule hydration parsing, and game-detail fallback behavior.
- Added `mlb-api-probe` for opt-in live MLB API drift checks without making normal tests depend on the network.
- Verification: Python 3.12.13 `pytest` passes with 11 tests; `ruff check .` passes; `python -m mlb_irc_bot --dry-run` passes; `python -m mlb_irc_bot.probe --help` passes; `compileall src tests` passes.
- Verification gap: Docker Compose config was not run because Docker is not installed on this machine.

## 2026-05-31 - Iteration 4: Compact MLB Output And Game Detail Commands

- Goal: make `@mlb` compact, add live-only `@mlb *`, and add pitcher/lineup commands.
- Decisions: use `/api/v1.1/game/{gamePk}/feed/live` before the older v1 endpoint; keep team-specific `@mlb TEAM` detailed while making date schedule output single-message and compact.
- Commands: added `@mlbpitcher TEAM`, `@mlbpitchers TEAM`, and `@mlblineup TEAM`.
- Data parsing: added helpers for current pitcher, game pitcher lists, and posted lineups from live feed boxscore/linescore data.
- Follow-up: made `@wildcard`, `@wildcard AL`, and `@wildcard NL` label replies as wildcard standings and added coverage for default all-league wildcard output.
- Verification: Python 3.12.13 `pytest` passes with 18 tests; `ruff check .` passes.

## 2026-05-31 - Iteration 5: Single-Message IRC Command Replies

- Goal: fix confusing delayed/interleaved IRC replies where `@wildcard` sent a title first and later lines appeared after unrelated commands.
- Reproduction: joined `#mlbtest` from the VPS as a temporary IRC client and confirmed `@wildcard` emitted `Wildcard`, then AL/NL lines were delayed into later command windows.
- Decisions: keep command replies to one IRC message for standings, wildcard, game detail, pitcher lists, and schedule output to avoid server/client throttling interleaving.
- Verification: Python 3.12.13 `pytest` passes with 17 tests; `ruff check .` passes.
