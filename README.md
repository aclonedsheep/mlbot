# MLB IRC Bot

Async IRC bot for a single MLB channel. It answers schedule, game, standings, wildcard, player stat, and leader commands, and posts live league-wide alerts.

## Commands

- `@mlb` shows today's schedule in one compact message.
- `@mlb *` shows only live games.
- `@mlb tomorrow` shows tomorrow's schedule.
- `@mlb TEAM` shows today's game for a team, with win probability and active pitchers when live.
- `@mlb TEAM tomorrow` shows tomorrow's game for a team.
- `@mlb game GAMEPK` shows one game by MLB game id.
- `@preview TEAM`, `@matchup TEAM`, or `@preview game GAMEPK` shows a compact game preview with probables, weather, lineup status, and team form when available.
- `@box TEAM` or `@box game GAMEPK` shows a compact R-H-E boxscore.
- `@wp TEAM` shows current win probability and the biggest game swing.
- `@stars TEAM` shows top boxscore performers.
- `@weather TEAM` shows game weather.
- `@highlights TEAM`, `@highlights game GAMEPK`, or `@highlights scoring game GAMEPK` shows compact MLB highlight MP4 links when available.
- `@more` shows the next page from the previous highlights result.
- `@replay TEAM` shows replay challenge usage/remaining when available.
- `@mlbpitcher TEAM` shows the current pitcher and game pitching line.
- `@mlbpitchers TEAM` shows all pitchers used and their game pitching lines.
- `@mlblineup TEAM` shows the posted lineup for that team.
- `@standings [AL|NL|division|TEAM]` shows regular-season standings.
- `@wildcard [AL|NL|all]` shows wildcard standings.
- `@sstats <player name> [hitting|pitching|fielding] [season] [7 days|14 days|30 days|last N games]` shows season or recent stats, defaulting pitchers to pitching stats.
- `@gamelog <player name> [hitting|pitching] [N]` shows recent game log lines.
- `@splits <player name> <risp|vl|vr|home|away|lateclose|basesloaded> [hitting|pitching]` shows situational splits.
- `@teamstats TEAM [hitting|pitching] [season] [7 days|14 days|30 days] [split]` shows team hitting and/or pitching stats.
- `@teamrank <stat> [hitting|pitching] [limit]` shows team rankings.
- `@teamleaders TEAM [category] [limit]` shows team leaders.
- `@defense <player name> [season]` shows Outs Above Average-style defense stats.
- `@arsenal <player name> [season]` shows pitch mix.
- `@savant <player name> [season]` shows a Savant percentile snapshot.
- `@xstats <player name> [season]` shows Savant expected stats and batted-ball quality.
- `@speed <player name> [season]` shows Savant sprint speed.
- `@bat <player name> [season]` shows Savant bat tracking.
- `@runvalue <player name> [season]` shows Savant swing/take batting run value.
- `@fieldrv <player name> [season]` shows Savant fielding run value.
- `@baserun <player name> [season]` shows Savant baserunning run value.
- `@arm <player name> [season]` shows Savant arm strength.
- `@transactions [TEAM] [today|yesterday|7 days|YYYY-MM-DD]` shows recent player transactions.
- `@leaders <category> [limit]` shows stat leaders.
- `@help [command]` lists command help.

See [docs/COMMANDS.md](docs/COMMANDS.md) for details.

Live IRC replies use standard IRC bold, italic, and foreground color control codes
to make teams, states, section labels, and key values easier to scan. The examples
in this documentation are shown as plaintext.

## Local Setup

Use Python 3.12. The IRC dependency currently pins an async stack that is not compatible with Python 3.13.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edit `.env` with IRC connection details, then run:

```powershell
.\.venv\Scripts\python -m mlb_irc_bot
```

## Docker

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The SQLite database is stored under `data/` by default.

## MLB API Probe

Run the opt-in probe when checking for MLB API drift:

```powershell
.\.venv\Scripts\mlb-api-probe --date 2026-05-31
```

## API Notice

This project uses MLB Stats API endpoints that are publicly reachable but unofficial and may change without notice. MLB data usage is subject to the MLBAM notice referenced in [docs/API_NOTES.md](docs/API_NOTES.md).
