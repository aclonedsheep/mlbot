# Project Memory

## 2026-06-11 - TASK-078: Retry HR Park Details

- Goal: fix live home run alerts missing `HR parks` because Baseball Savant's
  park-count data can lag the MLB live feed during active games.
- Starting point: local `main` is clean and ahead of `origin/main` by the
  TASK-077 deployment-record commit `9e33efd`; deployed app code is
  `c98ef06f7a27c5492edc4e6ae89675326b5b3062`. The remote alert store showed
  recent home run messages for game `823371`, including Rafael Flores Jr.,
  with EV/LA/distance but no park count.
- Findings: replaying game `823371` locally reproduced the missing park data;
  MLB live feed exposes batted-ball play ids immediately, but the Savant
  `/leaderboard/home-runs?cat=xhr` rows and per-play video pages were not yet
  populated for the active-game HRs.
- Planned changes: add a deferred `HR parks` follow-up alert that retries
  Savant enrichment on later polls, only sends after the original HR alert was
  recorded, and skips itself if the original message already included the park
  count.
- Changes: added a standalone `home_run_parks` alert generated when Savant park
  data becomes available after the original HR. The scheduler now supports
  alerts gated on a previously recorded alert key, checks the original message
  so HRs that already included `HR parks` do not get a duplicate follow-up, and
  ties the follow-up to the existing home-run alert toggle.
- Verification: focused scheduler/storage/detector regressions pass;
  `.\.venv\Scripts\python -m pytest -q -o cache_dir=.tmp\pytest-cache
  --basetemp=.tmp\pytest-basetemp` passes with 69 tests and known dependency
  deprecation warnings; `.\.venv\Scripts\python -m ruff check .` passes;
  `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes; `git diff --check`
  passes with only expected Windows line-ending warnings.
- Commit: `4e077b00e03d125641873d222d2ad6594d48c940`
  (`[TASK-078] Retry HR park details`).
- Deployment: pushed and deployed `4e077b0` to the VPS with
  `powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy.ps1`; the
  deploy fast-forwarded `/home/wolfb/mlbot` from `c98ef06` to `4e077b0`,
  rebuilt/recreated the Compose service, and the in-container dry-run passed
  for `slopstats` on Libera `#mlbtest`.
- Post-deploy check: remote checkout was clean at
  `4e077b00e03d125641873d222d2ad6594d48c940`; `docker compose ps` showed
  `mlbot-mlb-irc-bot-1` up; `docker inspect` reported `status=running
  running=true restarts=0 started=2026-06-12T00:28:49.958071314Z`.
- Live check gap: Savant still had not provided a live park-count row for the
  Rafael Flores Jr. homer during investigation, so the new path is deployed and
  waiting on normal polling to send a follow-up only after Savant catches up.
- Resume prompt: Continue after TASK-078; live HR alerts now stay immediate and
  a delayed `HR parks: Player 80% (24/30)` follow-up is queued by normal
  polling once Savant catches up. The implementation is committed at
  `4e077b0`, deployed on the VPS, and remote dry-run/container checks pass.
  Next useful step is to watch `#mlbtest` for either a natural deferred HR park
  follow-up or the next HR whose Savant data is ready in time for the first
  alert.

## 2026-06-11 - TASK-077: Show HR Park Percentage

- Goal: make home run alerts show what percentage of MLB parks the batted ball
  would have been a homer in, instead of only showing the other-park count.
- Starting point: local `main` is clean and ahead of `origin/main` by the
  TASK-076 deployment-record commit `48bd77b`; deployed app code is documented
  at `08b24127f9f6bd4d3aca8bfac7a67c32886c2f9e`.
- Planned changes: relabel the existing Baseball Savant park-count detail as a
  total MLB park percentage plus raw count, keep the alert compact, update
  detector/docs tests, run local checks, and update the backlog/memory before
  committing.
- Changes: home run details now render the Baseball Savant park count as a
  compact total-park percentage and raw count, for example
  `HR parks 80% (24/30)`. The formatter prefers the total `parks`/`ct` count
  and falls back from `otherParks` by adding the actual home-run park back into
  the 30-park denominator.
- Verification: focused alert detector regressions pass;
  `.\.venv\Scripts\python -m pytest -q -o cache_dir=.tmp\pytest-cache
  --basetemp=.tmp\pytest-basetemp` passes with 67 tests and known dependency
  deprecation warnings; `.\.venv\Scripts\python -m ruff check .` passes;
  `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes; `git diff --check`
  passes with only expected Windows line-ending warnings.
- Commit: `c98ef06f7a27c5492edc4e6ae89675326b5b3062`
  (`[TASK-077] Show HR park percentage`).
- Deployment: pushed and deployed `c98ef06` to the VPS with
  `powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy.ps1`; the
  deploy fast-forwarded `/home/wolfb/mlbot` from `08b2412` to `c98ef06`,
  rebuilt/recreated the Compose service, and the in-container dry-run passed
  for `slopstats` on Libera `#mlbtest`.
- Post-deploy check: remote checkout was clean at
  `c98ef06f7a27c5492edc4e6ae89675326b5b3062`; `docker compose ps` showed
  `mlbot-mlb-irc-bot-1` up; `docker inspect` reported `status=running
  running=true restarts=0 started=2026-06-12T00:10:31.567741881Z`.
- Live check gap: no natural home run alert replay was captured during the
  deploy window, so the exact live IRC line still needs a natural `#mlbtest`
  watch if the label feels worth judging in-channel.
- Resume prompt: Continue after TASK-077; HR alerts now label Savant park reach
  as `HR parks 80% (24/30)`-style percentage/count text. The implementation is
  committed at `c98ef06`, deployed on the VPS, and remote dry-run/container
  checks pass. Next useful step is to watch a naturally firing home run alert
  in `#mlbtest` and tweak only if the `HR parks` label feels unclear.

## 2026-06-11 - TASK-076: Add High-Leverage Situation Context

- Goal: make high-leverage alerts explain why the plate appearance is high
  leverage by adding compact game situation context such as base state, outs,
  and tying/go-ahead run status.
- Starting point: local `main` is clean and ahead of `origin/main` by the
  TASK-075 deployment-record commit `4cc9d57`; deployed app code is documented
  at `f5a2d1be930d58f8655611315641b1373236655e`.
- Planned changes: derive high-leverage situation text from win-probability
  play fields, include it in primary high-leverage alerts and consolidated LI
  secondary details, add regression coverage for primary/consolidated output,
  run local checks, update backlog/memory, commit, deploy, and verify the
  container.
- Changes: high-leverage alerts now append compact situation context when MLB
  exposes it, using the pre-at-bat score from the play log when available plus
  base occupancy, tying/go-ahead run status, and outs. Consolidated same-play
  messages now carry the same context in the LI secondary detail.
- Verification: focused alert/scheduler tests pass; `.\.venv\Scripts\python -m
  pytest -q -o cache_dir=.tmp\pytest-cache --basetemp=.tmp\pytest-basetemp`
  passes with 66 tests and known dependency deprecation warnings;
  `.\.venv\Scripts\python -m ruff check .` passes; `.\.venv\Scripts\python -m
  mlb_irc_bot --dry-run` passes.
- Commit: `08b24127f9f6bd4d3aca8bfac7a67c32886c2f9e`
  (`[TASK-076] Add high leverage situation context`).
- Deployment: pushed and deployed `08b2412` to the VPS with
  `powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy.ps1`; the
  deploy fast-forwarded `/home/wolfb/mlbot` from `f5a2d1b` to `08b2412`,
  rebuilt/recreated the Compose service, and the in-container dry-run passed
  for `slopstats` on Libera `#mlbtest`.
- Post-deploy check: remote checkout was clean at
  `08b24127f9f6bd4d3aca8bfac7a67c32886c2f9e`; `docker inspect` reported
  `status=running running=true restarts=0
  started=2026-06-11T18:59:47.003528094Z`; `docker compose ps` showed
  `mlbot-mlb-irc-bot-1` up.
- Live check gap: immediate post-deploy logs showed only expected first-poll
  suppression for existing game alerts, and an extra 90-second log window
  produced no fresh natural high-leverage alert to judge in `#mlbtest`.
- Resume prompt: Continue after TASK-076; high-leverage alerts now explain the
  tense situation with compact score/base/outs context when MLB exposes it,
  implementation commit `08b2412` is deployed, and the local deployment-record
  commit is the latest handoff checkpoint.

## 2026-06-11 - TASK-075: Raise Barrel Alert EV Threshold

- Goal: make barrel alerts fire only for special hard-hit balls by requiring
  the configured hard-hit exit-velocity threshold in addition to the launch
  angle window.
- Starting point: local `main` is clean and ahead of `origin/main` by the
  TASK-074 deployment-record commit `74cf518`; deployed app code is documented
  at `101b79bcba88ef6f44fc38938f1da1349d1e2bca`.
- Planned changes: change barrel detection to require
  `MLB_ALERT_HARD_HIT_THRESHOLD_MPH` instead of the old fixed 95 mph floor, add
  regressions for below-threshold sweet-spot contact and configurable threshold
  behavior, run local checks, update backlog/memory, commit, deploy, and verify
  the container.
- Changes: barrel detection now requires the configured hard-hit EV threshold
  in addition to the 8-32 degree launch-angle window. With the default 110 mph
  threshold, 95-109 mph sweet-spot contact no longer triggers barrel or
  hard-hit alerts; raising `MLB_ALERT_HARD_HIT_THRESHOLD_MPH` also raises the
  barrel EV floor.
- Verification: focused alert/scheduler tests pass; `.\.venv\Scripts\python -m
  pytest -q -o cache_dir=.tmp\pytest-cache --basetemp=.tmp\pytest-basetemp`
  passes with 65 tests and known dependency deprecation warnings;
  `.\.venv\Scripts\python -m ruff check .` passes; `.\.venv\Scripts\python -m
  mlb_irc_bot --dry-run` passes; `git diff --check` passes with only expected
  Windows line-ending warnings.
- Commit: `f5a2d1be930d58f8655611315641b1373236655e`
  (`[TASK-075] Raise barrel alert EV threshold`).
- Deployment: pushed and deployed `f5a2d1b` to the VPS with
  `powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy.ps1`; the
  deploy fast-forwarded `/home/wolfb/mlbot` from `101b79b` to `f5a2d1b`,
  rebuilt/recreated the Compose service, and the in-container dry-run passed
  for `slopstats` on Libera `#mlbtest`.
- Post-deploy check: remote checkout was clean at
  `f5a2d1be930d58f8655611315641b1373236655e`; `docker inspect` reported
  `status=running running=true restarts=0
  started=2026-06-11T17:59:45.3511781Z`; `docker compose ps` showed
  `mlbot-mlb-irc-bot-1` up.
- Live check gap: immediate post-deploy logs showed only expected first-poll
  suppression for existing game alerts, with no fresh natural barrel alert to
  judge in `#mlbtest`.
- Resume prompt: Continue after TASK-075; barrel alerts now require the
  configured hard-hit EV threshold plus the 8-32 degree launch-angle window,
  implementation commit `f5a2d1b` is deployed, and the local deployment-record
  commit is the latest handoff checkpoint.

## 2026-06-11 - TASK-074: Include Hitters In Barrel Alerts

- Goal: fix barrel and hard-hit alerts that can omit the hitter's name when MLB
  sends generic result text for a batted-ball play.
- Starting point: local `main` is clean and ahead of `origin/main` by the
  TASK-073 deployment-record commit `e4aa401`; deployed app code is documented
  at `325142f50ce54521c1418cac42061ad7671065be`.
- Planned changes: derive a batted-ball alert subject from `matchup.batter`
  plus result text, preserve existing descriptions that already name the
  hitter, add regression coverage for generic barrel text, run local checks,
  update backlog/memory, commit, deploy, and verify the container.
- Changes: batted-ball alert text now prefixes generic MLB result text with the
  batter from `matchup.batter`, while leaving descriptions that already include
  the hitter unchanged. Consolidated barrel/hard-hit detail text now includes
  the hitter when available, and barrel-primary batches suppress redundant
  hard-hit detail for the same batted ball.
- Verification: focused alert/scheduler tests pass; `.\.venv\Scripts\python -m
  pytest -q -o cache_dir=.tmp\pytest-cache --basetemp=.tmp\pytest-basetemp`
  passes with 63 tests and known dependency deprecation warnings;
  `.\.venv\Scripts\python -m ruff check .` passes; `.\.venv\Scripts\python -m
  mlb_irc_bot --dry-run` passes; `git diff --check` passes with only expected
  Windows line-ending warnings.
- Commit: `101b79bcba88ef6f44fc38938f1da1349d1e2bca`.
- Deployment: pushed and deployed `101b79b` to the VPS with
  `powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy.ps1`; the
  remote checkout fast-forwarded to `101b79bcba88ef6f44fc38938f1da1349d1e2bca`,
  the `mlb-irc-bot` Compose service rebuilt/recreated successfully, and the
  in-container dry-run passed for `slopstats` on Libera `#mlbtest`.
- Post-deploy check: remote `git status --short --branch` was clean at
  `101b79b`; `docker compose ps` showed `mlbot-mlb-irc-bot-1` up; `docker
  inspect` showed `status=running`, `running=true`, `restarts=0`, and
  `started=2026-06-11T17:38:45.495111566Z`.
- Live check gap: immediate post-deploy logs had no fresh barrel alert to judge
  in `#mlbtest`.
- Resume prompt: Continue after TASK-074; barrel and hard-hit alerts now include
  the hitter from `matchup.batter` when MLB result text is generic, barrel
  secondary details include the hitter, and barrel-primary batches suppress
  redundant hard-hit details. The fix is committed at
  `101b79bcba88ef6f44fc38938f1da1349d1e2bca`, deployed on the VPS, and remote
  dry-run/container checks pass. Next useful step is to watch a naturally
  firing barrel alert in `#mlbtest` and tweak only if the live phrasing still
  feels off.

## 2026-06-10 - TASK-073: Consolidate Overlapping Play Alerts

- Goal: consolidate multiple alert classes for the same MLB play into one IRC
  message that keeps a natural headline and compact secondary facts such as
  win-probability swing, leverage, and batted-ball quality.
- Starting point: local `main` is clean and ahead of `origin/main` by the
  TASK-072 deployment-record commit `835d637`; deployed app code is documented
  at `d70e56b4bd3aec25d9424bc0c2a45271e2f26149`.
- Planned changes: add merge metadata to the internal alert model, group
  play-derived alerts by game and at-bat after enabled/seen/suppression checks,
  choose one headline by alert priority, append stable secondary details, mark
  both component keys and the group sentinel as sent, and leave state alerts
  such as bases-loaded and late-threat standalone.
- Changes: `Alert` now carries optional group/detail metadata and alert batches
  consolidate by game/at-bat. Play-derived alerts share those keys and provide
  priority/detail hints; the scheduler filters disabled, suppressed, and seen
  alerts before consolidation, sends one batch message, and marks the play
  sentinel plus component keys as sent.
- Verification: focused alert/scheduler tests pass; `.\.venv\Scripts\python -m
  pytest -q -o cache_dir=.tmp\pytest-cache --basetemp=.tmp\pytest-basetemp`
  passes with 62 tests and known dependency deprecation warnings;
  `.\.venv\Scripts\python -m ruff check .` passes; `.\.venv\Scripts\python -m
  mlb_irc_bot --dry-run` passes; `git diff --check` passes with only expected
  Windows line-ending warnings.
- Commit: `325142f50ce54521c1418cac42061ad7671065be`.
- Deployment: pushed and deployed `325142f` to the VPS with
  `powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy.ps1`; the
  remote checkout fast-forwarded to `325142f50ce54521c1418cac42061ad7671065be`,
  the `mlb-irc-bot` Compose service rebuilt/recreated successfully, and the
  in-container dry-run passed for `slopstats` on Libera `#mlbtest`.
- Post-deploy check: remote `git status --short --branch` was clean at
  `325142f`; `docker compose ps` showed `mlbot-mlb-irc-bot-1` up; `docker
  inspect` showed `status=running`, `running=true`, `restarts=0`, and
  `started=2026-06-10T20:35:05.140876316Z`.
- Live check gap: immediate post-deploy logs showed first-poll suppression of
  existing alerts for several games but no fresh natural overlapping-play alert
  to judge in `#mlbtest`.
- Resume prompt: Continue after TASK-073; overlapping play-derived alerts now
  consolidate into one IRC message with a priority headline and compact
  secondary facts, are committed at
  `325142f50ce54521c1418cac42061ad7671065be`, deployed on the VPS, and remote
  dry-run/container checks pass. Next useful step is to watch a naturally
  firing overlapping-play alert in `#mlbtest` and tweak only if the combined
  suffix feels noisy.

## 2026-06-08 - TASK-072: Fix Bases-Loaded Current Batter

- Goal: fix bases-loaded alerts showing the wrong player as "up" when MLB's
  live linescore offense payload names the last runner to reach base instead of
  the current plate-appearance batter.
- Starting point: local `main` is clean and ahead of `origin/main` by the
  TASK-071 handoff-only deployment record commit; TASK-071 app code is deployed
  at `d6956eefda17a1f54998ba9f9f04392971b8ac25`.
- Live inspection: MLB live feed game `824829` (SEA @ BAL) showed Gunnar
  Henderson walking in the bottom of the 3rd to load the bases; he was then a
  listed runner, and the next batter was Pete Alonso.
- Changes: bases-loaded and late-threat current-batter selection now ignores a
  linescore/current-play batter who is already listed on first, second, or
  third; when that stale batter is the latest baserunner, the detector uses the
  linescore `onDeck` hitter as the player coming up instead of repeating the
  runner's name.
- Verification: focused alert detector tests pass; full
  `.\.venv\Scripts\python -m pytest -q -o
  cache_dir=.tmp\task072-pytest-cache
  --basetemp=.tmp\task072-pytest-basetemp` passes with 59 tests and known
  dependency deprecation warnings; `.\.venv\Scripts\python -m ruff check .`
  passes; `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes.
- Commit: `d70e56b4bd3aec25d9424bc0c2a45271e2f26149`.
- Deployment: pushed and deployed `d70e56b` to the VPS with
  `powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy.ps1`; the
  remote checkout fast-forwarded to `d70e56b4bd3aec25d9424bc0c2a45271e2f26149`,
  the `mlb-irc-bot` Compose service rebuilt/recreated successfully, and the
  in-container dry-run passed for `slopstats` on Libera `#mlbtest`.
- Post-deploy check: remote `git status --short --branch` was clean at
  `d70e56b`; `docker inspect` showed `status=running`, `running=true`,
  `restarts=0`, and `started=2026-06-08T23:34:28.861832182Z`.
- Live check gap: an immediate MLB live-feed sweep found no live games with
  bases loaded, so there was no honest natural alert replay available after
  deploy.
- Resume prompt: Continue after TASK-072; bases-loaded alerts now avoid naming
  a listed baserunner as the current batter and fall forward to the on-deck
  hitter when MLB has not advanced the plate-appearance payload. The fix is
  committed at `d70e56b4bd3aec25d9424bc0c2a45271e2f26149`, deployed on the VPS,
  and remote dry-run/container checks pass. Next useful step is to watch a
  naturally firing bases-loaded or late-threat alert in `#mlbtest` when one
  occurs, or continue with the compact command sweep from the backlog.

## 2026-06-08 - TASK-071: Highlight Filters And More Paging

- Goal: add `@more` as a follow-up command for paged highlight results and add
  highlight filters for useful content types such as condensed games, scoring
  plays, homers, defense, pitching, recaps, interviews, and data clips.
- Starting point: local `main` is clean and ahead of `origin/main` by the
  TASK-070 handoff-only deployment record commit; deployed app code is at
  `5a8f78ad5aa362206cb11754226f2173ae777671`.
- Planned changes: classify highlights from MLB content metadata and text,
  teach `@highlights` to accept a filter token before or after the game/team
  selector, store the remaining result cursor in the router, add `@more` to
  emit subsequent highlight pages, update help/docs/tests, run local checks,
  and commit.
- Changes: highlights now carry parsed content tags from MLB keywords,
  title/description text, and slugs; filters include condensed games, scoring
  plays, homers, defense, pitching, recaps, interviews, and data clips;
  `@highlights` accepts a filter before or after the game/team selector;
  `@highlights filters` lists available filters; `@more` emits the next page
  from the previous highlights result using an in-router cursor.
- Verification: focused command/client tests pass; `.\.venv\Scripts\python -m
  pytest -q -o cache_dir=.tmp\task071-pytest-cache
  --basetemp=.tmp\task071-pytest-basetemp` passes with 58 tests and known
  dependency deprecation warnings; `.\.venv\Scripts\python -m ruff check .`
  passes; `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes; `git diff
  --check` passes. A live client probe for game `822807` classified 40
  highlights: condensed=1, scoring=19, homers=14, defense=2, pitching=7,
  recap=1, interviews=2, data=17, and uncategorized highlights=4.
- Commit: `d6956eefda17a1f54998ba9f9f04392971b8ac25`.
- Deployment: pushed and deployed `d6956ee` to the VPS with
  `powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy.ps1`; the
  remote checkout fast-forwarded to `d6956eefda17a1f54998ba9f9f04392971b8ac25`,
  the `mlb-irc-bot` Compose service rebuilt/recreated successfully, and the
  in-container dry-run passed for `slopstats` on Libera `#mlbtest`.
- Live check: joined Libera `#mlbtest` as `AIMore200` and confirmed
  `@highlights filters`, `@highlights scoring game 822807`, and `@more` worked
  in-channel. The scoring filter returned MP4 links numbered `1/19` through
  `3/19`, then `@more` returned the next MP4 page starting at `4/19`.
- Resume prompt: Continue after TASK-071; `@highlights` supports filters such
  as condensed, scoring, homers, defense, pitching, recap, interviews, and data;
  `@more` pages through the previous highlights result; the feature is
  committed at `d6956eefda17a1f54998ba9f9f04392971b8ac25`, deployed on the VPS,
  and live `#mlbtest` probes pass. Next useful step is a compact live sweep of
  `@preview`, expanded split aliases, and any naturally firing scoring-state
  alert during active games.

## 2026-06-08 - TASK-070: Resolve Highlight Links To MP4

- Goal: make `@highlights` share direct MLB MP4 playback links instead of
  public MLB video page links when direct media is available.
- Starting point: local `main` is clean and ahead of `origin/main` by the
  TASK-069 handoff-only deployment record commit; deployed app code is at
  `a7350e895fd0ff93ea27954a95cab7d74c39b21f`.
- Planned changes: prefer MP4 playback URLs from `/api/v1/game/{gamePk}/content`,
  add an MLB video-page metadata fallback for slug-only highlight links, update
  `@highlights` docs/tests to expect direct MP4 links, run local checks, commit,
  and deploy so IRC receives the new links.
- Changes: `GameHighlight` now keeps an optional `page_url`; game-content
  parsing prefers direct MP4 playbacks, especially MLB's `mp4Avc` URL, before
  falling back to public MLB video pages; slug-only MLB video links are resolved
  through public page `og:video` metadata when needed; `@highlights` prints the
  resolved MP4 URL because the formatter uses `GameHighlight.url`; highlights
  now emit one IRC line per returned clip so long MP4 URLs do not hide links
  behind an omitted-count suffix.
- Verification: focused parser/command tests pass; `.\.venv\Scripts\python -m
  pytest -q -o cache_dir=.tmp\task070-pytest-cache
  --basetemp=.tmp\task070-pytest-basetemp` passes with 55 tests and known
  dependency deprecation warnings; `.\.venv\Scripts\python -m ruff check .`
  passes; `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes; `git diff
  --check` passes. A live client probe for game `822807` resolved the Brandon
  Valenzuela sample highlight to
  `https://mlb-cuts-diamond.mlb.com/FORGE/2026/2026-06/07/5ede2bd0-63d98c4c-69ac4da6-csvm-diamondgcp-asset_1280x720_59_4000K.mp4`.
- Commit: `5a8f78ad5aa362206cb11754226f2173ae777671`.
- Deployment: pushed and deployed `5a8f78a` to the VPS with
  `powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy.ps1`; the
  remote checkout fast-forwarded to `5a8f78ad5aa362206cb11754226f2173ae777671`,
  the `mlb-irc-bot` Compose service rebuilt/recreated successfully, and the
  in-container dry-run passed for `slopstats` on Libera `#mlbtest`.
- Live check: joined Libera `#mlbtest` as `AIHighlight656` and confirmed
  `@highlights game 822807` returned three separate IRC replies, each with a
  direct `.mp4` URL, including the Brandon Valenzuela sample URL.
- Resume prompt: Continue after TASK-070; `@highlights` resolves MLB highlight
  page links to direct MP4 URLs when available, emits one IRC line per returned
  highlight, is committed at `5a8f78ad5aa362206cb11754226f2173ae777671`, and is
  deployed on the VPS with live `#mlbtest` proof. Next useful step is a compact
  live sweep of `@preview`, expanded split aliases, and any naturally firing
  scoring-state alert during active games.

## 2026-06-08 - TASK-069: Complete Help Coverage And Deploy

- Goal: make `@help` cover every command and subcommand/alias, then deploy the
  current branch to the VPS.
- Starting point: local `main` is clean and ahead of `origin/main` by TASK-066
  through TASK-068 commits; TASK-068 is locally verified but not deployed.
- Planned changes: add per-command `@help` topics for all routed commands and
  aliases, add a regression that help coverage stays aligned with the command
  router, run the standard local checks, commit the help fix, deploy with the
  canonical PowerShell script, and record the deployed commit.
- Changes: added command-specific help for `@preview`/`@matchup`, `@highlights`,
  `@wp`, `@stars`, `@weather`, `@replay`, pitcher and lineup commands,
  standings and wildcard, player/team stats, defense/arsenal, transactions, and
  `@help`; documented `@preview game GAMEPK` in the command docs and README;
  added a regression that all routed commands and aliases have topic help.
- Verification: `.\.venv\Scripts\python -m pytest tests\unit\test_commands.py
  -q -o cache_dir=.tmp\task069-focused-pytest-cache
  --basetemp=.tmp\task069-focused-pytest-basetemp` passes with 31 tests;
  `.\.venv\Scripts\python -m pytest -q -o cache_dir=.tmp\task069-pytest-cache
  --basetemp=.tmp\task069-pytest-basetemp` passes with 55 tests and known
  dependency deprecation warnings; `.\.venv\Scripts\python -m ruff check .`
  passes; `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes; `git diff
  --check` passes.
- Commit: `a7350e895fd0ff93ea27954a95cab7d74c39b21f`.
- Deployment: pushed and deployed `a7350e8` to the VPS with
  `powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy.ps1`; the
  remote checkout fast-forwarded from `75ba89a` to
  `a7350e895fd0ff93ea27954a95cab7d74c39b21f`, the `mlb-irc-bot` Compose
  service rebuilt/recreated successfully, and the in-container dry-run passed
  for `slopstats` on Libera `#mlbtest`.
- Live check: joined Libera `#mlbtest` as `AIHelpCheck543` and confirmed
  `slopstats` answered `@help`, `@help preview`, `@help highlights`,
  `@help wildcard`, and `@help help` with the updated deployed help text,
  including `@preview game GAMEPK` and the command/alias topic message.
- Resume prompt: Continue after TASK-069; help coverage is complete, committed
  at `a7350e895fd0ff93ea27954a95cab7d74c39b21f`, deployed on the VPS, and live
  `#mlbtest` help probes pass. Next useful step is a compact live sweep of
  `@preview`, `@highlights`, expanded split aliases, and any naturally firing
  scoring-state alert during active games.

## 2026-06-08 - TASK-068: Preview Highlights Splits And Scoring Alerts

- Goal: implement the approved feature batch: compact `@preview`/`@matchup` game previews, `@highlights` game media links, expanded split aliases, and lead-change/tie-game/walk-off alerts.
- Starting point: local `main` is clean and ahead of `origin/main` by the TASK-066 and TASK-067 handoff commits; current commands already cover schedules, game detail, boxscores, win probability, stars, weather/replay, player/team stats, transactions, and leaders.
- Planned changes: add MLB client models/parsers and IRC formatters for game previews and game content highlights; add command routing/help/docs for `@preview`, `@matchup`, and `@highlights`; expand `situation_code` aliases used by player and team splits; add scoring-state alert detectors for ties, lead changes, and walk-offs with config toggles; add focused unit coverage and run pytest, ruff, and dry-run.
- Changes: added `@preview`/`@matchup` game previews with probables, weather,
  lineup status, and team form where available; added `@highlights TEAM` and
  `@highlights game GAMEPK` from `/api/v1/game/{gamePk}/content`; expanded
  split aliases for day/night, grass/turf, score state, starter/reliever,
  league-opponent, and batting-order contexts; added tied-game, go-ahead or
  lead-change, and walk-off alerts behind `MLB_ENABLE_ALERT_LEAD_CHANGES`.
- Verification: `.\.venv\Scripts\python -m pytest -q -o
  cache_dir=.tmp\task068-pytest-cache
  --basetemp=.tmp\task068-pytest-basetemp` passes with 54 tests and known
  dependency deprecation warnings; `.\.venv\Scripts\python -m ruff check .`
  passes; `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes.
- Commit: `ff4e8985d9f34b0bc1a466d2048ff9a5b92eb29b`.
- Resume prompt: Continue after TASK-068; preview/highlight commands, expanded
  split aliases, and scoring-state alerts are implemented and locally verified.
  Next useful step is deployment to the VPS if the new commands/alerts should
  go live, followed by a compact `#mlbtest` sweep of `@preview`, `@highlights`,
  expanded split aliases, and any naturally firing scoring-state alert.

## 2026-06-08 - TASK-067: Bound Leaders Output

- Goal: reproduce and fix `@leaders` output truncation and prevent spammy high
  limits such as `@leaders HR 300`.
- Starting point: local `main` is ahead of `origin/main` by the two TASK-066
  formatting-preview handoff commits; `@leaders` already clamps integer limits
  internally, but that behavior is under-tested and all returned leaders are
  still formatted into one IRC message.
- Planned changes: add tests for leader-limit clamping and overlong leader
  formatting, cap user-requested leader limits to an IRC-safe maximum, make
  leader formatting reserve room for a concise omitted-count suffix instead of
  blind truncation, update command docs/backlog/memory, then run pytest, ruff,
  and dry-run.
- Changes: named the `@leaders`, `@teamrank`, and `@teamleaders` limit caps;
  kept `@leaders` capped at 10; changed league leader formatting to include
  whole entries only and append `+N more` when long names/teams would exceed
  the IRC message budget; documented the caps.
- Verification: `.\.venv\Scripts\python -m pytest -q -o
  cache_dir=.tmp\task067-pytest-cache
  --basetemp=.tmp\task067-pytest-basetemp` passes with 50 tests and known
  dependency deprecation warnings; `.\.venv\Scripts\python -m ruff check .`
  passes; `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes.
- Commit: `3fb84be078f77fbf771568a05e844bb3eaa0123f`.
- Resume prompt: Continue after TASK-067; `@leaders` limit clamping and
  whole-entry omitted-count formatting are covered by tests and passing local
  checks. The local branch is ahead of `origin/main` by the TASK-066 handoff
  commits plus TASK-067; deploy only if you want the leader-output fix live on
  the VPS. Next useful candidates are a naturally firing alert preview during
  live games or adding a Docker Compose config check in an environment with
  Docker.

## 2026-06-08 - TASK-066: Preview Deployed Formatting

- Goal: preview the deployed TASK-065 IRC formatting in real `#mlbtest` and
  record whether the calmer command/alert output is acceptable or needs a
  follow-up tweak.
- Starting point: `main` is clean and synced with `origin/main` at `75ba89a`;
  TASK-065 is documented as deployed to `mlbotslop` in Libera `#mlbtest`, and
  the backlog's next candidate is a focused live formatting preview.
- Planned changes: run the standard local checks, perform a compact live command
  sweep covering `@help`, `@mlb *`, `@mlb TEAM`, `@box TEAM`, and one
  stat-heavy command, then update `docs/tasks/backlog.md` and this handoff with
  the results.
- Local verification: `.\.venv\Scripts\python -m pytest -q -o
  cache_dir=.tmp\task066-pytest-cache
  --basetemp=.tmp\task066-pytest-basetemp` passes with 48 tests and known
  dependency deprecation warnings; `.\.venv\Scripts\python -m ruff check .`
  passes; `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes.
- Live preview: joined Libera `#mlbtest` as `AIFormatCheck606` and ran
  `@help`, `@mlb *`, `@mlb NYY`, `@box NYY`, and `@sstats Ohtani hitting`.
  `mlbotslop` returned one readable response for each command. The deployed
  formatting looked acceptably calm in raw IRC control output: colors were
  limited to titles/states, routine command/stat labels used bold or italic
  emphasis, and resets were balanced.
- Gap: no live games were active during the preview, so no naturally firing
  alert could be judged in-channel.
- Commit: `1652e2e014757337ef3d59d8d278a74141e1d99f`.
- Resume prompt: Continue after TASK-066; deployed command formatting was
  previewed successfully in `#mlbtest`. The next useful live check is to watch a
  naturally firing alert when games are active and tweak alert presentation only
  if the added game context feels noisy in-channel. The Docker Compose config
  check remains a separate environment/CI candidate because Docker is not on
  this Windows PATH.

## 2026-06-08 - TASK-065: Add Alert Game Context And Calmer Formatting

- Goal: make live announcements more informative at a glance by adding score,
  inning, and outs context where the live feed exposes it, then apply a
  conservative formatting cleanup so IRC messages are easier to scan.
- Starting point: `main` is clean at `de3b85c`; TASK-064 restored scheduler
  reliability and deployed stale-baseline suppression. User approved
  implementing both the announcement-context change and a conservative
  formatting pass after a read-only formatting audit.
- Planned changes: add a reusable alert game-context helper in
  `src/mlb_irc_bot/alerts/detectors.py`; attach it to play/contextual alerts
  that currently lack score/inning/outs; keep game-info/final/bases-loaded
  behavior coherent; tune central IRC styling and dense formatter output only
  where the blast radius is controlled; update tests and docs.
- Changes: added a reusable alert game-update helper that appends current score,
  inning, and outs where the live feed exposes them; attached that context to
  HR, scoring, win-probability, high-leverage, hard-hit/barrel, bases-loaded,
  no-hit, cycle, and immaculate-inning alerts. Kept game-info and final alerts
  in their natural formats.
- Formatting: grouped top-level `@help`, made live `@mlb TEAM` and `@box`
  replies use clearer section labels, parenthesized pitcher game summaries,
  removed embedded `|` separators from batter stat summaries, and introduced
  plain `irc.stat_value()` for routine stat-list values so bold is more
  conservative without removing emphasis from scores and alert prefixes.
- Local verification: `.\.venv\Scripts\python -m pytest -q -o cache_dir=.tmp\task065-pytest-cache --basetemp=.tmp\task065-pytest-basetemp`
  passes with 48 tests; `.\.venv\Scripts\python -m ruff check .` passes;
  `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes.
- Deployment: pushed and deployed `6251942` to the VPS with
  `powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy.ps1`. The
  script fast-forwarded `/home/wolfb/mlbot`, rebuilt/recreated
  `mlb-irc-bot`, and the in-container dry-run passed for `mlbotslop` on Libera
  `#mlbtest`.
- Post-deploy check: `docker compose ps` showed `mlbot-mlb-irc-bot-1` up;
  in-container `python -m mlb_irc_bot --dry-run` passed; `docker inspect`
  showed `status=running`, `running=true`, `restarts=0`, and
  `started=2026-06-08T13:08:44.074797494Z`; the remote checkout was clean at
  `62519428bdbab99d240b326ac10af809a7db31bc`.
- Commit: `8f4d9ef154eccce6e295071f9c8bfb6c31df3e3c`.
- Resume prompt: Continue after TASK-065; alert-context and calmer formatting
  changes are deployed to `mlbotslop` in Libera `#mlbtest`. When games are live,
  preview `@help`, `@mlb *`, `@mlb TEAM`, `@box TEAM`, one stat-heavy command,
  and any naturally firing alert; if formatting needs tweaks, keep them narrow
  in `src/mlb_irc_bot/irc_format.py`, `src/mlb_irc_bot/mlb/formatters.py`, or
  `src/mlb_irc_bot/alerts/detectors.py`.

## 2026-06-08 - TASK-064: Restore Live Announcement Scheduler

- Goal: troubleshoot and restore IRC announcements after `mlbotslop` stayed online but stopped posting live channel alerts.
- Starting point: local `main` is ahead of `origin/main` by four release-workflow commits; VPS checkout is on `56753e2` with the container up for 24 hours, commands answering in `#mlbtest`, and the alert store showing no new rows after `2026-06-07T01:11Z`.
- Live check: joined Libera `#mlbtest` as `AIAnnounceCheck`; `mlbotslop` was present and answered private `@mlb *` checks, but no channel announcements appeared during a 150-second wait while SF@CHC was live.
- Finding: a direct in-container scheduler probe found fresh unseen alerts for the active game and many final games, while the SQLite alert store had no rows newer than the prior deploy window. The IRC command loop was alive, so the background scheduler had likely died or stalled silently.
- Changes: supervised `LiveScheduler.run_forever()` so poll failures are logged and retried, kept per-game alert collection failures from stopping the whole poll, kept one failed IRC send from terminating remaining alert delivery, and baselined already-live/final games on first scheduler poll to avoid stale alert floods after a restart.
- Local verification: `.\.venv\Scripts\python -m pytest -q -o cache_dir=.tmp\task064-pytest-cache --basetemp=.tmp\task064-pytest-basetemp` passes with 47 tests; `.\.venv\Scripts\python -m ruff check .` passes; `.\.venv\Scripts\python -m mlb_irc_bot --dry-run` passes.
- Deployment: pushed and deployed `826ab3a` to the VPS. The deploy script rebuilt/restarted `mlb-irc-bot` and the in-container dry-run passed for `mlbotslop` on Libera `#mlbtest`.
- Live verification: `docker compose logs` showed the new scheduler running and suppressing stale first-poll alerts, including 3 existing alerts for live game `824670` (SF@CHC). Rejoined `#mlbtest` twice after deploy; `mlbotslop` answered private `@mlb *` checks. No new channel alert appeared during the watch windows because a direct feed check still showed only the same 3 alert keys that had already been baselined.
- Commit: `826ab3a9f3a0ad068a5a37e2a2e8f53065d98501`.
- Resume prompt: Continue after TASK-064; the live scheduler is deployed with crash supervision and stale-backfill suppression. If announcements are questioned again, check `docker compose logs mlb-irc-bot` for scheduler exceptions/suppression lines, then compare the active game feed's alert keys against the SQLite store before changing code.

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
