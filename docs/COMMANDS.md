# Commands

The bot listens for commands beginning with `@` by default.

## Game And Schedule

- `@mlb`: today's MLB schedule in one compact message.
- `@mlb *`: live games only.
- `@mlb tomorrow`: tomorrow's MLB schedule in one compact message.
- `@mlb yesterday`: yesterday's final scores.
- `@mlb TEAM`: today's game for a team abbreviation or alias. Live games include win probability and active pitchers.
- `@mlb TEAM tomorrow`: tomorrow's game for a team.
- `@mlb TEAM yesterday`: previous day result for a team.
- `@mlb game GAMEPK`: details for one MLB game id.

Examples:

```text
@mlb
@mlb *
@mlb NYY
@mlb LAD tomorrow
@mlb game 824832
```

## Game Details

- `@box TEAM [today|yesterday]`: compact R-H-E boxscore for a team's game.
- `@box game GAMEPK`: compact R-H-E boxscore for one MLB game id.
- `@mlbpitcher TEAM`: current pitcher for that team's game, with game stats.
- `@mlbpitchers TEAM`: all pitchers used in that team's game, with game stats.
- `@mlblineup TEAM`: posted lineup for that team, or a message if unavailable.

Examples:

```text
@box NYY
@box game 824832
@mlbpitcher NYY
@mlbpitchers LAD
@mlblineup SEA
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

- `@sstats <player name> [hitting|pitching|fielding] [season] [7 days|14 days|30 days]`: season stats or recent date-range stats. Pitchers default to pitching stats; everyone else defaults to hitting.
- `@teamstats TEAM [hitting|pitching] [season] [7 days|14 days|30 days]`: team hitting and/or pitching stats.
- `@transactions [TEAM] [today|yesterday|7 days|YYYY-MM-DD]`: recent MLB or team transactions.
- `@leaders <category> [limit]`: stat leaders.

Examples:

```text
@sstats Shohei Ohtani hitting
@sstats Tarik Skubal
@sstats Tarik Skubal pitching 2025
@sstats Shohei Ohtani hitting 7 days
@sstats Aaron Judge 30 days
@teamstats TOR
@teamstats LAD pitching 14 days
@transactions
@transactions TOR 7 days
@leaders homeRuns 5
```

## Help

- `@help`: all commands.
- `@help mlb`: detailed help for `@mlb`.
