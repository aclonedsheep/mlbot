# Commands

The bot listens for commands beginning with `@` by default.

## Game And Schedule

- `@mlb`: today's MLB schedule with live status and final scores.
- `@mlb tomorrow`: tomorrow's MLB schedule.
- `@mlb yesterday`: yesterday's final scores.
- `@mlb TEAM`: today's game for a team abbreviation or alias.
- `@mlb TEAM tomorrow`: tomorrow's game for a team.
- `@mlb TEAM yesterday`: previous day result for a team.
- `@mlb game GAMEPK`: details for one MLB game id.

Examples:

```text
@mlb
@mlb NYY
@mlb LAD tomorrow
@mlb game 824832
```

## Standings

- `@standings`: AL and NL regular-season standings by division.
- `@standings AL`: American League standings.
- `@standings NL`: National League standings.
- `@standings TEAM`: standings context for one team.
- `@wildcard`: AL and NL wildcard standings.
- `@wildcard AL`: American League wildcard standings.
- `@wildcard NL`: National League wildcard standings.

## Stats

- `@sstats <player name> [hitting|pitching|fielding] [season]`: season stats.
- `@leaders <category> [limit]`: stat leaders.

Examples:

```text
@sstats Shohei Ohtani hitting
@sstats Tarik Skubal pitching 2025
@leaders homeRuns 5
```

## Help

- `@help`: all commands.
- `@help mlb`: detailed help for `@mlb`.
