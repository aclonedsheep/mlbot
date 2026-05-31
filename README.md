# MLB IRC Bot

Async IRC bot for a single MLB channel. It answers schedule, game, standings, wildcard, player stat, and leader commands, and posts live league-wide alerts.

## Commands

- `@mlb` shows today's schedule, live games, and final scores.
- `@mlb tomorrow` shows tomorrow's schedule.
- `@mlb TEAM` shows today's game for a team.
- `@mlb TEAM tomorrow` shows tomorrow's game for a team.
- `@mlb game GAMEPK` shows one game by MLB game id.
- `@standings [AL|NL|division|TEAM]` shows regular-season standings.
- `@wildcard [AL|NL|all]` shows wildcard standings.
- `@sstats <player name> [hitting|pitching|fielding] [season]` shows season stats.
- `@leaders <category> [limit]` shows stat leaders.
- `@help [command]` lists command help.

See [docs/COMMANDS.md](docs/COMMANDS.md) for details.

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
