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
- Deployment: pushed and deployed `6251942` to the VPS. The deploy script
  fast-forwarded `/home/wolfb/mlbot`, rebuilt/recreated `mlb-irc-bot`, and the
  in-container dry-run passed for `mlbotslop` on Libera `#mlbtest`. A
  post-deploy probe showed the container running with `restarts=0` and the
  remote checkout clean at `62519428bdbab99d240b326ac10af809a7db31bc`.

### TASK-066 - Preview Deployed Formatting

- Status: Done.
- Goal: preview the deployed TASK-065 formatting in real `#mlbtest` before
  making additional style changes.
- Result: joined Libera `#mlbtest` as `AIFormatCheck606` and ran `@help`,
  `@mlb *`, `@mlb NYY`, `@box NYY`, and `@sstats Ohtani hitting`. `mlbotslop`
  returned one readable response for each command; the raw IRC controls showed
  high-signal color on titles/states, calmer bold/italic emphasis for routine
  command and stat labels, and balanced resets.
- Verification: `pytest` passes with 48 tests; `ruff check .` passes;
  `python -m mlb_irc_bot --dry-run` passes.
- Gap: no live games were active during the sweep, so no naturally firing alert
  could be visually judged.

### TASK-067 - Bound Leaders Output

- Status: Done.
- Goal: keep `@leaders` output readable and prevent high requested limits from
  producing spammy API calls or overlong IRC replies.
- Result: `@leaders` keeps its limit capped at 10, the command docs now call
  out leaderboard caps, and long league-leader replies fit whole entries with a
  concise `+N more` suffix instead of blind truncation.
- Verification: `pytest` passes with 50 tests; `ruff check .` passes;
  `python -m mlb_irc_bot --dry-run` passes.

### TASK-068 - Preview Highlights Splits And Scoring Alerts

- Status: Done.
- Goal: implement the approved feature batch for compact game previews,
  highlight links, expanded split aliases, and scoring-state alerts.
- Result: added `@preview` and `@matchup` for compact game previews with
  probables, weather, lineup status, and team form when available; added
  `@highlights TEAM` and `@highlights game GAMEPK` backed by game-content
  highlight metadata; expanded player/team split aliases such as day/night,
  grass/turf, score state, starter/reliever, league-opponent, and batting-order
  splits; added tied-game, go-ahead/lead-change, and walk-off alerts behind
  `MLB_ENABLE_ALERT_LEAD_CHANGES`.
- Verification: `pytest` passes with 54 tests; `ruff check .` passes;
  `python -m mlb_irc_bot --dry-run` passes.

### TASK-069 - Complete Help Coverage And Deploy

- Status: Done.
- Goal: make `@help` cover every command and subcommand/alias, then deploy the
  current branch to the VPS.
- Result: added command-specific help for `@preview`/`@matchup`,
  `@highlights`, `@wp`, `@stars`, `@weather`, `@replay`, pitcher and lineup
  commands, standings and wildcard, player/team stats, defense/arsenal,
  transactions, and `@help`; documented `@preview game GAMEPK` in the command
  docs and README.
- Verification: `pytest` passes with 55 tests; `ruff check .` passes;
  `python -m mlb_irc_bot --dry-run` passes.
- Deployment: pushed and deployed `a7350e8` to the VPS. The deploy script
  fast-forwarded `/home/wolfb/mlbot`, rebuilt/recreated `mlb-irc-bot`, and the
  in-container dry-run passed for `slopstats` on Libera `#mlbtest`. A
  post-deploy probe showed the remote checkout clean at
  `a7350e895fd0ff93ea27954a95cab7d74c39b21f` with the Compose service up.
- Live check: joined Libera `#mlbtest` as `AIHelpCheck543` and confirmed
  `slopstats` answered `@help`, `@help preview`, `@help highlights`,
  `@help wildcard`, and `@help help` with the updated deployed help text.

### TASK-070 - Resolve Highlight Links To MP4

- Status: Done.
- Goal: make `@highlights` share direct MLB MP4 playback links instead of
  public MLB video page links when direct media is available.
- Result: highlight parsing now prefers direct MP4 playback URLs from
  `/api/v1/game/{gamePk}/content`, keeps the MLB video page URL separately, and
  falls back through public video-page `og:video` metadata for slug-only items.
  `@highlights` now prints resolved MP4 URLs in IRC when available, using one
  line per returned highlight so long media URLs do not hide links behind an
  omitted-count suffix.
- Verification: focused highlight parser/command tests pass; `pytest` passes
  with 55 tests; `ruff check .` passes; `python -m mlb_irc_bot --dry-run`
  passes; `git diff --check` passes. A live client probe for game `822807`
  resolved the Brandon Valenzuela sample highlight to
  `https://mlb-cuts-diamond.mlb.com/FORGE/2026/2026-06/07/5ede2bd0-63d98c4c-69ac4da6-csvm-diamondgcp-asset_1280x720_59_4000K.mp4`.
- Deployment: pushed and deployed `5a8f78a` to the VPS. The deploy script
  fast-forwarded `/home/wolfb/mlbot`, rebuilt/recreated `mlb-irc-bot`, and the
  in-container dry-run passed for `slopstats` on Libera `#mlbtest`. A
  post-deploy probe showed the remote checkout clean at
  `5a8f78ad5aa362206cb11754226f2173ae777671` with the Compose service up.
- Live check: joined Libera `#mlbtest` as `AIHighlight656` and confirmed
  `@highlights game 822807` returned three separate IRC replies, each with a
  direct `.mp4` URL, including the Brandon Valenzuela sample URL.

## Current

### TASK-071 - Highlight Filters And More Paging

- Status: Done.
- Goal: add `@more` as a follow-up command for paged highlight results and add
  useful highlight filters such as condensed games, scoring plays, homers,
  defense, pitching, recaps, interviews, and data clips.
- Result: highlights now carry parsed content tags from MLB metadata and
  title/description text; `@highlights` accepts a filter before or after the
  game/team selector; `@highlights filters` lists the available filters; and
  `@more` emits the next page from the previous highlights result.
- Verification: focused command/client tests pass; `pytest` passes with 58
  tests; `ruff check .` passes; `python -m mlb_irc_bot --dry-run` passes; `git
  diff --check` passes. A live client probe for game `822807` classified 40
  highlight items across condensed, scoring, homers, defense, pitching, recap,
  interviews, data clips, and uncategorized highlights.
- Deployment: pushed and deployed `d6956ee` to the VPS. The deploy script
  fast-forwarded `/home/wolfb/mlbot`, rebuilt/recreated `mlb-irc-bot`, and the
  in-container dry-run passed for `slopstats` on Libera `#mlbtest`. A
  post-deploy probe showed the remote checkout clean at
  `d6956eefda17a1f54998ba9f9f04392971b8ac25` with the Compose service up.
- Live check: joined Libera `#mlbtest` as `AIMore200` and confirmed
  `@highlights filters`, `@highlights scoring game 822807`, and `@more` worked
  in-channel. The scoring filter returned MP4 links numbered `1/19` through
  `3/19`, then `@more` returned the next MP4 page starting at `4/19`.

### TASK-072 - Fix Bases-Loaded Current Batter

- Status: Done.
- Goal: fix bases-loaded alerts showing the latest baserunner as the hitter
  coming up when MLB's live linescore/current-play payload has not advanced
  past the plate appearance that just loaded the bases.
- Live inspection: MLB live feed game `824829` (SEA @ BAL) showed Gunnar
  Henderson walking in the bottom of the 3rd to load the bases; Gunnar was then
  listed as a runner, and the next batter was Pete Alonso.
- Result: current-batter selection now rejects any candidate who is already
  listed on first, second, or third. If the stale linescore batter is a listed
  runner, bases-loaded context falls forward to the `onDeck` hitter instead of
  announcing the runner as "up."
- Verification: focused alert detector tests pass; `pytest` passes with 59
  tests; `ruff check .` passes; `python -m mlb_irc_bot --dry-run` passes.
- Deployment: pushed and deployed `d70e56b` to the VPS. The deploy script
  fast-forwarded `/home/wolfb/mlbot`, rebuilt/recreated `mlb-irc-bot`, and the
  in-container dry-run passed for `slopstats` on Libera `#mlbtest`. A
  post-deploy probe showed the remote checkout clean at
  `d70e56b4bd3aec25d9424bc0c2a45271e2f26149` with the container running,
  `restarts=0`.
- Live check gap: an immediate MLB live-feed sweep found no live games with
  bases loaded, so there was no natural alert replay available after deploy.

### TASK-073 - Consolidate Overlapping Play Alerts

- Status: Done.
- Goal: send one IRC message for an MLB play when multiple enabled detectors
  identify the same event, while preserving compact secondary facts such as
  win-probability swing, leverage, and batted-ball quality.
- Result: play-derived alerts now carry a shared game/at-bat group key,
  headline priority, and optional detail text. The scheduler filters disabled,
  suppressed, and already-seen alerts first, then consolidates remaining
  same-play alerts into one natural headline with stable secondary details.
  Sent batches record the play sentinel plus each component alert key so later
  polls do not re-announce delayed duplicates for the same play.
- Verification: focused alert and scheduler regressions pass; `pytest` passes
  with 62 tests; `ruff check .` passes; `python -m mlb_irc_bot --dry-run`
  passes; `git diff --check` passes.
- Deployment: pushed and deployed `325142f` to the VPS. The deploy script
  fast-forwarded `/home/wolfb/mlbot`, rebuilt/recreated `mlb-irc-bot`, and the
  in-container dry-run passed for `slopstats` on Libera `#mlbtest`. A
  post-deploy probe showed the remote checkout clean at
  `325142f50ce54521c1418cac42061ad7671065be`, with the container running and
  `restarts=0`.
- Live check gap: immediate post-deploy logs showed only expected first-poll
  suppression of existing alerts, so there was no natural overlapping-play
  channel replay to judge in `#mlbtest`.

### TASK-074 - Include Hitters In Barrel Alerts

- Status: Done.
- Goal: fix barrel and hard-hit alerts that can omit the hitter's name when MLB
  sends generic batted-ball result text.
- Result: batted-ball alerts now derive their visible subject from
  `matchup.batter` plus the MLB result text, preserving descriptions that
  already include the hitter while prefixing generic text such as `Double`.
  Consolidated barrel/hard-hit details also include the hitter when available,
  and a barrel primary no longer appends a redundant hard-hit detail for the
  same batted ball.
- Verification: focused alert and scheduler regressions pass; `pytest` passes
  with 63 tests; `ruff check .` passes; `python -m mlb_irc_bot --dry-run`
  passes; `git diff --check` passes.
- Deployment: pushed and deployed `101b79b` to the VPS. The deploy script
  fast-forwarded `/home/wolfb/mlbot`, rebuilt/recreated `mlb-irc-bot`, and the
  in-container dry-run passed for `slopstats` on Libera `#mlbtest`. A
  post-deploy probe showed the remote checkout clean at
  `101b79bcba88ef6f44fc38938f1da1349d1e2bca`, with the container running and
  `restarts=0`.
- Live check gap: immediate post-deploy logs had no fresh barrel alert to judge
  in `#mlbtest`.

### TASK-075 - Raise Barrel Alert EV Threshold

- Status: Local checks pass; deployment pending.
- Goal: make barrel alerts fire only for special hard-hit balls instead of
  routine 95+ mph sweet-spot contact.
- Result: barrel detection now requires the configured hard-hit exit-velocity
  threshold, `MLB_ALERT_HARD_HIT_THRESHOLD_MPH`, in addition to the launch-angle
  window. With the default threshold, a barrel alert only fires at 110+ mph and
  8-32 degrees, and custom hard-hit thresholds also control barrel eligibility.
- Verification: focused alert and scheduler regressions pass; `pytest` passes
  with 65 tests; `ruff check .` passes; `python -m mlb_irc_bot --dry-run`
  passes; `git diff --check` passes.
- Deployment: pending after the implementation commit.

## Next Candidates

- Watch a naturally firing barrel or overlapping-play alert in `#mlbtest` and
  make only narrow formatting tweaks if the consolidated suffix feels noisy
  in-channel.
- Run a live `@preview`, `@highlights`, and expanded-split command sweep after
  deployment to judge IRC readability and confirm `@highlights` returns MP4
  URLs in-channel.
- Consider whether `@teamleaders` should also get omitted-count formatting if a
  future category returns unusually long player names.
- Add a Docker Compose config check to CI or another environment where Docker is
  available.
