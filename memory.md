# Project Memory

## 2026-06-08 - TASK-064: Restore Live Announcement Scheduler

- Goal: troubleshoot and restore IRC announcements after `mlbotslop` stayed online but stopped posting live channel alerts.
- Starting point: local `main` is ahead of `origin/main` by four release-workflow commits; VPS checkout is on `56753e2` with the container up for 24 hours, commands answering in `#mlbtest`, and the alert store showing no new rows after `2026-06-07T01:11Z`.
- Live check: joined Libera `#mlbtest` as `AIAnnounceCheck`; `mlbotslop` was present and answered private `@mlb *` checks, but no channel announcements appeared during a 150-second wait while SF@CHC was live.
- Finding: a direct in-container scheduler probe found fresh unseen alerts for the active game and many final games, while the SQLite alert store had no rows newer than the prior deploy window. The IRC command loop was alive, so the background scheduler had likely died or stalled silently.
- Changes: supervised `LiveScheduler.run_forever()` so poll failures are logged and retried, kept per-game alert collection failures from stopping the whole poll, kept one failed IRC send from terminating remaining alert delivery, and baselined already-live/final games on first scheduler poll to avoid stale alert floods after a restart.
- Local verification: `.\.venv\Scripts\python -m pytest -q -o cache_dir=.tmp\task064-pytest-cache --basetemp=.tmp\task064-pytest-basetemp` passes with 47 tests; `.\.venv\Scripts\python -m ruff check .` passes; `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes.
- Deployment: pending.

## 2026-06-07 - TASK-063: Release Workflow Validation

- Goal: run the restored release-readiness workflow locally and document any deployment dry-run limitations or gaps.
- Starting point: `main` is ahead of `origin/main` by the two TASK-062 commits, backlog highest completed task is TASK-062, and the first next candidate is a full local release check plus deployment dry-run.
- Changes: documented the process-scoped PowerShell execution-policy bypass for deployment scripts, added the no-push/no-SSH deployment dry-run command, and updated the backlog with TASK-063 results and next candidates.
- Verification: Python 3.12.13 venv confirmed; `.\.venv\Scripts\python -m pytest -q -o cache_dir=.tmp\task063-pytest-cache --basetemp=.tmp\task063-pytest-basetemp` passes with 44 tests and known dependency deprecation warnings; `.\.venv\Scripts\python -m ruff check .` passes; `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes; `powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy.ps1 -DryRun -AllowDirty -SkipPush` prints the intended SSH deploy command without pushing or connecting.
- Gap: `docker compose config` could not run because `docker` is not installed on PATH.
- Commit: `59114069f24863ce2cea6863182144c6285edbe7`.

## 2026-06-07 - TASK-062: Release Workflow Cleanup

- Goal: restore the release-readiness task breadcrumbs expected by handoff prompts and remove local pytest scratch-directory noise from routine git checks.
- Starting point: prompt says TASK-061 is complete and backlog ends at TASK-061, but this checkout lacks `CLAUDE.md`, `AGENTS.md`, and `docs/tasks/backlog.md`; local `main` and `origin/main` are `56753e2`, and requested base `b3a52a2` is not present after fetch.
- Changes: added repo-facing agent instructions, recreated a lightweight task backlog with TASK-062 as the cleanup, updated checkpoint docs, and ignored `.tmp/`.
- Verification: `.\.venv\Scripts\python -m pytest -q -o cache_dir=.tmp\task062-pytest-cache --basetemp=.tmp\task062-pytest-basetemp` passes with 44 tests; `.\.venv\Scripts\python -m ruff check .` passes; `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes.
- Commit: `0f1eaff25960e0ddffee42594a85f661cbaa0257`.

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

## 2026-05-31 - Iteration 6: Pitcher Lines And Rich Player Stats

- Goal: add game pitching lines to `@mlbpitcher`/`@mlbpitchers`, improve `@sstats` formatting, and support recent stat windows such as `7 days`, `14 days`, and `30 days`.
- Decisions: pull pitcher game stats from live-feed boxscore player records; keep `@sstats` on MLB Stats API direct calls and request optional `seasonAdvanced`, `sabermetrics`, `expectedStatistics`, and date-range advanced payloads.
- API finding: live probes confirmed MLB Stats API exposes public sabermetric fields including WAR/wRC+/FIP and expected-stat fields including expected AVG/SLG/wOBA-style values; complete Baseball Savant/Statcast metrics may still need a separate source.
- Commands: `@sstats <player> [group] [season] [N days]` now maps day windows to `byDateRange`/`byDateRangeAdvanced`; existing season requests include basic, advanced, sabermetric, and expected sections when available.
- Verification: Python 3.12.13 `pytest` passes with 20 tests; `ruff check .` passes; live client smoke test returned formatted Ohtani hitting season/recent stats and Skubal pitching season stats.

## 2026-05-31 - Iteration 7: Pitcher-Aware Stat Defaults

- Goal: make `@sstats Skubal` and other primary pitchers default to pitching stats without requiring the `pitching` argument.
- Decisions: preserve whether a stat group was explicitly requested while parsing; after player resolution, infer the default group from MLB player search primary position, using pitching for `Pitcher`/`P`-style positions and hitting otherwise.
- Commands: `@sstats <pitcher>` now defaults to pitching, while explicit overrides such as `@sstats Tarik Skubal hitting` still work.
- Verification: Python 3.12.13 `pytest -o cache_dir=.tmp\pytest-cache` passes with 22 tests; `ruff check .` passes.

## 2026-05-31 - Iteration 8: IRC Self-Reply Guard

- Goal: fix a live IRC smoke-test bug where help replies beginning with bot commands could be parsed again by the bot.
- Finding: the bot responded to its own channel messages, causing queued, mismatched replies such as `@help mlb` leading to an accidental `@mlb [today|tomorrow|yesterday]` parse.
- Decision: ignore `PRIVMSG` lines from the current or configured bot nick before command routing.
- Verification: Python 3.12.13 `pytest -o cache_dir=.tmp\pytest-cache` passes with 23 tests; `ruff check .` passes.
- Live IRC smoke: after VPS deploy, a validated sweep in `#mlbtest` passed 23/23 command checks covering help, `@mlb`, `@mlb *`, team/date/game lookup, standings, wildcard, pitcher-default `@sstats`, leaders, pitcher lines, and lineups.
- Follow-ups noticed: all-league standings can truncate; `@help` top-level could advertise `@mlb *`; detailed game lookup could include game id and last play more consistently.

## 2026-05-31 - Iteration 9: Boxscores, Win Probability, Team Stats, Transactions

- Goal: add `@box`, enrich live `@mlb TEAM` with win probability and active pitchers, and add `@teamstats` plus `@transactions`.
- Decisions: use `/game/{gamePk}/contextMetrics` for current win probability, `/teams/{teamId}/stats` for team season/date-range stats, `/transactions` for league/team moves, and existing live feed boxscore/linescore data for compact R-H-E boxscore output.
- Commands: added `@box TEAM [today|yesterday]`, `@box game GAMEPK`, `@teamstats TEAM [hitting|pitching] [season] [N days]`, and `@transactions [TEAM] [today|yesterday|N days|YYYY-MM-DD]`.
- Formatting: live `@mlb TEAM` now appends `Win:` and `P:` sections before last play; win probability handles MLB percentage-point decimals such as `0.9` as `0.9%`, not `90%`.
- Verification: Python 3.12.13 `pytest -o cache_dir=.tmp\pytest-cache` passes with 29 tests; `ruff check .` passes; live client smoke covered enriched `@mlb TEAM`, `@box`, `@teamstats`, and `@transactions`.

## 2026-06-01 - Iteration 10: Styled IRC Responses

- Goal: improve IRC readability for all command replies and live alerts using standard bold, italic, and foreground color control codes.
- Decisions: add centralized IRC formatting helpers, keep styling always on, preserve stripped plaintext behavior for existing command contracts, and truncate by visible text while preserving complete control codes.
- Formatting: styled titles, teams, live/final states, section labels, ranks, stat labels, values, command help/errors, no-data messages, and alert prefixes.
- Docs: noted that live IRC replies are styled while documentation examples remain plaintext.
- Verification: Python 3.12.13 `pytest -q -o cache_dir=$env:TEMP\mlbot-pytest-cache --basetemp=$env:TEMP\mlbot-pytest-basetemp` passes with 33 tests; `ruff check .` passes.

## 2026-06-01 - Iteration 11: Calmer IRC Styling

- Goal: reduce visual noise after live review showed the first styled pass was too colorful.
- Decisions: keep bold/italic for teams, sections, labels, and values; reserve colors for titles, live/error/warning/final/no-data states, and alert prefixes.
- Verification: Python 3.12.13 `pytest -q -o cache_dir=$env:TEMP\mlbot-pytest-cache --basetemp=$env:TEMP\mlbot-pytest-basetemp` passes with 33 tests; `ruff check .` passes.

## 2026-06-06 - Iteration 12: Consolidated HR And Scoring Alerts

- Goal: prevent duplicate live alerts when a home run is also listed as a scoring play.
- Decisions: make scoring-play home runs emit the existing `home_run` alert shape and keep standalone home run detection only for home runs absent from `scoringPlays`.
- Tests: added regression coverage proving a home run scoring play emits only one HR alert while ordinary scoring plays still emit scoring alerts.
- Docs: noted that home run scoring plays are posted as HR alerts only.
- Verification: `python -m pytest tests\unit\test_alert_detectors.py -q` passes; `python -m ruff check src\mlb_irc_bot\alerts\detectors.py tests\unit\test_alert_detectors.py` passes. Full `python -m pytest` is blocked locally because this shell has Python 3.13 and the project's pinned HTTPX stack imports the removed `cgi` module.

## 2026-06-06 - Iteration 13: VPS Deploy Script

- Goal: capture the manual VPS deployment flow in a reusable script.
- Decisions: add `scripts/deploy.ps1` with defaults for `208.109.241.169`, `/home/wolfb/mlbot`, `main`, and the `mlb-irc-bot` Compose service; keep the script conservative by requiring clean local and remote checkouts.
- Deploy flow: push with the `aclonedsheep` GitHub CLI credential by default, SSH to the VPS, fast-forward the checkout, rebuild/restart Docker Compose, run app dry-run inside the container, and print container state.
- Docs: documented the one-command deployment and common options in `docs/DEVELOPMENT.md`.

## 2026-06-06 - Iteration 14: Expanded Stats, Game Context, And Alerts

- Goal: implement the approved API review list for new IRC commands and live alerts.
- API findings: `/game/{gamePk}/winProbability` exposes per-play win probability, swing, and leverage data; live feed and boxscore expose weather, replay challenge state, game info, and top performers; `/people/{id}/stats` supports `lastXGames`, `gameLog`, `statSplits`, `outsAboveAverage`, and `pitchArsenal`; `/teams/stats` and `/teams/{id}/leaders` support team rankings/leaders.
- Commands: added `@wp`, `@stars`, `@weather`, `@replay`, `@gamelog`, `@splits`, `@teamrank`, `@teamleaders`, `@defense`, and `@arsenal`; extended `@sstats` with `last N games`, `@teamstats` with situation splits, and `@leaders` with expanded/basic plus advanced leaderboard aliases.
- Alerts: added configurable win-probability swing, high-leverage, hard-hit, barrel/sweet-spot, late-threat, and game-info/weather alerts; final alerts now append a top performer when the live feed has one.
- Verification: Python 3.12.13 `pytest` passes with 41 tests using a repo-local temp dir; `ruff check .` passes; live API smoke for `@wp game`, `@stars game`, `@weather game`, and `@replay game` returned formatted replies for game 823697.

## 2026-06-06 - Iteration 15: Restore Pregame Announcements

- Goal: confirm and fix missing IRC announcements after the expanded alert update.
- Live check: inspected the VPS container to confirm it was running in `#mlbtest` on Libera, then joined as `AIBugWaiter9000` for four minutes; human channel traffic appeared, but no bot announcements did.
- Finding: game-info/weather detectors worked, but `LiveScheduler` skipped every scheduled non-live game, so near-start announcements were never collected. The scheduler also started on IRC welcome before the bot had confirmed its own channel join.
- Decisions: start alert scheduling only after the bot sees its own configured-channel `JOIN`; poll upcoming games only in the near-start window and throttle those detail checks by `MLB_NEAR_START_POLL_SECONDS`.
- Verification: `python -m pytest -q -o cache_dir=.tmp\pytest-cache --basetemp=.tmp\pytest-basetemp` passes with 44 tests; `python -m ruff check .` passes; `python -m mlb_irc_bot --dry-run` passes.
