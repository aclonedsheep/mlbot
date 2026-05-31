import asyncio
from datetime import date, datetime
from typing import Any

import httpx

from mlb_irc_bot.mlb.hydrate import SCHEDULE_HYDRATE, schedule_params
from mlb_irc_bot.mlb.models import (
    GameDetail,
    GameSummary,
    JsonDict,
    Leader,
    LinescoreSnapshot,
    PlayerSearchResult,
    PlayerStats,
    StandingTeam,
    TeamInfo,
)
from mlb_irc_bot.mlb.teams import TEAM_DIRECTORY


class MLBAPIError(RuntimeError):
    pass


LEADER_GROUPS: dict[str, str] = {
    "homeRuns": "hitting",
    "rbi": "hitting",
    "runs": "hitting",
    "hits": "hitting",
    "battingAverage": "hitting",
    "ops": "hitting",
    "stolenBases": "hitting",
    "era": "pitching",
    "wins": "pitching",
    "strikeouts": "pitching",
    "strikeOuts": "pitching",
    "saves": "pitching",
    "whip": "pitching",
}

LEADER_ALIASES: dict[str, str] = {
    "hr": "homeRuns",
    "home_runs": "homeRuns",
    "homeruns": "homeRuns",
    "avg": "battingAverage",
    "average": "battingAverage",
    "sb": "stolenBases",
    "k": "strikeouts",
    "ks": "strikeouts",
    "so": "strikeouts",
}


class MLBStatsClient:
    def __init__(
        self,
        *,
        base_url: str = "https://statsapi.mlb.com/api",
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "MLBStatsClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def get_schedule(self, target_date: date, team_id: int | None = None) -> list[GameSummary]:
        payload = await self._get("/v1/schedule", params=schedule_params(target_date.isoformat(), team_id))
        return [self._parse_schedule_game(game) for day in payload.get("dates", []) for game in day.get("games", [])]

    async def get_schedule_by_game_pk(self, game_pk: int) -> GameSummary | None:
        payload = await self._get(
            "/v1/schedule",
            params={"sportId": 1, "gamePk": game_pk, "hydrate": SCHEDULE_HYDRATE},
        )
        games = [game for day in payload.get("dates", []) for game in day.get("games", [])]
        return self._parse_schedule_game(games[0]) if games else None

    async def get_game_detail(self, game_pk: int) -> GameDetail:
        try:
            live = await self._get(f"/v1/game/{game_pk}/feed/live")
            return self._parse_live_game(live)
        except MLBAPIError:
            summary = await self.get_schedule_by_game_pk(game_pk)
            if summary is None:
                raise
            fallback: JsonDict = {"scheduleGame": summary.raw, "gamePk": game_pk}
            for endpoint in ("linescore", "boxscore", "playByPlay"):
                try:
                    fallback[endpoint] = await self._get(f"/v1/game/{game_pk}/{endpoint}")
                except MLBAPIError:
                    fallback[endpoint] = {}
            last_play = self._last_play_from_play_by_play(fallback.get("playByPlay", {}))
            return GameDetail(summary=summary, last_play=last_play, raw=fallback)

    async def get_standings(
        self,
        *,
        season: int,
        standings_type: str = "regularSeason",
        league: str | None = None,
    ) -> list[StandingTeam]:
        league_id = {"AL": "103", "NL": "104"}.get(league.upper() if league else "", "103,104")
        payload = await self._get(
            "/v1/standings",
            params={
                "leagueId": league_id,
                "season": season,
                "standingsTypes": standings_type,
                "hydrate": "team,league,division",
            },
        )
        records: list[StandingTeam] = []
        for record in payload.get("records", []):
            league_name = _name(record.get("league"))
            division_name = _name(record.get("division"))
            for team_record in record.get("teamRecords", []):
                team = team_record.get("team") or {}
                team_id = team.get("id")
                records.append(
                    StandingTeam(
                        team_id=team_id,
                        team_name=team.get("name") or TEAM_DIRECTORY.name_for_id(team_id),
                        abbreviation=team.get("abbreviation") or TEAM_DIRECTORY.abbreviation_for_id(team_id),
                        league_name=league_name,
                        division_name=division_name,
                        wins=_int(team_record.get("wins")),
                        losses=_int(team_record.get("losses")),
                        pct=str(team_record.get("winningPercentage") or team_record.get("pct") or ""),
                        games_back=str(team_record.get("gamesBack") or "-"),
                        wild_card_games_back=str(team_record.get("wildCardGamesBack") or "-"),
                        division_rank=str(team_record.get("divisionRank") or ""),
                        league_rank=str(team_record.get("leagueRank") or ""),
                        wild_card_rank=str(team_record.get("wildCardRank") or ""),
                        streak=_streak(team_record.get("streak")),
                        last_ten=_last_ten(team_record.get("records", {})),
                    )
                )
        return records

    async def search_people(self, name: str) -> list[PlayerSearchResult]:
        payload = await self._get("/v1/people/search", params={"names": name})
        return [
            PlayerSearchResult(
                person_id=person["id"],
                full_name=person.get("fullName", ""),
                team_name=_name(person.get("currentTeam")),
                position=_name(person.get("primaryPosition")),
                active=person.get("active"),
            )
            for person in payload.get("people", [])
            if person.get("id") is not None
        ]

    async def get_player_stats(self, player: PlayerSearchResult, *, group: str, season: int) -> PlayerStats:
        payload = await self._get(
            f"/v1/people/{player.person_id}/stats",
            params={"stats": "season", "group": group, "season": season, "sportId": 1},
        )
        splits = payload.get("stats", [{}])[0].get("splits", [])
        stats = splits[0].get("stat", {}) if splits else {}
        return PlayerStats(player=player, group=group, season=season, stats=stats)

    async def get_leaders(self, category: str, *, season: int, limit: int = 5) -> list[Leader]:
        category = normalize_leader_category(category)
        stat_group = LEADER_GROUPS.get(category, "hitting")
        payload = await self._get(
            "/v1/stats/leaders",
            params={
                "leaderCategories": category,
                "season": season,
                "sportId": 1,
                "statGroup": stat_group,
                "leaderGameTypes": "R",
                "limit": limit,
            },
        )
        leaders: list[Leader] = []
        for group in payload.get("leagueLeaders", []):
            for leader in group.get("leaders", []):
                person = leader.get("person") or {}
                team = leader.get("team") or {}
                leaders.append(
                    Leader(
                        rank=str(leader.get("rank") or ""),
                        value=str(leader.get("value") or ""),
                        player_name=person.get("fullName") or person.get("name") or "",
                        team_name=team.get("name"),
                    )
                )
        return leaders[:limit]

    async def available_schedule_hydrations(self, target_date: date) -> list[str]:
        payload = await self._get(
            "/v1/schedule",
            params={"sportId": 1, "date": target_date.isoformat(), "hydrate": "hydrations"},
        )
        return list(payload.get("hydrations", []))

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> JsonDict:
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = await self._client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(0.25)
        raise MLBAPIError(f"MLB API request failed for {path}: {last_error}") from last_error

    def _parse_schedule_game(self, game: JsonDict) -> GameSummary:
        teams = game.get("teams", {})
        away_wrapper = teams.get("away", {})
        home_wrapper = teams.get("home", {})
        status = game.get("status") or {}
        return GameSummary(
            game_pk=int(game["gamePk"]),
            game_date=_parse_datetime(game.get("gameDate")),
            official_date=_parse_date(game.get("officialDate")),
            status=status.get("abstractGameState") or status.get("detailedState") or "",
            abstract_state=status.get("abstractGameState") or "",
            detailed_state=status.get("detailedState") or "",
            away=_team_from_wrapper(away_wrapper),
            home=_team_from_wrapper(home_wrapper),
            away_score=_optional_int(away_wrapper.get("score")),
            home_score=_optional_int(home_wrapper.get("score")),
            venue=_name(game.get("venue")),
            away_probable_pitcher=_name(away_wrapper.get("probablePitcher")),
            home_probable_pitcher=_name(home_wrapper.get("probablePitcher")),
            linescore=_parse_linescore(game.get("linescore") or {}),
            series_description=game.get("seriesDescription"),
            raw=game,
        )

    def _parse_live_game(self, payload: JsonDict) -> GameDetail:
        game_data = payload.get("gameData", {})
        live_data = payload.get("liveData", {})
        teams = game_data.get("teams", {})
        status = game_data.get("status") or {}
        linescore = live_data.get("linescore") or {}
        away_team = teams.get("away", {})
        home_team = teams.get("home", {})
        summary = GameSummary(
            game_pk=int(game_data.get("game", {}).get("pk") or payload.get("gamePk")),
            game_date=_parse_datetime(game_data.get("datetime", {}).get("dateTime")),
            official_date=_parse_date(game_data.get("datetime", {}).get("officialDate")),
            status=status.get("abstractGameState") or status.get("detailedState") or "",
            abstract_state=status.get("abstractGameState") or "",
            detailed_state=status.get("detailedState") or "",
            away=_team_from_team(away_team),
            home=_team_from_team(home_team),
            away_score=_optional_int((linescore.get("teams", {}).get("away") or {}).get("runs")),
            home_score=_optional_int((linescore.get("teams", {}).get("home") or {}).get("runs")),
            venue=_name(game_data.get("venue")),
            linescore=_parse_linescore(linescore),
            raw=payload,
        )
        return GameDetail(
            summary=summary,
            last_play=self._last_play_from_play_by_play(live_data.get("plays", {})),
            raw=payload,
        )

    @staticmethod
    def _last_play_from_play_by_play(play_data: JsonDict) -> str | None:
        plays = play_data.get("allPlays", [])
        if not plays:
            return None
        result = plays[-1].get("result") or {}
        return result.get("description") or result.get("event")


def normalize_leader_category(category: str) -> str:
    compact = category.strip().replace("-", "_")
    return LEADER_ALIASES.get(compact.lower(), category)


def _team_from_wrapper(wrapper: JsonDict) -> TeamInfo:
    return _team_from_team(wrapper.get("team") or {})


def _team_from_team(team: JsonDict) -> TeamInfo:
    team_id = team.get("id")
    return TeamInfo(
        id=team_id,
        name=team.get("name") or TEAM_DIRECTORY.name_for_id(team_id),
        abbreviation=team.get("abbreviation") or TEAM_DIRECTORY.abbreviation_for_id(team_id),
    )


def _parse_linescore(data: JsonDict) -> LinescoreSnapshot | None:
    if not data:
        return None
    offense = data.get("offense") or {}
    runners = tuple(base for base in ("first", "second", "third") if offense.get(base))
    return LinescoreSnapshot(
        current_inning=_optional_int(data.get("currentInning")),
        inning_state=data.get("inningState"),
        inning_half=data.get("inningHalf"),
        balls=_optional_int(data.get("balls")),
        strikes=_optional_int(data.get("strikes")),
        outs=_optional_int(data.get("outs")),
        runners=runners,
    )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _int(value: Any) -> int:
    return int(value or 0)


def _name(value: JsonDict | None) -> str:
    if not value:
        return ""
    return value.get("name") or value.get("fullName") or value.get("abbreviation") or ""


def _streak(value: JsonDict | None) -> str:
    if not value:
        return ""
    return str(value.get("streakCode") or value.get("streakType") or "")


def _last_ten(records: JsonDict) -> str:
    for split in records.get("splitRecords", []):
        if split.get("type") == "lastTen":
            return f"{split.get('wins', 0)}-{split.get('losses', 0)}"
    return ""
