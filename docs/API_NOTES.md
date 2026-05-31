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

## Hydrate Probe

Planning probe on 2026-05-31:

- `hydrate=team,linescore,probablePitcher,flags` returned schedule games with `linescore`.
- `hydrate=hydrations` returned the hydration catalog, not hydrated game data.

The implementation keeps hydration strings centralized in `mlb/hydrate.py` and includes tests for fallback behavior.

Use `mlb-api-probe --date YYYY-MM-DD` for an opt-in live check of schedule hydration behavior.

## Usage Notice

MLBAM states that individual, non-commercial, non-bulk use of MLB materials is permitted, and other uses require authorization. Keep polling conservative and cache responses where practical.
