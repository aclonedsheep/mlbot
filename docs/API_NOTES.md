# MLB API Notes

The project calls the MLB Stats API directly instead of using a wrapper because hydrate behavior is a known drift point.

## Primary Endpoints

- Schedule: `/api/v1/schedule?sportId=1&date=YYYY-MM-DD&hydrate=team,linescore,probablePitcher,flags`
- Teams: `/api/v1/teams?sportId=1&season=YYYY`
- Regular standings: `/api/v1/standings?leagueId=103,104&season=YYYY&standingsTypes=regularSeason`
- Wildcard standings: `/api/v1/standings?leagueId=103,104&season=YYYY&standingsTypes=wildCard`
- Player search: `/api/v1/people/search`
- Player stats: `/api/v1/people/{personId}/stats`
- Game live feed: `/api/v1.1/game/{gamePk}/feed/live`, with `/api/v1/...` fallback
- Game fallback data: `/api/v1/game/{gamePk}/linescore`, `/boxscore`, `/playByPlay`
- Game context metrics: `/api/v1/game/{gamePk}/contextMetrics` for live win probability.
- Team stats: `/api/v1/teams/{teamId}/stats` with `season`, `group`, `stats`, and optional date range.
- Transactions: `/api/v1/transactions` with `sportId`, `teamId`, `startDate`, and `endDate`.
- Home run park counts: Baseball Savant `/leaderboard/home-runs?type=details&player_id={id}&year={year}&player_type=Batters&cat=xhr`.
  The bot matches Savant rows to MLB live-feed home run plays by batted-ball `playId`
  and treats this enrichment as optional.

## Player Stat Types

Live probes on 2026-05-31 showed the player stats endpoint accepting these useful `stats`
values:

- `season`: normal season totals and rates.
- `seasonAdvanced`: advanced rates such as ISO, BABIP, K/PA, BB/PA, K/9, BB/9, and whiff percentage.
- `sabermetrics`: public MLB Stats API sabermetric fields including WAR, wRC+, FIP, xFIP, and related run-value fields when available.
- `expectedStatistics`: expected-stat fields such as expected AVG, SLG, and wOBA-style values when available.
- `byDateRange` and `byDateRangeAdvanced`: date-window basic and advanced stats using `startDate` and `endDate`.

The bot treats advanced, sabermetric, and expected-stat responses as optional because
support can vary by group, player, date range, and future API changes. A separate paid API
is not required for the MLB Stats API WAR and expected-stat fields above, but complete
Baseball Savant/Statcast-style expected metrics may require Baseball Savant CSV endpoints
or another data source and should be considered less stable.

## Hydrate Probe

Planning probe on 2026-05-31:

- `hydrate=team,linescore,probablePitcher,flags` returned schedule games with `linescore`.
- `hydrate=hydrations` returned the hydration catalog, not hydrated game data.

The implementation keeps hydration strings centralized in `mlb/hydrate.py` and includes tests for fallback behavior.

Use `mlb-api-probe --date YYYY-MM-DD` for an opt-in live check of schedule hydration behavior.

## Usage Notice

MLBAM states that individual, non-commercial, non-bulk use of MLB materials is permitted, and other uses require authorization. Keep polling conservative and cache responses where practical.
