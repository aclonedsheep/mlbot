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
    LineupEntry,
    PitcherInfo,
    PlayerSearchResult,
    PlayerStats,
    StandingTeam,
    TeamInfo,
    TeamLineup,
    TeamPitchers,
    TeamStats,
    Transaction,
    WinProbability,
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

    async def get_schedule(
        self, target_date: date, team_id: int | None = None
    ) -> list[GameSummary]:
        payload = await self._get(
            "/v1/schedule",
            params=schedule_params(target_date.isoformat(), team_id),
        )
        return [
            self._parse_schedule_game(game)
            for day in payload.get("dates", [])
            for game in day.get("games", [])
        ]

    async def get_schedule_by_game_pk(self, game_pk: int) -> GameSummary | None:
        payload = await self._get(
            "/v1/schedule",
            params={"sportId": 1, "gamePk": game_pk, "hydrate": SCHEDULE_HYDRATE},
        )
        games = [game for day in payload.get("dates", []) for game in day.get("games", [])]
        return self._parse_schedule_game(games[0]) if games else None

    async def get_game_detail(self, game_pk: int) -> GameDetail:
        for version in ("v1.1", "v1"):
            try:
                live = await self._get(f"/{version}/game/{game_pk}/feed/live")
                return self._parse_live_game(live)
            except MLBAPIError:
                continue

        summary = await self.get_schedule_by_game_pk(game_pk)
        if summary is None:
            raise MLBAPIError(f"MLB API request failed for game {game_pk}: no game data found")
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
                        abbreviation=(
                            team.get("abbreviation") or TEAM_DIRECTORY.abbreviation_for_id(team_id)
                        ),
                        league_name=league_name,
                        division_name=division_name,
                        wins=_int(team_record.get("wins")),
                        losses=_int(team_record.get("losses")),
                        pct=str(
                            team_record.get("winningPercentage") or team_record.get("pct") or ""
                        ),
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

    async def get_win_probability(self, game_pk: int) -> WinProbability | None:
        payload = await self._get(f"/v1/game/{game_pk}/contextMetrics")
        game = payload.get("game") or {}
        teams = game.get("teams") or {}
        away = _team_from_wrapper(teams.get("away") or {})
        home = _team_from_wrapper(teams.get("home") or {})
        away_probability = _optional_float(payload.get("awayWinProbability"))
        home_probability = _optional_float(payload.get("homeWinProbability"))
        if away_probability is None and home_probability is None:
            return None
        return WinProbability(
            away=away,
            home=home,
            away_probability=away_probability,
            home_probability=home_probability,
        )

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

    async def get_player_stats(
        self,
        player: PlayerSearchResult,
        *,
        group: str,
        season: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> PlayerStats:
        if (start_date is None) != (end_date is None):
            raise ValueError("start_date and end_date must be supplied together")

        if start_date and end_date:
            range_params = {
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
            }
            stats = await self._get_player_stat_split(
                player.person_id,
                stat_type="byDateRange",
                group=group,
                season=season,
                extra_params=range_params,
            )
            advanced = await self._try_player_stat_split(
                player.person_id,
                stat_type="byDateRangeAdvanced",
                group=group,
                season=season,
                extra_params=range_params,
            )
            return PlayerStats(
                player=player,
                group=group,
                season=season,
                stats=stats,
                advanced_stats=advanced,
                start_date=start_date,
                end_date=end_date,
            )

        stats = await self._get_player_stat_split(
            player.person_id,
            stat_type="season",
            group=group,
            season=season,
        )
        advanced = await self._try_player_stat_split(
            player.person_id,
            stat_type="seasonAdvanced",
            group=group,
            season=season,
        )
        sabermetric = await self._try_player_stat_split(
            player.person_id,
            stat_type="sabermetrics",
            group=group,
            season=season,
        )
        expected = await self._try_player_stat_split(
            player.person_id,
            stat_type="expectedStatistics",
            group=group,
            season=season,
        )
        return PlayerStats(
            player=player,
            group=group,
            season=season,
            stats=stats,
            advanced_stats=advanced,
            sabermetric_stats=sabermetric,
            expected_stats=expected,
        )

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

    async def get_team_stats(
        self,
        team: TeamInfo,
        *,
        group: str,
        season: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TeamStats:
        if team.id is None:
            raise ValueError(f"missing MLB team id for {team.abbreviation}")
        if (start_date is None) != (end_date is None):
            raise ValueError("start_date and end_date must be supplied together")

        params: dict[str, Any] = {
            "season": season,
            "group": group,
            "stats": "season",
            "gameType": "R",
        }
        if start_date and end_date:
            params["stats"] = "byDateRange"
            params["startDate"] = start_date.isoformat()
            params["endDate"] = end_date.isoformat()
        payload = await self._get(f"/v1/teams/{team.id}/stats", params=params)
        stat = _best_stat_split(payload)
        return TeamStats(
            team=team,
            group=group,
            season=season,
            stats=stat,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_transactions(
        self,
        *,
        start_date: date,
        end_date: date,
        team_id: int | None = None,
    ) -> list[Transaction]:
        params: dict[str, Any] = {
            "sportId": 1,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        }
        if team_id is not None:
            params["teamId"] = team_id
        payload = await self._get("/v1/transactions", params=params)
        transactions = [
            _parse_transaction(transaction)
            for transaction in payload.get("transactions") or ()
        ]
        return sorted(
            transactions,
            key=lambda item: (
                item.date or date.min,
                item.transaction_id or 0,
            ),
            reverse=True,
        )

    async def available_schedule_hydrations(self, target_date: date) -> list[str]:
        payload = await self._get(
            "/v1/schedule",
            params={"sportId": 1, "date": target_date.isoformat(), "hydrate": "hydrations"},
        )
        return list(payload.get("hydrations", []))

    async def _get_player_stat_split(
        self,
        person_id: int,
        *,
        stat_type: str,
        group: str,
        season: int,
        extra_params: dict[str, str] | None = None,
    ) -> JsonDict:
        params = {
            "stats": stat_type,
            "group": group,
            "season": season,
            "sportId": 1,
            "gameType": "R",
        }
        if extra_params:
            params.update(extra_params)
        payload = await self._get(f"/v1/people/{person_id}/stats", params=params)
        return _best_stat_split(payload)

    async def _try_player_stat_split(
        self,
        person_id: int,
        *,
        stat_type: str,
        group: str,
        season: int,
        extra_params: dict[str, str] | None = None,
    ) -> JsonDict:
        try:
            return await self._get_player_stat_split(
                person_id,
                stat_type=stat_type,
                group=group,
                season=season,
                extra_params=extra_params,
            )
        except MLBAPIError:
            return {}

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


def current_pitcher_for_team(detail: GameDetail, team_id: int) -> PitcherInfo | None:
    linescore = _raw_linescore(detail.raw)
    for side in ("defense", "offense"):
        side_data = linescore.get(side) or {}
        team = _team_from_team(side_data.get("team") or {})
        if team.id == team_id and side_data.get("pitcher"):
            pitcher_id = _optional_int(side_data["pitcher"].get("id"))
            player_record = _pitcher_record_with_team(detail, pitcher_id)
            if player_record:
                player, player_team = player_record
                return _pitcher_from_player_record(player, player_team, pitcher_id)
            return _pitcher_from_person(side_data["pitcher"], team)
    return None


def active_pitchers(detail: GameDetail) -> list[PitcherInfo]:
    pitchers: list[PitcherInfo] = []
    seen: set[int] = set()
    for team_id in (detail.summary.away.id, detail.summary.home.id):
        if team_id is None:
            continue
        pitcher = current_pitcher_for_team(detail, team_id)
        if pitcher is None:
            continue
        dedupe_id = pitcher.player_id or id(pitcher)
        if dedupe_id in seen:
            continue
        seen.add(dedupe_id)
        pitchers.append(pitcher)
    return pitchers


def pitchers_by_team(detail: GameDetail) -> list[TeamPitchers]:
    teams = _raw_boxscore(detail.raw).get("teams") or {}
    team_pitchers: list[TeamPitchers] = []
    for side in ("away", "home"):
        side_data = teams.get(side) or {}
        team = _team_from_team(side_data.get("team") or _raw_game_team(detail.raw, side))
        players = side_data.get("players") or {}
        pitchers = tuple(
            _pitcher_from_player_record(_player_record(players, pitcher_id), team, pitcher_id)
            for pitcher_id in side_data.get("pitchers") or ()
            if _player_record(players, pitcher_id)
        )
        if team.id is not None or pitchers:
            team_pitchers.append(TeamPitchers(team=team, pitchers=pitchers))
    return team_pitchers


def lineup_for_team(detail: GameDetail, team_id: int) -> TeamLineup | None:
    teams = _raw_boxscore(detail.raw).get("teams") or {}
    for side in ("away", "home"):
        side_data = teams.get(side) or {}
        team = _team_from_team(side_data.get("team") or _raw_game_team(detail.raw, side))
        if team.id != team_id:
            continue
        players = side_data.get("players") or {}
        entries: list[LineupEntry] = []
        for order, player_id in enumerate(side_data.get("battingOrder") or (), start=1):
            player = _player_record(players, player_id)
            if not player:
                continue
            person = player.get("person") or {}
            position = player.get("position") or {}
            entries.append(
                LineupEntry(
                    order=order,
                    player_id=_optional_int(person.get("id") or player_id),
                    full_name=_name(person),
                    position=position.get("abbreviation") or "",
                )
            )
        return TeamLineup(team=team, entries=tuple(entries))
    return None


def normalize_leader_category(category: str) -> str:
    compact = category.strip().replace("-", "_")
    return LEADER_ALIASES.get(compact.lower(), category)


def _raw_linescore(raw: JsonDict) -> JsonDict:
    return ((raw.get("liveData") or {}).get("linescore") or raw.get("linescore") or {})


def _raw_boxscore(raw: JsonDict) -> JsonDict:
    return ((raw.get("liveData") or {}).get("boxscore") or raw.get("boxscore") or {})


def _raw_game_team(raw: JsonDict, side: str) -> JsonDict:
    return (((raw.get("gameData") or {}).get("teams") or {}).get(side) or {})


def _player_record(players: JsonDict, player_id: int | str) -> JsonDict:
    return players.get(f"ID{player_id}") or players.get(str(player_id)) or {}


def _pitcher_record_with_team(
    detail: GameDetail, pitcher_id: int | None
) -> tuple[JsonDict, TeamInfo] | None:
    if pitcher_id is None:
        return None
    teams = _raw_boxscore(detail.raw).get("teams") or {}
    for side in ("away", "home"):
        side_data = teams.get(side) or {}
        player = _player_record(side_data.get("players") or {}, pitcher_id)
        if player:
            team = _team_from_team(side_data.get("team") or _raw_game_team(detail.raw, side))
            return player, team
    return None


def _pitcher_from_player_record(
    player: JsonDict, team: TeamInfo, fallback_player_id: int | str | None = None
) -> PitcherInfo:
    person = player.get("person") or {}
    return PitcherInfo(
        player_id=_optional_int(person.get("id") or fallback_player_id),
        full_name=_name(person),
        team=team,
        game_stats=(player.get("stats") or {}).get("pitching") or {},
    )


def _pitcher_from_person(person: JsonDict, team: TeamInfo) -> PitcherInfo:
    return PitcherInfo(
        player_id=_optional_int(person.get("id")),
        full_name=_name(person),
        team=team,
    )


def _team_from_wrapper(wrapper: JsonDict) -> TeamInfo:
    return _team_from_team(wrapper.get("team") or {})


def _team_from_team(team: JsonDict) -> TeamInfo:
    team_id = team.get("id")
    return TeamInfo(
        id=team_id,
        name=team.get("name") or TEAM_DIRECTORY.name_for_id(team_id),
        abbreviation=team.get("abbreviation") or TEAM_DIRECTORY.abbreviation_for_id(team_id),
    )


def _parse_transaction(transaction: JsonDict) -> Transaction:
    return Transaction(
        transaction_id=_optional_int(transaction.get("id")),
        date=_parse_date(transaction.get("date")),
        player_name=_name(transaction.get("person")),
        type_description=str(transaction.get("typeDesc") or ""),
        description=str(transaction.get("description") or ""),
        from_team=(
            _team_from_team(transaction["fromTeam"])
            if transaction.get("fromTeam")
            else None
        ),
        to_team=(
            _team_from_team(transaction["toTeam"])
            if transaction.get("toTeam")
            else None
        ),
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


def _best_stat_split(payload: JsonDict) -> JsonDict:
    fallback: JsonDict = {}
    for stat_group in payload.get("stats") or ():
        for split in stat_group.get("splits") or ():
            if not fallback:
                fallback = split.get("stat") or {}
            sport_id = (split.get("sport") or {}).get("id")
            if sport_id in (1, "1"):
                return split.get("stat") or {}
    return fallback


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


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
