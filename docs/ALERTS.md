# Alerts

The bot is designed for one configured MLB channel and posts league-wide alerts there.

Alert types are enabled or disabled through environment variables, not IRC commands.

## Alert Types

- Home runs.
- Scoring plays and run-scoring state changes.
- Home run scoring plays are posted as home run alerts only, not duplicate scoring alerts.
- Bases-loaded situations.
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
