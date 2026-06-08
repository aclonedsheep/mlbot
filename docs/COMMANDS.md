# Commands

The bot listens for commands beginning with `@` by default.

Live IRC replies include standard IRC bold, italic, and foreground color control
codes for readability. The examples below are plaintext.

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
- `@wp TEAM [today|yesterday]`: current win probability and the biggest win-probability swing.
- `@wp game GAMEPK`: win probability for one MLB game id.
- `@stars TEAM [today|yesterday]`: top boxscore performers.
- `@stars game GAMEPK`: top performers for one MLB game id.
- `@weather TEAM [today|yesterday]`: game weather when available.
- `@weather game GAMEPK`: weather for one MLB game id.
- `@replay TEAM [today|yesterday]`: replay challenge usage/remaining.
- `@replay game GAMEPK`: replay state for one MLB game id.
- `@mlbpitcher TEAM`: current pitcher for that team's game, with game stats.
- `@mlbpitchers TEAM`: all pitchers used in that team's game, with game stats.
- `@mlblineup TEAM`: posted lineup for that team, or a message if unavailable.

Examples:

```text
@box NYY
@box game 824832
@wp NYY
@stars game 824832
@weather LAD
@replay TOR
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

- `@sstats <player name> [hitting|pitching|fielding] [season] [7 days|14 days|30 days|last N games]`: season stats, recent date-range stats, or last-N-games stats. Pitchers default to pitching stats; everyone else defaults to hitting.
- `@gamelog <player name> [hitting|pitching] [N]`: recent game log lines.
- `@splits <player name> <risp|vl|vr|home|away|lateclose|basesloaded> [hitting|pitching] [season]`: situational player splits.
- `@teamstats TEAM [hitting|pitching] [season] [7 days|14 days|30 days] [risp|vl|vr|home|away|lateclose|basesloaded]`: team hitting and/or pitching stats, including situation splits.
- `@teamrank <stat> [hitting|pitching] [limit]`: team rankings for stats such as OPS, HR, ERA, WHIP, runs, and strikeouts. Limit is capped at 10.
- `@teamleaders TEAM [category] [limit]`: team leaders for one category, or a compact default set. Limit is capped at 5.
- `@defense <player name> [season]`: defense stats such as Outs Above Average and fielding runs prevented when available.
- `@arsenal <player name> [season]`: pitch mix, usage, average velocity, and counts.
- `@transactions [TEAM] [today|yesterday|7 days|YYYY-MM-DD]`: recent MLB or team transactions.
- `@leaders <category> [limit]`: stat leaders. Common aliases include `hr`, `rbi`, `ops`, `obp`, `slg`, `whip`, `k/9`, `k/bb`, `wRC+`, `WAR`, `FIP`, `xFIP`, and `xwOBA`. Limit is capped at 10.

Examples:

```text
@sstats Shohei Ohtani hitting
@sstats Tarik Skubal
@sstats Tarik Skubal pitching 2025
@sstats Shohei Ohtani hitting 7 days
@sstats Aaron Judge 30 days
@sstats Aaron Judge last 7 games
@gamelog Aaron Judge 5
@splits Aaron Judge risp
@teamstats TOR
@teamstats LAD pitching 14 days
@teamstats TOR hitting risp
@teamrank ops 5
@teamleaders TOR hr
@defense Daulton Varsho
@arsenal Tarik Skubal
@transactions
@transactions TOR 7 days
@leaders homeRuns 5
@leaders wRC+ 5
```

## Help

- `@help`: all commands.
- `@help mlb`: detailed help for `@mlb`.
