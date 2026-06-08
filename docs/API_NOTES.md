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
- Game win-probability history: `/api/v1/game/{gamePk}/winProbability` for current game win probability, largest swings, and high-leverage play context.
- Game content: `/api/v1/game/{gamePk}/content` for MLB video highlight metadata, slugs, and MP4 playback URLs.
- Boxscore top performers: `/api/v1/game/{gamePk}/boxscore` and live-feed `liveData.boxscore.topPerformers`.
- Weather/replay/game info: live-feed `gameData.weather`, `gameData.review`, and `gameData.gameInfo`.
- Team stats: `/api/v1/teams/{teamId}/stats` with `season`, `group`, `stats`, and optional date range.
- Team rankings: `/api/v1/teams/stats` with `sortStat` and `order`.
- Team leaders: `/api/v1/teams/{teamId}/leaders`.
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
- `lastXGames`: compact recent player stats using `limit`.
- `gameLog`: game-by-game player stat lines.
- `statSplits`: situational splits using `sitCodes` such as `risp`, `vl`, `vr`, `h`, `a`, `lc`, and `r123`.
- `outsAboveAverage`: player defense fields such as total OAA and fielding runs prevented when available.
- `pitchArsenal`: pitch mix usage, count, and average speed.

The `/api/v1/{type}` metadata endpoint exposes useful catalogs. Live probes on
2026-06-06 confirmed `statTypes`, `statGroups`, `leagueLeaderTypes`, `metrics`,
`situationCodes`, and `rosterTypes`; a 2026-06-08 check confirmed additional
split codes such as day/night, grass/turf, score state, starter/reliever, league
opponent, and batting-order splits. The split commands use the public
`situationCodes` catalog; advanced leaders use `/api/v1/stats` rather than
`/api/v1/stats/leaders` when categories such as wRC+, WAR, FIP, xFIP, or xwOBA
are not available through the league-leader endpoint.

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
