import asyncio
import json
import re
from dataclasses import replace
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx

from mlb_irc_bot.mlb.hydrate import SCHEDULE_HYDRATE, schedule_params
from mlb_irc_bot.mlb.models import (
    GameDetail,
    GameHighlight,
    GameLogEntry,
    GameSummary,
    JsonDict,
    Leader,
    LinescoreSnapshot,
    LineupEntry,
    PitchArsenalEntry,
    PitcherInfo,
    PlayerSearchResult,
    PlayerStats,
    SavantLeaderboardRow,
    StandingTeam,
    TeamInfo,
    TeamLeaderGroup,
    TeamLineup,
    TeamPitchers,
    TeamRanking,
    TeamStats,
    TopPerformer,
    Transaction,
    WinProbability,
    WinProbabilitySummary,
    WinProbabilitySwing,
)
from mlb_irc_bot.mlb.teams import TEAM_DIRECTORY


class MLBAPIError(RuntimeError):
    pass


LEADER_GROUPS: dict[str, str] = {
    "assists": "fielding",
    "battingAverage": "hitting",
    "caughtStealing": "hitting",
    "doubles": "hitting",
    "earnedRunAverage": "pitching",
    "extraBaseHits": "hitting",
    "fieldingPercentage": "fielding",
    "hits": "hitting",
    "holds": "pitching",
    "homeRuns": "hitting",
    "inningsPitched": "pitching",
    "onBasePercentage": "hitting",
    "onBasePlusSlugging": "hitting",
    "putOuts": "fielding",
    "rangeFactorPerGame": "fielding",
    "rangeFactorPer9Inn": "fielding",
    "runs": "hitting",
    "runsBattedIn": "hitting",
    "saves": "pitching",
    "saveOpportunities": "pitching",
    "sluggingPercentage": "hitting",
    "stolenBases": "hitting",
    "stolenBasePercentage": "hitting",
    "strikeouts": "pitching",
    "strikeoutsPer9Inn": "pitching",
    "strikeoutWalkRatio": "pitching",
    "totalBases": "hitting",
    "totalBattersFaced": "pitching",
    "totalPlateAppearances": "hitting",
    "triples": "hitting",
    "walks": "hitting",
    "walksAndHitsPerInningPitched": "pitching",
    "walksPer9Inn": "pitching",
    "wins": "pitching",
}

LEADER_ALIASES: dict[str, str] = {
    "average": "battingAverage",
    "avg": "battingAverage",
    "bb": "walks",
    "era": "earnedRunAverage",
    "h": "hits",
    "hr": "homeRuns",
    "home_runs": "homeRuns",
    "homeruns": "homeRuns",
    "ip": "inningsPitched",
    "k": "strikeouts",
    "k9": "strikeoutsPer9Inn",
    "k/9": "strikeoutsPer9Inn",
    "kbb": "strikeoutWalkRatio",
    "k/bb": "strikeoutWalkRatio",
    "ks": "strikeouts",
    "obp": "onBasePercentage",
    "ops": "onBasePlusSlugging",
    "rbi": "runsBattedIn",
    "sb": "stolenBases",
    "slg": "sluggingPercentage",
    "so": "strikeouts",
    "sv": "saves",
    "tb": "totalBases",
    "whip": "walksAndHitsPerInningPitched",
    "xbh": "extraBaseHits",
}

ADVANCED_LEADERS: dict[str, tuple[str, str, str, str]] = {
    "babip": ("seasonAdvanced", "hitting", "babip", "desc"),
    "fip": ("sabermetrics", "pitching", "fip", "asc"),
    "fip-": ("sabermetrics", "pitching", "fipMinus", "asc"),
    "fipminus": ("sabermetrics", "pitching", "fipMinus", "asc"),
    "iso": ("seasonAdvanced", "hitting", "iso", "desc"),
    "ra9war": ("sabermetrics", "pitching", "ra9War", "desc"),
    "war": ("sabermetrics", "hitting", "war", "desc"),
    "woba": ("sabermetrics", "hitting", "woba", "desc"),
    "wrc+": ("sabermetrics", "hitting", "wRcPlus", "desc"),
    "wrcplus": ("sabermetrics", "hitting", "wRcPlus", "desc"),
    "xavg": ("expectedStatistics", "hitting", "avg", "desc"),
    "xfip": ("sabermetrics", "pitching", "xfip", "asc"),
    "xslg": ("expectedStatistics", "hitting", "slg", "desc"),
    "xwoba": ("expectedStatistics", "hitting", "woba", "desc"),
}

TEAM_RANKINGS: dict[str, tuple[str, str, str, str]] = {
    "avg": ("season", "hitting", "avg", "desc"),
    "era": ("season", "pitching", "era", "asc"),
    "homeruns": ("season", "hitting", "homeRuns", "desc"),
    "hr": ("season", "hitting", "homeRuns", "desc"),
    "k": ("season", "pitching", "strikeOuts", "desc"),
    "ops": ("season", "hitting", "ops", "desc"),
    "r": ("season", "hitting", "runs", "desc"),
    "runs": ("season", "hitting", "runs", "desc"),
    "sb": ("season", "hitting", "stolenBases", "desc"),
    "whip": ("season", "pitching", "whip", "asc"),
}

SITUATION_ALIASES: dict[str, tuple[str, str]] = {
    "a": ("a", "Away"),
    "ahead": ("sah", "Ahead"),
    "away": ("a", "Away"),
    "b1": ("b1", "Batting First"),
    "b2": ("b2", "Batting Second"),
    "b3": ("b3", "Batting Third"),
    "b4": ("b4", "Batting Fourth"),
    "b5": ("b5", "Batting Fifth"),
    "b6": ("b6", "Batting Sixth"),
    "b7": ("b7", "Batting Seventh"),
    "b8": ("b8", "Batting Eighth"),
    "b9": ("b9", "Batting Ninth"),
    "basesloaded": ("r123", "Bases Loaded"),
    "behind": ("sbh", "Behind"),
    "day": ("d", "Day Games"),
    "daygames": ("d", "Day Games"),
    "dh": ("pD", "Designated Hitter"),
    "firsthalf": ("h1", "First Half"),
    "grass": ("g", "Grass"),
    "loaded": ("r123", "Bases Loaded"),
    "home": ("h", "Home"),
    "interleague": ("int", "Interleague"),
    "late": ("lc", "Late / Close"),
    "lateclose": ("lc", "Late / Close"),
    "lefthandedstarter": ("vls", "vs Left Handed Starter"),
    "night": ("n", "Night Games"),
    "nightgames": ("n", "Night Games"),
    "postas": ("posas", "Post All-Star"),
    "postallstar": ("posas", "Post All-Star"),
    "preas": ("preas", "Pre All-Star"),
    "preallstar": ("preas", "Pre All-Star"),
    "reliever": ("rp", "Reliever"),
    "righthandedstarter": ("vrs", "vs Right Handed Starter"),
    "risp": ("risp", "Scoring Position"),
    "secondhalf": ("h2", "Second Half"),
    "sp": ("sp", "Starter"),
    "starter": ("sp", "Starter"),
    "tied": ("sti", "Tied"),
    "turf": ("t", "Turf"),
    "val": ("val", "vs AL"),
    "vl": ("vl", "vs Left"),
    "vlhp": ("vl", "vs Left"),
    "vnl": ("vnl", "vs NL"),
    "vr": ("vr", "vs Right"),
    "vrhp": ("vr", "vs Right"),
    "vsal": ("val", "vs AL"),
    "vsleftstarter": ("vls", "vs Left Handed Starter"),
    "vsnl": ("vnl", "vs NL"),
    "vsrightstarter": ("vrs", "vs Right Handed Starter"),
}

SAVANT_BASE_URL = "https://baseballsavant.mlb.com"
SAVANT_HOME_RUN_CATEGORY = "xhr"


class MLBStatsClient:
    def __init__(
        self,
        *,
        base_url: str = "https://statsapi.mlb.com/api",
        savant_base_url: str = SAVANT_BASE_URL,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.savant_base_url = savant_base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._home_run_detail_cache: dict[tuple[int, int, str], list[JsonDict]] = {}

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

    async def enrich_home_run_data(self, feed: JsonDict) -> None:
        """Attach Savant park counts to home run plays when the public feed has them."""
        season = _raw_game_year(feed)
        game_pk = _raw_game_pk(feed)
        if season is None or game_pk is None:
            return

        for play in _raw_all_plays(feed):
            if not _raw_is_home_run_play(play):
                continue
            play_id = _batted_ball_play_id(play)
            batter_id = _safe_int(((play.get("matchup") or {}).get("batter") or {}).get("id"))
            if not play_id or batter_id is None:
                continue
            detail = await self._home_run_detail(
                batter_id=batter_id,
                season=season,
                game_pk=game_pk,
                play_id=play_id,
            )
            if detail:
                _apply_home_run_detail(play, detail)

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

    async def get_win_probability_plays(self, game_pk: int) -> list[JsonDict]:
        payload = await self._get_json(
            f"{self.base_url}/v1/game/{game_pk}/winProbability",
            params=None,
            label=f"/v1/game/{game_pk}/winProbability",
        )
        return payload if isinstance(payload, list) else []

    async def get_win_probability_summary(
        self, game_pk: int, summary: GameSummary | None = None
    ) -> WinProbabilitySummary:
        plays = await self.get_win_probability_plays(game_pk)
        if summary is None:
            game_detail = await self.get_game_detail(game_pk)
            summary = game_detail.summary
        current = _win_probability_from_plays(summary, plays)
        if current is None:
            current = await self.get_win_probability(game_pk)
        return WinProbabilitySummary(
            current=current,
            biggest_swing=_biggest_win_probability_swing(summary, plays),
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
        games_limit: int | None = None,
    ) -> PlayerStats:
        if (start_date is None) != (end_date is None):
            raise ValueError("start_date and end_date must be supplied together")
        if games_limit is not None and (start_date or end_date):
            raise ValueError("games_limit cannot be combined with start_date/end_date")

        if games_limit is not None:
            stats = await self._get_player_stat_split(
                player.person_id,
                stat_type="lastXGames",
                group=group,
                season=season,
                extra_params={"limit": str(games_limit)},
            )
            return PlayerStats(
                player,
                group,
                season,
                stats=stats,
                games_limit=games_limit,
            )

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
        advanced = advanced_leader_config(category)
        if advanced is not None:
            stat_type, group, stat_key, order = advanced
            return await self.get_stat_rankings(
                stat_key,
                stat_type=stat_type,
                group=group,
                season=season,
                limit=limit,
                order=order,
            )
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

    async def get_stat_rankings(
        self,
        stat_key: str,
        *,
        stat_type: str,
        group: str,
        season: int,
        limit: int = 5,
        order: str = "desc",
        situation_code: str | None = None,
    ) -> list[Leader]:
        params: dict[str, Any] = {
            "stats": stat_type,
            "group": group,
            "season": season,
            "sportIds": 1,
            "playerPool": "ALL",
            "limit": limit,
            "sortStat": stat_key,
            "order": order,
        }
        if situation_code:
            params["sitCodes"] = situation_code
        payload = await self._get("/v1/stats", params=params)
        leaders: list[Leader] = []
        for split in _stats_splits(payload):
            player = split.get("player") or split.get("person") or {}
            team = split.get("team") or {}
            stat = split.get("stat") or {}
            leaders.append(
                Leader(
                    rank=str(split.get("rank") or len(leaders) + 1),
                    value=_stat_value(stat, stat_key),
                    player_name=player.get("fullName") or player.get("name") or "",
                    team_name=team.get("abbreviation") or team.get("name"),
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
        situation_code: str | None = None,
        situation_label: str | None = None,
    ) -> TeamStats:
        if team.id is None:
            raise ValueError(f"missing MLB team id for {team.abbreviation}")
        if (start_date is None) != (end_date is None):
            raise ValueError("start_date and end_date must be supplied together")
        if situation_code and (start_date or end_date):
            raise ValueError("situation splits cannot be combined with date ranges")

        params: dict[str, Any] = {
            "season": season,
            "group": group,
            "stats": "season",
            "gameType": "R",
        }
        if situation_code:
            params["stats"] = "statSplits"
            params["sitCodes"] = situation_code
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
            split_label=situation_label,
        )

    async def get_player_split_stats(
        self,
        player: PlayerSearchResult,
        *,
        group: str,
        season: int,
        situation_code: str,
        situation_label: str,
    ) -> PlayerStats:
        stats = await self._get_player_stat_split(
            player.person_id,
            stat_type="statSplits",
            group=group,
            season=season,
            extra_params={"sitCodes": situation_code},
        )
        return PlayerStats(
            player=player,
            group=group,
            season=season,
            stats=stats,
            split_label=situation_label,
        )

    async def get_player_game_log(
        self,
        player: PlayerSearchResult,
        *,
        group: str,
        season: int,
        limit: int,
    ) -> list[GameLogEntry]:
        payload = await self._get(
            f"/v1/people/{player.person_id}/stats",
            params={
                "stats": "gameLog",
                "group": group,
                "season": season,
                "sportId": 1,
                "gameType": "R",
            },
        )
        entries = [
            GameLogEntry(
                date=_parse_date(split.get("date")),
                opponent=_team_from_team(split.get("opponent") or {}),
                is_home=split.get("isHome"),
                stats=split.get("stat") or {},
            )
            for split in _stats_splits(payload)
        ]
        entries.sort(key=lambda entry: entry.date or date.min, reverse=True)
        return entries[:limit]

    async def get_player_defense(
        self,
        player: PlayerSearchResult,
        *,
        season: int,
    ) -> PlayerStats:
        for group in ("fielding", "hitting"):
            try:
                stats = await self._get_player_stat_split(
                    player.person_id,
                    stat_type="outsAboveAverage",
                    group=group,
                    season=season,
                )
            except MLBAPIError:
                continue
            if stats:
                return PlayerStats(player, "fielding", season, stats)
        return PlayerStats(player, "fielding", season, {})

    async def get_pitch_arsenal(
        self,
        player: PlayerSearchResult,
        *,
        season: int,
    ) -> list[PitchArsenalEntry]:
        payload = await self._get(
            f"/v1/people/{player.person_id}/stats",
            params={
                "stats": "pitchArsenal",
                "group": "pitching",
                "season": season,
                "sportId": 1,
                "gameType": "R",
            },
        )
        entries: list[PitchArsenalEntry] = []
        for split in _stats_splits(payload):
            stat = split.get("stat") or {}
            pitch_type = stat.get("type") or {}
            entries.append(
                PitchArsenalEntry(
                    pitch_type=(
                        pitch_type.get("description")
                        or pitch_type.get("code")
                        or str(pitch_type or "")
                    ),
                    count=_optional_int(stat.get("count")),
                    percentage=_optional_float(stat.get("percentage")),
                    average_speed=_optional_float(stat.get("averageSpeed")),
                )
            )
        return sorted(entries, key=lambda entry: entry.percentage or 0, reverse=True)

    async def get_savant_percentiles(
        self,
        player: PlayerSearchResult,
        *,
        season: int,
    ) -> SavantLeaderboardRow:
        return await self._get_savant_leaderboard_row(
            player,
            season=season,
            leaderboard="percentiles",
            path="/leaderboard/percentile-rankings",
            variable="leaderboard_data",
            params={
                "type": "batter",
                "year": season,
                "team": "",
                "sort": "xwoba",
                "sortDir": "desc",
            },
            id_keys=("player_id", "pid", "id"),
        )

    async def get_savant_expected_stats(
        self,
        player: PlayerSearchResult,
        *,
        season: int,
    ) -> SavantLeaderboardRow:
        return await self._get_savant_leaderboard_row(
            player,
            season=season,
            leaderboard="expected stats",
            path="/leaderboard/expected_statistics",
            variable="data",
            params={
                "type": "batter",
                "year": season,
                "position": "",
                "team": "",
                "min": 0,
            },
            id_keys=("entity_id", "player_id", "pid", "id"),
        )

    async def get_savant_sprint_speed(
        self,
        player: PlayerSearchResult,
        *,
        season: int,
    ) -> SavantLeaderboardRow:
        return await self._get_savant_leaderboard_row(
            player,
            season=season,
            leaderboard="sprint speed",
            path="/leaderboard/sprint_speed",
            variable="data",
            params={"year": season, "position": "", "team": "", "min": 0},
            id_keys=("runner_id", "player_id", "entity_id", "id"),
        )

    async def get_savant_bat_tracking(
        self,
        player: PlayerSearchResult,
        *,
        season: int,
    ) -> SavantLeaderboardRow:
        return await self._get_savant_leaderboard_row(
            player,
            season=season,
            leaderboard="bat tracking",
            path="/leaderboard/bat-tracking",
            variable="data",
            params={
                "gameType": "Regular",
                "minGroupSwings": 1,
                "minSwings": 1,
                "seasonEnd": season,
                "seasonStart": season,
                "type": "batter",
            },
            id_keys=("id", "savant_batter_id", "batter_id", "player_id"),
        )

    async def get_savant_run_value(
        self,
        player: PlayerSearchResult,
        *,
        season: int,
    ) -> SavantLeaderboardRow:
        return await self._get_savant_leaderboard_row(
            player,
            season=season,
            leaderboard="batting run value",
            path="/leaderboard/swing-take",
            variable="data",
            params={"year": season},
            id_keys=("player_id", "pid", "id"),
        )

    async def get_savant_fielding_run_value(
        self,
        player: PlayerSearchResult,
        *,
        season: int,
    ) -> SavantLeaderboardRow:
        return await self._get_savant_leaderboard_row(
            player,
            season=season,
            leaderboard="fielding run value",
            path="/leaderboard/fielding-run-value",
            variable="data",
            params={
                "type": "fielder",
                "seasonStart": season,
                "seasonEnd": season,
                "minInnings": 0,
            },
            id_keys=("id", "player_id", "entity_id", "pid"),
        )

    async def get_savant_baserunning_run_value(
        self,
        player: PlayerSearchResult,
        *,
        season: int,
    ) -> SavantLeaderboardRow:
        return await self._get_savant_leaderboard_row(
            player,
            season=season,
            leaderboard="baserunning run value",
            path="/leaderboard/baserunning-run-value",
            variable="data",
            params={"season": season, "type": "runner"},
            id_keys=("entity_id", "player_id", "pid", "id"),
        )

    async def get_savant_arm_strength(
        self,
        player: PlayerSearchResult,
        *,
        season: int,
    ) -> SavantLeaderboardRow:
        return await self._get_savant_leaderboard_row(
            player,
            season=season,
            leaderboard="arm strength",
            path="/leaderboard/arm-strength",
            variable="data",
            params={
                "type": "player",
                "year": season,
                "minThrows": 0,
                "pos": "",
                "team": "",
            },
            id_keys=("player_id", "fielder_id", "entity_id", "id"),
        )

    async def get_team_leaders(
        self,
        team: TeamInfo,
        *,
        categories: list[str],
        season: int,
        limit: int,
    ) -> list[TeamLeaderGroup]:
        if team.id is None:
            raise ValueError(f"missing MLB team id for {team.abbreviation}")
        normalized = [normalize_leader_category(category) for category in categories]
        payload = await self._get(
            f"/v1/teams/{team.id}/leaders",
            params={
                "leaderCategories": ",".join(normalized),
                "season": season,
                "leaderGameTypes": "R",
                "limit": limit,
            },
        )
        groups: list[TeamLeaderGroup] = []
        for group in payload.get("teamLeaders") or []:
            leaders = []
            for leader in group.get("leaders") or []:
                person = leader.get("person") or {}
                leaders.append(
                    Leader(
                        rank=str(leader.get("rank") or ""),
                        value=str(leader.get("value") or ""),
                        player_name=person.get("fullName") or person.get("name") or "",
                        team_name=team.abbreviation,
                    )
                )
            groups.append(
                TeamLeaderGroup(
                    category=str(group.get("leaderCategory") or ""),
                    leaders=tuple(leaders[:limit]),
                )
            )
        return groups

    async def get_team_rankings(
        self,
        category: str,
        *,
        season: int,
        group: str | None = None,
        limit: int = 5,
    ) -> list[TeamRanking]:
        stat_type, default_group, stat_key, order = team_ranking_config(category)
        group = group or default_group
        payload = await self._get(
            "/v1/teams/stats",
            params={
                "season": season,
                "sportIds": 1,
                "group": group,
                "stats": stat_type,
                "sortStat": stat_key,
                "order": order,
            },
        )
        rankings: list[TeamRanking] = []
        for split in _stats_splits(payload):
            stat = split.get("stat") or {}
            rankings.append(
                TeamRanking(
                    rank=str(split.get("rank") or len(rankings) + 1),
                    team=_team_from_team(split.get("team") or {}),
                    value=_stat_value(stat, stat_key),
                    stats=stat,
                )
            )
        return rankings[:limit]

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

    async def get_game_highlights(
        self,
        game_pk: int,
        *,
        limit: int | None = 3,
        tag: str | None = None,
    ) -> list[GameHighlight]:
        payload = await self._get(f"/v1/game/{game_pk}/content")
        highlights = _parse_game_highlights(payload)
        if tag and tag != "all":
            highlights = [highlight for highlight in highlights if tag in highlight.tags]
        if limit is not None:
            highlights = highlights[:limit]
        return await self._resolve_highlight_mp4_urls(highlights)

    async def resolve_video_mp4_url(self, video_url: str) -> str | None:
        """Resolve an MLB public video page to its direct MP4 URL when exposed."""
        try:
            html = await self._get_text(video_url, label=video_url)
        except MLBAPIError:
            return None
        return _extract_video_mp4_url(html)

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

    async def _home_run_detail(
        self,
        *,
        batter_id: int,
        season: int,
        game_pk: int,
        play_id: str,
    ) -> JsonDict:
        cache_key = (batter_id, season, SAVANT_HOME_RUN_CATEGORY)
        had_cached_rows = cache_key in self._home_run_detail_cache
        rows = await self._home_run_details_for_batter(
            batter_id,
            season,
            category=SAVANT_HOME_RUN_CATEGORY,
        )
        detail = _find_home_run_detail(rows, game_pk=game_pk, play_id=play_id)
        if detail or not had_cached_rows:
            return detail

        rows = await self._home_run_details_for_batter(
            batter_id,
            season,
            category=SAVANT_HOME_RUN_CATEGORY,
            refresh=True,
        )
        return _find_home_run_detail(rows, game_pk=game_pk, play_id=play_id)

    async def _home_run_details_for_batter(
        self,
        batter_id: int,
        season: int,
        *,
        category: str,
        refresh: bool = False,
    ) -> list[JsonDict]:
        cache_key = (batter_id, season, category)
        if not refresh and cache_key in self._home_run_detail_cache:
            return self._home_run_detail_cache[cache_key]

        try:
            payload = await self._get_savant(
                "/leaderboard/home-runs",
                params={
                    "type": "details",
                    "player_id": batter_id,
                    "year": season,
                    "player_type": "Batters",
                    "cat": category,
                },
            )
        except MLBAPIError:
            return []

        rows = payload if isinstance(payload, list) else []
        self._home_run_detail_cache[cache_key] = rows
        return rows

    async def _get_savant_leaderboard_row(
        self,
        player: PlayerSearchResult,
        *,
        season: int,
        leaderboard: str,
        path: str,
        variable: str,
        params: dict[str, Any],
        id_keys: tuple[str, ...],
    ) -> SavantLeaderboardRow:
        rows = await self._get_savant_embedded_rows(path, params=params, variable=variable)
        row = _find_savant_player_row(rows, player_id=player.person_id, id_keys=id_keys)
        return SavantLeaderboardRow(
            player=player,
            season=season,
            leaderboard=leaderboard,
            stats=row,
        )

    async def _get_savant_embedded_rows(
        self,
        path: str,
        *,
        params: dict[str, Any],
        variable: str,
    ) -> list[JsonDict]:
        html = await self._get_savant_text(path, params=params)
        return _extract_savant_embedded_array(html, variable=variable, label=path)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> JsonDict:
        url = f"{self.base_url}{path}"
        payload = await self._get_json(url, params=params, label=path)
        return payload if isinstance(payload, dict) else {}

    async def _get_savant(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.savant_base_url}{path}"
        return await self._get_json(url, params=params, label=path)

    async def _get_savant_text(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> str:
        url = f"{self.savant_base_url}{path}"
        return await self._get_text(url, params=params, label=path)

    async def _resolve_highlight_mp4_urls(
        self, highlights: list[GameHighlight]
    ) -> list[GameHighlight]:
        resolved: list[GameHighlight] = []
        for highlight in highlights:
            if _is_mp4_url(highlight.url) or not _is_mlb_video_url(highlight.url):
                resolved.append(highlight)
                continue
            mp4_url = await self.resolve_video_mp4_url(highlight.url)
            resolved.append(replace(highlight, url=mp4_url) if mp4_url else highlight)
        return resolved

    async def _get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None,
        label: str,
    ) -> Any:
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
        raise MLBAPIError(f"MLB API request failed for {label}: {last_error}") from last_error

    async def _get_text(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        label: str,
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = await self._client.get(url, params=params)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(0.25)
        raise MLBAPIError(f"MLB API request failed for {label}: {last_error}") from last_error

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


def top_performers(detail: GameDetail, *, limit: int = 3) -> list[TopPerformer]:
    boxscore = _raw_boxscore(detail.raw)
    performers: list[TopPerformer] = []
    for item in boxscore.get("topPerformers") or []:
        player = item.get("player") or {}
        person = player.get("person") or player
        player_id = _optional_int(person.get("id"))
        team = _team_for_player_id(boxscore, player_id)
        stats = player.get("stats") or {}
        performers.append(
            TopPerformer(
                player_name=_name(person),
                performer_type=str(item.get("type") or ""),
                game_score=_optional_int(item.get("gameScore")),
                team=team,
                batting_stats=stats.get("batting") or {},
                pitching_stats=stats.get("pitching") or {},
            )
        )
    return performers[:limit]


def normalize_leader_category(category: str) -> str:
    compact = category.strip().replace("-", "_")
    return LEADER_ALIASES.get(compact.lower(), category)


def advanced_leader_config(category: str) -> tuple[str, str, str, str] | None:
    compact = category.strip().replace("-", "").replace("_", "").lower()
    return ADVANCED_LEADERS.get(category.lower()) or ADVANCED_LEADERS.get(compact)


def team_ranking_config(category: str) -> tuple[str, str, str, str]:
    compact = category.strip().replace("-", "").replace("_", "").lower()
    normalized = LEADER_ALIASES.get(category.strip().replace("-", "_").lower(), compact)
    if compact in TEAM_RANKINGS:
        return TEAM_RANKINGS[compact]
    if normalized in TEAM_RANKINGS:
        return TEAM_RANKINGS[normalized]
    if normalized in LEADER_GROUPS:
        group = LEADER_GROUPS[normalized]
        lower_is_better = {"earnedRunAverage", "walksAndHitsPerInningPitched"}
        order = "asc" if normalized in lower_is_better else "desc"
        stat_key = {
            "earnedRunAverage": "era",
            "onBasePlusSlugging": "ops",
            "walksAndHitsPerInningPitched": "whip",
        }.get(normalized, normalized)
        return "season", group, stat_key, order
    raise ValueError(f"unknown team ranking category '{category}'")


def situation_code(value: str) -> tuple[str, str] | None:
    compact = value.strip().replace("-", "").replace("_", "").lower()
    return SITUATION_ALIASES.get(compact)


def _parse_game_highlights(payload: JsonDict) -> list[GameHighlight]:
    highlights = payload.get("highlights") or {}
    items: list[JsonDict] = []
    for bucket_name in (
        "live",
        "highlights",
        "scoreboard",
        "scoreboardPreview",
        "gameCenter",
        "milestone",
    ):
        bucket = highlights.get(bucket_name) or {}
        items.extend(bucket.get("items") or [])

    parsed: list[GameHighlight] = []
    seen_highlights: set[str] = set()
    for item in items:
        title = str(item.get("headline") or item.get("title") or item.get("blurb") or "").strip()
        if not title:
            continue
        url = _highlight_url(item)
        identity = _highlight_identity(item, url)
        if not url or identity in seen_highlights:
            continue
        seen_highlights.add(identity)
        parsed.append(
            GameHighlight(
                title=title,
                url=url,
                blurb=item.get("blurb"),
                duration=item.get("duration"),
                page_url=_highlight_page_url(item),
                tags=_highlight_tags(item),
            )
        )
    return parsed


def _highlight_url(item: JsonDict) -> str:
    return _highlight_mp4_url(item) or _highlight_page_url(item) or _first_playback_url(item)


def _highlight_mp4_url(item: JsonDict) -> str:
    candidates: list[tuple[tuple[int, int], str]] = []
    for index, playback in enumerate(item.get("playbacks") or ()):
        url = str(playback.get("url") or "")
        if not _is_mp4_url(url):
            continue
        name = str(playback.get("name") or "").lower()
        mimetype = str(playback.get("mimetype") or playback.get("mimeType") or "").lower()
        if name == "mp4avc":
            rank = 0
        elif "mp4" in name or mimetype == "video/mp4":
            rank = 1
        elif "highbit" in name:
            rank = 3
        else:
            rank = 2
        candidates.append(((rank, index), url))
    if not candidates:
        return ""
    return min(candidates, key=lambda item: item[0])[1]


def _highlight_page_url(item: JsonDict) -> str:
    slug = str(item.get("slug") or item.get("id") or "").strip("/")
    if slug:
        return f"https://www.mlb.com/video/{slug}"
    return ""


def _first_playback_url(item: JsonDict) -> str:
    for playback in item.get("playbacks") or ():
        url = str(playback.get("url") or "")
        if url.startswith("http"):
            return url
    return ""


def _highlight_identity(item: JsonDict, url: str) -> str:
    return str(item.get("slug") or item.get("id") or url).strip().lower()


def _highlight_tags(item: JsonDict) -> tuple[str, ...]:
    text = _highlight_search_text(item)
    keyword_text = _highlight_keyword_text(item)
    tags: list[str] = []

    def add(tag: str, condition: bool) -> None:
        if condition and tag not in tags:
            tags.append(tag)

    add("condensed", _contains_any(text + " " + keyword_text, ("condensed game",)))
    add("recap", _contains_any(keyword_text, ("game recap", "mlbcom_game_recap")))
    add(
        "interviews",
        _contains_any(
            text + " " + keyword_text,
            (
                "interview",
                "press conference",
                "manager postgame",
                "postgame",
                "talks",
            ),
        ),
    )
    add(
        "defense",
        _contains_any(
            text + " " + keyword_text,
            (
                "defense",
                "throws out",
                "throw out",
                "double play",
                "diving",
                "catch",
                "robs",
                "fielding",
            ),
        ),
    )
    add(
        "pitching",
        _contains_any(
            text + " " + keyword_text,
            (
                "pitching",
                "strikes out",
                "strikeout",
                "called out on strikes",
                "outing",
                "pitches",
                "save",
            ),
        ),
    )
    add("homers", _contains_any(text, ("homer", "home run", "go deep", "goes deep")))
    add(
        "scoring",
        _contains_any(
            text,
            (
                "rbi",
                "runs",
                "scores",
                "score",
                "homer",
                "home run",
                "sacrifice fly",
                "walk-off",
            ),
        ),
    )
    add(
        "data",
        _contains_any(
            text + " " + keyword_text,
            (
                "data visualization",
                "data viz",
                "bat tracking",
                "distance behind",
                "deep dive",
                "breaking down",
                "visualizing",
                "starting lineup",
                "bench availability",
                "fielding alignment",
                "bullpen availability",
            ),
        ),
    )
    if not tags:
        tags.append("highlights")
    return tuple(tags)


def _highlight_search_text(item: JsonDict) -> str:
    values = [
        item.get("headline"),
        item.get("title"),
        item.get("blurb"),
        item.get("description"),
        item.get("slug"),
        item.get("id"),
        item.get("kicker"),
    ]
    return " ".join(str(value) for value in values if value).casefold()


def _highlight_keyword_text(item: JsonDict) -> str:
    values: list[str] = []
    for key in ("keywords", "keywordsDisplay", "keywordsAll"):
        for keyword in item.get(key) or ():
            if isinstance(keyword, dict):
                values.extend(
                    str(value)
                    for value in (
                        keyword.get("displayName"),
                        keyword.get("slug"),
                        keyword.get("value"),
                    )
                    if value
                )
            elif keyword:
                values.append(str(keyword))
    return " ".join(values).casefold()


def _contains_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)


def _is_mp4_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(".mp4")


def _is_mlb_video_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.lower().endswith("mlb.com") and parsed.path.startswith("/video/")


def _extract_video_mp4_url(html: str) -> str | None:
    parser = _VideoPageParser()
    parser.feed(html)
    return parser.mp4_url


class _VideoPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.mp4_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.mp4_url is not None or tag.lower() != "meta":
            return
        values = {name.lower(): value or "" for name, value in attrs}
        key = (values.get("property") or values.get("name") or "").lower()
        if key not in {
            "og:video:secure_url",
            "og:video",
            "twitter:player:stream",
        }:
            return
        content = values.get("content") or ""
        if _is_mp4_url(content):
            self.mp4_url = content


def _raw_game_pk(raw: JsonDict) -> int | None:
    return _safe_int(
        raw.get("gamePk")
        or ((raw.get("gameData") or {}).get("game") or {}).get("pk")
        or raw.get("game_pk")
        or (raw.get("scheduleGame") or {}).get("gamePk")
    )


def _raw_game_year(raw: JsonDict) -> int | None:
    date_value = (
        ((raw.get("gameData") or {}).get("datetime") or {}).get("officialDate")
        or (raw.get("scheduleGame") or {}).get("officialDate")
    )
    if date_value:
        try:
            return _parse_date(date_value).year
        except ValueError:
            pass
    for play in _raw_all_plays(raw):
        start_time = (play.get("about") or {}).get("startTime")
        if not start_time:
            continue
        try:
            return _parse_datetime(start_time).year
        except ValueError:
            continue
    return None


def _raw_all_plays(raw: JsonDict) -> list[JsonDict]:
    if "playByPlay" in raw:
        plays = raw.get("playByPlay") or {}
    else:
        plays = ((raw.get("liveData") or {}).get("plays") or {})
    return list(plays.get("allPlays") or [])


def _raw_is_home_run_play(play: JsonDict) -> bool:
    result = play.get("result") or {}
    event = (result.get("eventType") or result.get("event") or "").lower()
    return event in {"home_run", "home run"}


def _batted_ball_play_id(play: JsonDict) -> str:
    fallback = ""
    for event in reversed(play.get("playEvents") or []):
        play_id = str(event.get("playId") or "")
        if event.get("hitData") and play_id:
            return play_id
        if play_id and not fallback:
            fallback = play_id
    return fallback


def _apply_home_run_detail(play: JsonDict, detail: JsonDict) -> None:
    data = dict(play.get("homeRunData") or {})
    parks = _safe_int(detail.get("ct"))
    if parks is not None:
        data["parks"] = parks
        data["otherParks"] = max(parks - 1, 0)

    exit_velocity = _safe_float(detail.get("exit_velocity"))
    if exit_velocity is not None:
        data["exitVelocity"] = exit_velocity
    launch_angle = _safe_float(detail.get("launch_angle"))
    if launch_angle is not None:
        data["launchAngle"] = launch_angle
    distance = _safe_float(detail.get("hr_distance"))
    if distance is not None:
        data["distance"] = distance

    if data:
        play["homeRunData"] = data


def _find_home_run_detail(rows: list[JsonDict], *, game_pk: int, play_id: str) -> JsonDict:
    for row in rows:
        if str(row.get("game_pk")) == str(game_pk) and row.get("play_id") == play_id:
            return row
    return {}


def _find_savant_player_row(
    rows: list[JsonDict],
    *,
    player_id: int,
    id_keys: tuple[str, ...],
) -> JsonDict:
    for row in rows:
        if any(_safe_int(row.get(key)) == player_id for key in id_keys):
            return row
    return {}


def _extract_savant_embedded_array(
    html: str,
    *,
    variable: str,
    label: str,
) -> list[JsonDict]:
    match = re.search(rf"(?:var|const|let)\s+{re.escape(variable)}\s*=\s*\[", html)
    if match is None:
        return []

    start = match.end() - 1
    end = _balanced_json_array_end(html, start)
    if end is None:
        raise MLBAPIError(f"MLB API request failed for {label}: malformed Savant data")

    try:
        payload = json.loads(html[start:end])
    except ValueError as exc:
        raise MLBAPIError(f"MLB API request failed for {label}: malformed Savant data") from exc
    return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []


def _balanced_json_array_end(value: str, start: int) -> int | None:
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(value[start:], start=start):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def _raw_linescore(raw: JsonDict) -> JsonDict:
    return ((raw.get("liveData") or {}).get("linescore") or raw.get("linescore") or {})


def _raw_boxscore(raw: JsonDict) -> JsonDict:
    return ((raw.get("liveData") or {}).get("boxscore") or raw.get("boxscore") or {})


def _team_for_player_id(boxscore: JsonDict, player_id: int | None) -> TeamInfo | None:
    if player_id is None:
        return None
    for side in ("away", "home"):
        side_data = ((boxscore.get("teams") or {}).get(side) or {})
        if _player_record(side_data.get("players") or {}, player_id):
            return _team_from_team(side_data.get("team") or {})
    return None


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


def _stats_splits(payload: JsonDict) -> list[JsonDict]:
    return [
        split
        for stat_group in payload.get("stats") or ()
        for split in stat_group.get("splits") or ()
    ]


def _stat_value(stat: JsonDict, key: str) -> str:
    value = stat.get(key)
    return "" if value is None else str(value)


def _win_probability_from_plays(
    summary: GameSummary, plays: list[JsonDict]
) -> WinProbability | None:
    if not plays:
        return None
    latest = plays[-1]
    away_probability = _optional_float(latest.get("awayTeamWinProbability"))
    home_probability = _optional_float(latest.get("homeTeamWinProbability"))
    if away_probability is None and home_probability is None:
        return None
    return WinProbability(
        away=summary.away,
        home=summary.home,
        away_probability=away_probability,
        home_probability=home_probability,
    )


def _biggest_win_probability_swing(
    summary: GameSummary, plays: list[JsonDict]
) -> WinProbabilitySwing | None:
    biggest: WinProbabilitySwing | None = None
    for play in plays:
        home_added = _optional_float(play.get("homeTeamWinProbabilityAdded"))
        away_added = _optional_float(play.get("awayTeamWinProbabilityAdded"))
        if home_added is None and away_added is None:
            continue
        if home_added is None and away_added is not None:
            home_added = -away_added
        if home_added is None:
            continue
        team = summary.home if home_added >= 0 else summary.away
        value = abs(home_added)
        result = play.get("result") or {}
        about = play.get("about") or {}
        swing = WinProbabilitySwing(
            team=team,
            probability_added=value,
            description=str(result.get("description") or result.get("event") or ""),
            inning=_optional_int(about.get("inning")),
            half_inning=str(about.get("halfInning") or ""),
        )
        if biggest is None or swing.probability_added > biggest.probability_added:
            biggest = swing
    return biggest


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


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
