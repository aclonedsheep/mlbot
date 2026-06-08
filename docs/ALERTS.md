# Alerts

The bot is designed for one configured MLB channel and posts league-wide alerts there.

Alert types are enabled or disabled through environment variables, not IRC commands.

Most live game-state alerts append a compact update when the MLB live feed
exposes it: current score, inning, and outs. Pregame game-info alerts and final
score alerts keep their natural formats.

## Alert Types

- Home runs, including exit velocity, launch angle, and Baseball Savant
  other-park count when those fields are available.
- Scoring plays and run-scoring state changes.
- Home run scoring plays are posted as home run alerts only, not duplicate scoring alerts.
- Bases-loaded situations, including score, inning, outs, and current batter
  when the live feed exposes them.
- Large win-probability swings from the game win-probability endpoint.
- High-leverage plate appearances when leverage index crosses the configured threshold.
- Hard-hit non-home-run batted balls at or above the configured exit-velocity threshold.
- Barrel/sweet-spot non-home-run batted balls when exit velocity and launch angle are available.
- Late threats when the tying or go-ahead run is at the plate or on base in the seventh inning or later.
- Game-info alerts with first pitch, delay, and weather when the live feed exposes them.
- Final scores.
- No-hit and perfect-game bids after five completed innings, then after each later completed inning.
- Immaculate innings.
- Cycle watch when a batter is one hit type away from a cycle.
- Completed cycles.

## Dedupe

Alerts are deduplicated in SQLite using stable keys such as game id, play id, player id, inning, event type, and team.

## Polling

- Schedule refresh: every 5 minutes.
- Active games: every 15 seconds.
- Near-start games: every 60 seconds.
- Finished games: checked until a final-score alert is recorded.

## Tuning

New context alerts can be disabled independently with:

- `MLB_ENABLE_ALERT_WIN_PROBABILITY`
- `MLB_ENABLE_ALERT_HIGH_LEVERAGE`
- `MLB_ENABLE_ALERT_HARD_HIT`
- `MLB_ENABLE_ALERT_BARREL`
- `MLB_ENABLE_ALERT_LATE_THREAT`
- `MLB_ENABLE_ALERT_WEATHER`

Thresholds:

- `MLB_ALERT_HARD_HIT_THRESHOLD_MPH`, default `110`
- `MLB_ALERT_WIN_PROBABILITY_THRESHOLD`, default `15`
- `MLB_ALERT_HIGH_LEVERAGE_THRESHOLD`, default `2.5`
