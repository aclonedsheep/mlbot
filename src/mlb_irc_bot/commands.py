import shlex
from collections.abc import Callable
from datetime import date, datetime, timedelta
from re import fullmatch

from mlb_irc_bot import irc_format as irc
from mlb_irc_bot.config import Settings
from mlb_irc_bot.mlb.client import (
    MLBAPIError,
    MLBStatsClient,
    active_pitchers,
    current_pitcher_for_team,
    lineup_for_team,
    normalize_leader_category,
    pitchers_by_team,
    situation_code,
    top_performers,
)
from mlb_irc_bot.mlb.formatters import (
    format_boxscore,
    format_compact_schedule,
    format_current_pitcher,
    format_defense,
    format_game_detail,
    format_game_log,
    format_game_summary,
    format_leaders,
    format_lineup,
    format_pitch_arsenal,
    format_pitchers,
    format_player_candidates,
    format_player_stats,
    format_probable_pitchers,
    format_replay,
    format_standings,
    format_team_leaders,
    format_team_rankings,
    format_team_standing,
    format_team_stats,
    format_top_performers,
    format_transactions,
    format_weather,
    format_win_probability_summary,
)
from mlb_irc_bot.mlb.models import GameDetail, GameSummary, PlayerSearchResult, TeamInfo
from mlb_irc_bot.mlb.teams import TEAM_DIRECTORY, TeamDirectory, TeamRecord

DATE_WORDS = {"today", "tomorrow", "yesterday"}
STAT_GROUPS = {"hitting", "pitching", "fielding"}
STAT_WINDOW_WORDS = {"day", "days"}
GAME_WINDOW_WORDS = {"game", "games"}
MAX_STAT_WINDOW_DAYS = 60
MAX_LAST_GAMES = 30
MAX_LEADERS_LIMIT = 10
MAX_TEAM_LEADERS_LIMIT = 5
MAX_TEAM_RANKINGS_LIMIT = 10
DEFAULT_TEAM_LEADER_CATEGORIES = [
    "homeRuns",
    "runsBattedIn",
    "onBasePlusSlugging",
    "earnedRunAverage",
    "strikeouts",
    "saves",
]


class CommandRouter:
    def __init__(
        self,
        *,
        client: MLBStatsClient,
        settings: Settings,
        teams: TeamDirectory = TEAM_DIRECTORY,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.teams = teams
        self.now = now or (lambda: datetime.now(settings.zoneinfo()))

    async def handle_message(self, text: str) -> list[str] | None:
        prefix = self.settings.command_prefix
        if not text.startswith(prefix):
            return None
        try:
            parts = shlex.split(text[len(prefix) :])
        except ValueError:
            parts = text[len(prefix) :].split()
        if not parts:
            return None

        command = parts[0].lower()
        args = parts[1:]
        try:
            if command == "mlb":
                return await self._mlb(args)
            if command == "box":
                return await self._box(args)
            if command == "wp":
                return await self._wp(args)
            if command == "stars":
                return await self._stars(args)
            if command == "weather":
                return await self._weather(args)
            if command == "replay":
                return await self._replay(args)
            if command == "mlbpitcher":
                return await self._mlb_pitcher(args)
            if command == "mlbpitchers":
                return await self._mlb_pitchers(args)
            if command == "mlblineup":
                return await self._mlb_lineup(args)
            if command == "standings":
                return await self._standings(args, wildcard=False)
            if command == "wildcard":
                return await self._standings(args, wildcard=True)
            if command == "sstats":
                return await self._season_stats(args)
            if command == "gamelog":
                return await self._game_log(args)
            if command == "splits":
                return await self._splits(args)
            if command == "leaders":
                return await self._leaders(args)
            if command == "teamstats":
                return await self._team_stats(args)
            if command == "teamrank":
                return await self._team_rank(args)
            if command == "teamleaders":
                return await self._team_leaders(args)
            if command == "defense":
                return await self._defense(args)
            if command == "arsenal":
                return await self._arsenal(args)
            if command == "transactions":
                return await self._transactions(args)
            if command == "help":
                return self._help(args)
        except MLBAPIError as exc:
            return [f"{irc.error('MLB API error')}: {exc}"]
        except ValueError as exc:
            return [f"{irc.error('Command error')}: {exc}"]
        return [
            f"{irc.warning('Unknown command')}: "
            f"{irc.bold(f'{self.settings.command_prefix}{command}')}. "
            f"Try {irc.bold(f'{self.settings.command_prefix}help')}."
        ]

    async def _mlb(self, args: list[str]) -> list[str]:
        if not args:
            return await self._schedule_for_date(self._date_for("today"))

        first = args[0].lower()
        if first == "*":
            target_date = self._date_for(args[1]) if len(args) > 1 else self._date_for("today")
            games = await self.client.get_schedule(target_date)
            return format_compact_schedule(
                games,
                target_date,
                self.settings.zoneinfo(),
                live_only=True,
            )

        if first == "game" and len(args) >= 2 and args[1].isdigit():
            detail = await self.client.get_game_detail(int(args[1]))
            return format_game_detail(
                detail,
                self.settings.zoneinfo(),
                win_probability_summary=await self._try_win_probability_summary(
                    detail.summary.game_pk, detail.summary
                ),
            )

        if first in DATE_WORDS or _is_iso_date(first):
            return await self._schedule_for_date(self._date_for(first))

        team = self.teams.resolve(args[0])
        if team is None:
            return [
                f"{irc.warning('Unknown team')} '{irc.bold(args[0])}'. "
                "Try an MLB abbreviation like NYY, LAD, SEA, or BOS."
            ]

        target_date = self._date_for(args[1]) if len(args) > 1 else self._date_for("today")
        games = await self.client.get_schedule(target_date, team_id=team.team_id)
        if not games:
            return [
                f"{irc.team(team.abbreviation)}: {irc.muted('no MLB game found')} "
                f"for {irc.value(target_date.isoformat())}."
            ]
        game = games[0]
        if game.is_live:
            detail = await self.client.get_game_detail(game.game_pk)
            return format_game_detail(
                detail,
                self.settings.zoneinfo(),
                win_probability=await self._try_win_probability(game.game_pk),
                active_pitchers=active_pitchers(detail),
            )
        return [format_game_summary(game, self.settings.zoneinfo())]

    async def _schedule_for_date(self, target_date: date) -> list[str]:
        games = await self.client.get_schedule(target_date)
        return format_compact_schedule(games, target_date, self.settings.zoneinfo())

    async def _box(self, args: list[str]) -> list[str]:
        if not args:
            return [
                f"{irc.warning('Usage')}: "
                f"{irc.bold(f'{self.settings.command_prefix}box')} TEAM [today|yesterday]"
            ]
        if args[0].lower() == "game" and len(args) >= 2 and args[1].isdigit():
            detail = await self.client.get_game_detail(int(args[1]))
            return [
                format_boxscore(
                    detail,
                    pitchers_by_team(detail),
                    top_performers=top_performers(detail),
                    win_probability_summary=await self._try_win_probability_summary(
                        detail.summary.game_pk, detail.summary
                    ),
                )
            ]

        game, message_or_abbreviation = await self._game_for_team_on_date(args, "box")
        if game is None:
            return [message_or_abbreviation]
        if game.is_upcoming:
            return [
                f"{irc.team(message_or_abbreviation)}: boxscore is "
                f"{irc.muted('not available yet')} for {irc.team(game.away.abbreviation)} "
                f"vs {irc.team(game.home.abbreviation, home=True)}."
            ]
        detail = await self.client.get_game_detail(game.game_pk)
        return [
            format_boxscore(
                detail,
                pitchers_by_team(detail),
                top_performers=top_performers(detail),
                win_probability_summary=await self._try_win_probability_summary(
                    detail.summary.game_pk, detail.summary
                ),
            )
        ]

    async def _wp(self, args: list[str]) -> list[str]:
        game, message = await self._detail_game_from_args(args, "wp", allow_upcoming=False)
        if game is None:
            return [message]
        summary = await self.client.get_win_probability_summary(game.game_pk, game)
        return [format_win_probability_summary(game, summary)]

    async def _stars(self, args: list[str]) -> list[str]:
        detail, message = await self._detail_from_args(args, "stars", allow_upcoming=False)
        if detail is None:
            return [message]
        return [format_top_performers(detail.summary, top_performers(detail))]

    async def _weather(self, args: list[str]) -> list[str]:
        detail, message = await self._detail_from_args(args, "weather", allow_upcoming=True)
        if detail is None:
            return [message]
        return [format_weather(detail)]

    async def _replay(self, args: list[str]) -> list[str]:
        detail, message = await self._detail_from_args(args, "replay", allow_upcoming=False)
        if detail is None:
            return [message]
        return [format_replay(detail)]

    async def _mlb_pitcher(self, args: list[str]) -> list[str]:
        game, team_abbreviation = await self._today_game_for_team(args, "mlbpitcher")
        if game is None:
            return [team_abbreviation]
        if game.is_upcoming:
            return [format_probable_pitchers(game)]
        detail = await self.client.get_game_detail(game.game_pk)
        team = self.teams.resolve(args[0])
        pitcher = current_pitcher_for_team(detail, team.team_id)
        return [format_current_pitcher(game, team.abbreviation, pitcher)]

    async def _mlb_pitchers(self, args: list[str]) -> list[str]:
        game, message_or_abbreviation = await self._today_game_for_team(args, "mlbpitchers")
        if game is None:
            return [message_or_abbreviation]
        if game.is_upcoming:
            return [format_probable_pitchers(game)]
        detail = await self.client.get_game_detail(game.game_pk)
        return format_pitchers(pitchers_by_team(detail), game)

    async def _mlb_lineup(self, args: list[str]) -> list[str]:
        game, message_or_abbreviation = await self._today_game_for_team(args, "mlblineup")
        if game is None:
            return [message_or_abbreviation]
        detail = await self.client.get_game_detail(game.game_pk)
        team = self.teams.resolve(args[0])
        lineup = lineup_for_team(detail, team.team_id)
        return [format_lineup(lineup, game, team.abbreviation)]

    async def _standings(self, args: list[str], *, wildcard: bool) -> list[str]:
        season = self.now().year
        scope = args[0] if args else "all"
        league = _league_from_scope(scope)
        team = self.teams.resolve(scope) if not wildcard else None
        records = await self.client.get_standings(
            season=season,
            standings_type="wildCard" if wildcard else "regularSeason",
            league=league,
        )
        if team is not None:
            for record in records:
                if record.team_id == team.team_id:
                    return [format_team_standing(record)]
            return [
                f"{irc.muted('No standings record found')} for "
                f"{irc.team(team.abbreviation)}."
            ]
        if wildcard:
            title = f"{league} wildcard standings" if league else "Wildcard standings"
        else:
            title = f"{league} standings" if league else "Standings"
        return format_standings(records, title=title, wildcard=wildcard)

    async def _season_stats(self, args: list[str]) -> list[str]:
        if not args:
            return [self._sstats_usage()]
        season, requested_group, window_days, games_limit, remaining = self._parse_sstats_args(args)
        name = " ".join(remaining).strip()
        if not name:
            return [self._sstats_usage()]

        matches = await self.client.search_people(name)
        if not matches:
            return [f"{irc.muted('No player found')} for '{irc.bold(name)}'."]
        exact = [player for player in matches if player.full_name.lower() == name.lower()]
        if len(exact) == 1:
            player = exact[0]
        elif len(matches) == 1:
            player = matches[0]
        else:
            candidates = [
                (
                    f"{player.full_name} "
                    f"({player.team_name or 'no team'}, {player.position or 'unknown'})"
                )
                for player in matches[:5]
            ]
            return [format_player_candidates(candidates)]
        group = requested_group or _default_stat_group_for_position(player.position)
        end_date = start_date = None
        if window_days is not None:
            end_date = self.now().date()
            start_date = end_date - timedelta(days=window_days - 1)
        stat_kwargs = {
            "group": group,
            "season": season,
            "start_date": start_date,
            "end_date": end_date,
        }
        if games_limit is not None:
            stat_kwargs["games_limit"] = games_limit
        stats = await self.client.get_player_stats(player, **stat_kwargs)
        return [format_player_stats(stats)]

    async def _game_log(self, args: list[str]) -> list[str]:
        if not args:
            return [
                f"{irc.warning('Usage')}: "
                f"{irc.bold(f'{self.settings.command_prefix}gamelog')} "
                "<player name> [hitting|pitching] [N]"
            ]
        season, group, limit, remaining = self._parse_game_log_args(args)
        if not remaining:
            return [
                f"{irc.warning('Usage')}: "
                f"{irc.bold(f'{self.settings.command_prefix}gamelog')} "
                "<player name> [hitting|pitching] [N]"
            ]
        player_or_reply = await self._resolve_player(" ".join(remaining))
        if isinstance(player_or_reply, str):
            return [player_or_reply]
        group = group or _default_stat_group_for_position(player_or_reply.position)
        entries = await self.client.get_player_game_log(
            player_or_reply,
            group=group,
            season=season,
            limit=limit,
        )
        return [format_game_log(player_or_reply.full_name, group, entries)]

    async def _splits(self, args: list[str]) -> list[str]:
        if not args:
            return [self._splits_usage()]
        season, group, situation, remaining = self._parse_split_args(args)
        if situation is None or not remaining:
            return [self._splits_usage()]
        player_or_reply = await self._resolve_player(" ".join(remaining))
        if isinstance(player_or_reply, str):
            return [player_or_reply]
        group = group or _default_stat_group_for_position(player_or_reply.position)
        stats = await self.client.get_player_split_stats(
            player_or_reply,
            group=group,
            season=season,
            situation_code=situation[0],
            situation_label=situation[1],
        )
        return [format_player_stats(stats)]

    async def _leaders(self, args: list[str]) -> list[str]:
        if not args:
            return [
                f"{irc.warning('Usage')}: "
                f"{irc.bold(f'{self.settings.command_prefix}leaders')} <category> [limit]"
            ]
        category = normalize_leader_category(args[0])
        limit = 5
        if len(args) > 1 and args[1].isdigit():
            limit = max(1, min(int(args[1]), MAX_LEADERS_LIMIT))
        leaders = await self.client.get_leaders(category, season=self.now().year, limit=limit)
        return [format_leaders(category, leaders)]

    async def _team_stats(self, args: list[str]) -> list[str]:
        if not args:
            return [self._teamstats_usage()]
        team = self.teams.resolve(args[0])
        if team is None:
            return [
                f"{irc.warning('Unknown team')} '{irc.bold(args[0])}'. "
                "Try an MLB abbreviation like NYY or LAD."
            ]
        season, group, window_days, situation, remaining = self._parse_teamstats_args(args[1:])
        if remaining:
            return [self._teamstats_usage()]
        start_date = end_date = None
        if window_days is not None:
            end_date = self.now().date()
            start_date = end_date - timedelta(days=window_days - 1)
        groups = [group] if group else ["hitting", "pitching"]
        stats = []
        for stat_group in groups:
            stat_kwargs = {
                "group": stat_group,
                "season": season,
                "start_date": start_date,
                "end_date": end_date,
            }
            if situation:
                stat_kwargs["situation_code"] = situation[0]
                stat_kwargs["situation_label"] = situation[1]
            stats.append(await self.client.get_team_stats(_team_info(team), **stat_kwargs))
        return [format_team_stats(stats)]

    async def _team_rank(self, args: list[str]) -> list[str]:
        if not args:
            return [
                f"{irc.warning('Usage')}: "
                f"{irc.bold(f'{self.settings.command_prefix}teamrank')} "
                "<stat> [hitting|pitching] [limit]"
            ]
        category = args[0]
        remaining = args[1:]
        group = None
        limit = 5
        for token in remaining:
            lowered = token.lower()
            if lowered in {"hitting", "pitching"}:
                group = lowered
            elif token.isdigit():
                limit = max(1, min(int(token), MAX_TEAM_RANKINGS_LIMIT))
            else:
                raise ValueError("teamrank accepts <stat> [hitting|pitching] [limit].")
        rankings = await self.client.get_team_rankings(
            category,
            season=self.now().year,
            group=group,
            limit=limit,
        )
        return [format_team_rankings(category, rankings)]

    async def _team_leaders(self, args: list[str]) -> list[str]:
        if not args:
            return [
                f"{irc.warning('Usage')}: "
                f"{irc.bold(f'{self.settings.command_prefix}teamleaders')} TEAM [category] [limit]"
            ]
        team = self.teams.resolve(args[0])
        if team is None:
            return [
                f"{irc.warning('Unknown team')} '{irc.bold(args[0])}'. "
                "Try an MLB abbreviation like NYY or LAD."
            ]
        remaining = args[1:]
        limit = 3
        if remaining and remaining[-1].isdigit():
            limit = max(1, min(int(remaining.pop()), MAX_TEAM_LEADERS_LIMIT))
        categories = (
            [normalize_leader_category(remaining[0])]
            if remaining
            else DEFAULT_TEAM_LEADER_CATEGORIES
        )
        groups = await self.client.get_team_leaders(
            _team_info(team),
            categories=categories,
            season=self.now().year,
            limit=limit,
        )
        return [format_team_leaders(_team_info(team), groups)]

    async def _defense(self, args: list[str]) -> list[str]:
        if not args:
            return [
                f"{irc.warning('Usage')}: "
                f"{irc.bold(f'{self.settings.command_prefix}defense')} <player name> [season]"
            ]
        season, remaining = _pop_optional_season(list(args), self.now().year)
        player_or_reply = await self._resolve_player(" ".join(remaining))
        if isinstance(player_or_reply, str):
            return [player_or_reply]
        stats = await self.client.get_player_defense(player_or_reply, season=season)
        return [format_defense(stats)]

    async def _arsenal(self, args: list[str]) -> list[str]:
        if not args:
            return [
                f"{irc.warning('Usage')}: "
                f"{irc.bold(f'{self.settings.command_prefix}arsenal')} <player name> [season]"
            ]
        season, remaining = _pop_optional_season(list(args), self.now().year)
        player_or_reply = await self._resolve_player(" ".join(remaining))
        if isinstance(player_or_reply, str):
            return [player_or_reply]
        entries = await self.client.get_pitch_arsenal(player_or_reply, season=season)
        return [format_pitch_arsenal(player_or_reply.full_name, entries)]

    async def _transactions(self, args: list[str]) -> list[str]:
        team: TeamRecord | None = None
        remaining = list(args)
        if remaining:
            maybe_team = self.teams.resolve(remaining[0])
            if maybe_team:
                team = maybe_team
                remaining.pop(0)

        start_date, end_date = self._parse_transaction_dates(remaining)
        transactions = await self.client.get_transactions(
            start_date=start_date,
            end_date=end_date,
            team_id=team.team_id if team else None,
        )
        title = _transaction_title(team, start_date, end_date)
        return [format_transactions(transactions, title=title)]

    def _help(self, args: list[str]) -> list[str]:
        prefix = self.settings.command_prefix
        topic = args[0].lower() if args else ""
        if topic == "mlb":
            return [
                f"{irc.bold(f'{prefix}mlb')} [today|tomorrow|yesterday] | "
                f"{irc.bold(f'{prefix}mlb *')} | "
                f"{irc.bold(f'{prefix}mlb')} TEAM [today|tomorrow|yesterday] | "
                f"{irc.bold(f'{prefix}mlb game')} GAMEPK"
            ]
        if topic == "box":
            return [
                f"{irc.bold(f'{prefix}box')} TEAM [today|yesterday] or "
                f"{irc.bold(f'{prefix}box game')} GAMEPK"
            ]
        if topic in {"wp", "stars", "weather", "replay"}:
            return [
                f"{irc.bold(f'{prefix}wp')} TEAM|game GAMEPK, "
                f"{irc.bold(f'{prefix}stars')} TEAM|game GAMEPK, "
                f"{irc.bold(f'{prefix}weather')} TEAM|game GAMEPK, "
                f"{irc.bold(f'{prefix}replay')} TEAM|game GAMEPK"
            ]
        if topic in {"mlbpitcher", "mlbpitchers", "mlblineup"}:
            return [
                f"{irc.bold(f'{prefix}mlbpitcher')} TEAM, "
                f"{irc.bold(f'{prefix}mlbpitchers')} TEAM, "
                f"{irc.bold(f'{prefix}mlblineup')} TEAM"
            ]
        if topic == "standings":
            return [
                f"{irc.bold(f'{prefix}standings')} [AL|NL|TEAM] and "
                f"{irc.bold(f'{prefix}wildcard')} [AL|NL|all]"
            ]
        if topic == "sstats":
            return [
                f"{irc.bold(f'{prefix}sstats')} <player name> [hitting|pitching|fielding] "
                f"[season] [7 days|14 days|30 days|last N games]; "
                "pitchers default to pitching"
            ]
        if topic in {"gamelog", "splits"}:
            return [
                f"{irc.bold(f'{prefix}gamelog')} <player name> [hitting|pitching] [N]; "
                f"{irc.bold(f'{prefix}splits')} <player name> "
                "<risp|vl|vr|home|away|lateclose|basesloaded> [hitting|pitching]"
            ]
        if topic == "leaders":
            return [
                f"{irc.bold(f'{prefix}leaders')} <category> [limit], e.g. "
                f"{irc.bold(f'{prefix}leaders homeRuns 5')}; supports OPS, WHIP, wRC+, WAR, FIP"
            ]
        if topic == "teamstats":
            return [
                f"{irc.bold(f'{prefix}teamstats')} TEAM [hitting|pitching] [season] "
                "[7 days|14 days|30 days] [risp|vl|vr|home|away|lateclose|basesloaded]"
            ]
        if topic in {"teamrank", "teamleaders"}:
            return [
                f"{irc.bold(f'{prefix}teamrank')} <stat> [hitting|pitching] [limit]; "
                f"{irc.bold(f'{prefix}teamleaders')} TEAM [category] [limit]"
            ]
        if topic in {"defense", "arsenal"}:
            return [
                f"{irc.bold(f'{prefix}defense')} <player name> [season]; "
                f"{irc.bold(f'{prefix}arsenal')} <player name> [season]"
            ]
        if topic == "transactions":
            return [
                f"{irc.bold(f'{prefix}transactions')} "
                "[TEAM] [today|yesterday|7 days|YYYY-MM-DD]"
            ]
        return [
            f"{irc.title('Commands')}: "
            f"{irc.section('games')}: {irc.bold(f'{prefix}mlb')}, "
            f"{irc.bold(f'{prefix}mlb *')}, {irc.bold(f'{prefix}mlb TEAM')}, "
            f"{irc.bold(f'{prefix}box')}, {irc.bold(f'{prefix}wp')}, "
            f"{irc.bold(f'{prefix}stars')}, {irc.bold(f'{prefix}weather')}, "
            f"{irc.bold(f'{prefix}replay')}, {irc.bold(f'{prefix}mlbpitcher')}, "
            f"{irc.bold(f'{prefix}mlbpitchers')}, {irc.bold(f'{prefix}mlblineup')} | "
            f"{irc.section('standings')}: {irc.bold(f'{prefix}standings')}, "
            f"{irc.bold(f'{prefix}wildcard')} | "
            f"{irc.section('stats')}: {irc.bold(f'{prefix}sstats')}, "
            f"{irc.bold(f'{prefix}gamelog')}, {irc.bold(f'{prefix}splits')}, "
            f"{irc.bold(f'{prefix}teamstats')}, {irc.bold(f'{prefix}teamrank')}, "
            f"{irc.bold(f'{prefix}teamleaders')}, {irc.bold(f'{prefix}leaders')}, "
            f"{irc.bold(f'{prefix}defense')}, {irc.bold(f'{prefix}arsenal')} | "
            f"{irc.section('other')}: {irc.bold(f'{prefix}transactions')}, "
            f"{irc.bold(f'{prefix}help <command>')}"
        ]

    def _sstats_usage(self) -> str:
        return (
            f"{irc.warning('Usage')}: "
            f"{irc.bold(f'{self.settings.command_prefix}sstats')} <player name> "
            "[hitting|pitching|fielding] [season] "
            "[7 days|14 days|30 days|last N games]"
        )

    def _teamstats_usage(self) -> str:
        return (
            f"{irc.warning('Usage')}: "
            f"{irc.bold(f'{self.settings.command_prefix}teamstats')} TEAM "
            "[hitting|pitching] [season] [7 days|14 days|30 days] "
            "[risp|vl|vr|home|away|lateclose|basesloaded]"
        )

    def _splits_usage(self) -> str:
        return (
            f"{irc.warning('Usage')}: "
            f"{irc.bold(f'{self.settings.command_prefix}splits')} <player name> "
            "<risp|vl|vr|home|away|lateclose|basesloaded> "
            "[hitting|pitching] [season]"
        )

    async def _resolve_player(self, name: str) -> PlayerSearchResult | str:
        name = name.strip()
        if not name:
            return self._sstats_usage()
        matches = await self.client.search_people(name)
        if not matches:
            return f"{irc.muted('No player found')} for '{irc.bold(name)}'."
        exact = [player for player in matches if player.full_name.lower() == name.lower()]
        if len(exact) == 1:
            return exact[0]
        if len(matches) == 1:
            return matches[0]
        candidates = [
            (
                f"{player.full_name} "
                f"({player.team_name or 'no team'}, {player.position or 'unknown'})"
            )
            for player in matches[:5]
        ]
        return format_player_candidates(candidates)

    def _parse_sstats_args(
        self, args: list[str]
    ) -> tuple[int, str | None, int | None, int | None, list[str]]:
        season = self.now().year
        group: str | None = None
        window_days: int | None = None
        games_limit: int | None = None
        remaining = list(args)

        changed = True
        while changed and remaining:
            changed = False
            last = remaining[-1].lower()
            if last in STAT_GROUPS:
                group = remaining.pop().lower()
                changed = True
                continue
            if remaining[-1].isdigit() and len(remaining[-1]) == 4:
                season = int(remaining.pop())
                changed = True
                continue
            parsed_games = _pop_game_window(remaining)
            if parsed_games is not None:
                games_limit = parsed_games
                changed = True
                continue
            parsed_window = _pop_stat_window(remaining)
            if parsed_window is not None:
                window_days = parsed_window
                changed = True

        if games_limit is not None and window_days is not None:
            raise ValueError("stats accepts either a day window or a game window, not both.")
        if games_limit is not None and not 1 <= games_limit <= MAX_LAST_GAMES:
            raise ValueError(f"last-games window must be 1-{MAX_LAST_GAMES} games.")
        if window_days is not None and not 1 <= window_days <= MAX_STAT_WINDOW_DAYS:
            raise ValueError(
                f"stats time window must be 1-{MAX_STAT_WINDOW_DAYS} days."
            )
        return season, group, window_days, games_limit, remaining

    def _parse_game_log_args(
        self, args: list[str]
    ) -> tuple[int, str | None, int, list[str]]:
        season = self.now().year
        group: str | None = None
        limit = 5
        remaining = list(args)
        changed = True
        while changed and remaining:
            changed = False
            last = remaining[-1].lower()
            if last in {"hitting", "pitching"}:
                group = remaining.pop().lower()
                changed = True
                continue
            if remaining[-1].isdigit() and len(remaining[-1]) == 4:
                season = int(remaining.pop())
                changed = True
                continue
            if remaining[-1].isdigit():
                limit = max(1, min(int(remaining.pop()), 10))
                changed = True
        return season, group, limit, remaining

    def _parse_split_args(
        self, args: list[str]
    ) -> tuple[int, str | None, tuple[str, str] | None, list[str]]:
        season = self.now().year
        group: str | None = None
        situation: tuple[str, str] | None = None
        remaining = list(args)
        changed = True
        while changed and remaining:
            changed = False
            last = remaining[-1].lower()
            if last in {"hitting", "pitching"}:
                group = remaining.pop().lower()
                changed = True
                continue
            if remaining[-1].isdigit() and len(remaining[-1]) == 4:
                season = int(remaining.pop())
                changed = True
                continue
            parsed_situation = situation_code(remaining[-1])
            if parsed_situation is not None:
                situation = parsed_situation
                remaining.pop()
                changed = True
        return season, group, situation, remaining

    def _parse_teamstats_args(
        self, args: list[str]
    ) -> tuple[int, str | None, int | None, tuple[str, str] | None, list[str]]:
        season = self.now().year
        group: str | None = None
        window_days: int | None = None
        situation: tuple[str, str] | None = None
        remaining = list(args)

        changed = True
        while changed and remaining:
            changed = False
            last = remaining[-1].lower()
            if last in {"hitting", "pitching"}:
                group = remaining.pop().lower()
                changed = True
                continue
            if remaining[-1].isdigit() and len(remaining[-1]) == 4:
                season = int(remaining.pop())
                changed = True
                continue
            parsed_situation = situation_code(remaining[-1])
            if parsed_situation is not None:
                situation = parsed_situation
                remaining.pop()
                changed = True
                continue
            parsed_window = _pop_stat_window(remaining)
            if parsed_window is not None:
                window_days = parsed_window
                changed = True

        if situation is not None and window_days is not None:
            raise ValueError(
                "team stats accepts either a situation split or a day window, not both."
            )
        if window_days is not None and not 1 <= window_days <= MAX_STAT_WINDOW_DAYS:
            raise ValueError(
                f"team stats time window must be 1-{MAX_STAT_WINDOW_DAYS} days."
            )
        return season, group, window_days, situation, remaining

    def _parse_transaction_dates(self, args: list[str]) -> tuple[date, date]:
        remaining = list(args)
        window_days = _pop_stat_window(remaining)
        if window_days is not None:
            if remaining:
                raise ValueError("transactions accepts one date or one day window.")
            if not 1 <= window_days <= MAX_STAT_WINDOW_DAYS:
                raise ValueError(
                    f"transactions time window must be 1-{MAX_STAT_WINDOW_DAYS} days."
                )
            end_date = self.now().date()
            return end_date - timedelta(days=window_days - 1), end_date
        if not remaining:
            today = self.now().date()
            return today, today
        if len(remaining) == 1:
            target_date = self._date_for(remaining[0])
            return target_date, target_date
        raise ValueError("transactions accepts [TEAM] [today|yesterday|7 days|YYYY-MM-DD].")

    def _date_for(self, value: str) -> date:
        today = self.now().date()
        value = value.lower()
        if value == "today":
            return today
        if value == "tomorrow":
            return today + timedelta(days=1)
        if value == "yesterday":
            return today - timedelta(days=1)
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"unknown date '{value}'. Use today, tomorrow, yesterday, or YYYY-MM-DD."
            ) from exc

    async def _today_game_for_team(
        self, args: list[str], command_name: str
    ) -> tuple[GameSummary | None, str]:
        if not args:
            return (
                None,
                f"{irc.warning('Usage')}: "
                f"{irc.bold(f'{self.settings.command_prefix}{command_name}')} TEAM",
            )
        team = self.teams.resolve(args[0])
        if team is None:
            return (
                None,
                f"{irc.warning('Unknown team')} '{irc.bold(args[0])}'. "
                "Try an MLB abbreviation like NYY or LAD.",
            )
        target_date = self._date_for("today")
        games = await self.client.get_schedule(target_date, team_id=team.team_id)
        if not games:
            return (
                None,
                f"{irc.team(team.abbreviation)}: {irc.muted('no MLB game found')} "
                f"for {irc.value(target_date.isoformat())}.",
            )
        return games[0], team.abbreviation

    async def _game_for_team_on_date(
        self, args: list[str], command_name: str
    ) -> tuple[GameSummary | None, str]:
        if not args:
            return (
                None,
                f"{irc.warning('Usage')}: "
                f"{irc.bold(f'{self.settings.command_prefix}{command_name}')} TEAM",
            )
        team = self.teams.resolve(args[0])
        if team is None:
            return (
                None,
                f"{irc.warning('Unknown team')} '{irc.bold(args[0])}'. "
                "Try an MLB abbreviation like NYY or LAD.",
            )
        target_date = self._date_for(args[1]) if len(args) > 1 else self._date_for("today")
        games = await self.client.get_schedule(target_date, team_id=team.team_id)
        if not games:
            return (
                None,
                f"{irc.team(team.abbreviation)}: {irc.muted('no MLB game found')} "
                f"for {irc.value(target_date.isoformat())}.",
            )
        return games[0], team.abbreviation

    async def _detail_game_from_args(
        self,
        args: list[str],
        command_name: str,
        *,
        allow_upcoming: bool,
    ) -> tuple[GameSummary | None, str]:
        if not args:
            return (
                None,
                f"{irc.warning('Usage')}: "
                f"{irc.bold(f'{self.settings.command_prefix}{command_name}')} "
                "TEAM [today|yesterday] or "
                f"{irc.bold(f'{self.settings.command_prefix}{command_name} game')} GAMEPK",
            )
        if args[0].lower() == "game" and len(args) >= 2 and args[1].isdigit():
            detail = await self.client.get_game_detail(int(args[1]))
            if detail.summary.is_upcoming and not allow_upcoming:
                return (
                    None,
                    f"{irc.team(detail.summary.away.abbreviation)} vs "
                    f"{irc.team(detail.summary.home.abbreviation, home=True)}: "
                    f"{irc.muted('not available before first pitch')}.",
                )
            return detail.summary, ""
        game, message = await self._game_for_team_on_date(args, command_name)
        if game is None:
            return None, message
        if game.is_upcoming and not allow_upcoming:
            return (
                None,
                f"{irc.team(message)}: {command_name} is "
                f"{irc.muted('not available before first pitch')} for "
                f"{irc.team(game.away.abbreviation)} vs "
                f"{irc.team(game.home.abbreviation, home=True)}.",
            )
        return game, message

    async def _detail_from_args(
        self,
        args: list[str],
        command_name: str,
        *,
        allow_upcoming: bool,
    ) -> tuple[GameDetail | None, str]:
        if args and args[0].lower() == "game" and len(args) >= 2 and args[1].isdigit():
            detail = await self.client.get_game_detail(int(args[1]))
            if detail.summary.is_upcoming and not allow_upcoming:
                return (
                    None,
                    f"{irc.team(detail.summary.away.abbreviation)} vs "
                    f"{irc.team(detail.summary.home.abbreviation, home=True)}: "
                    f"{irc.muted('not available before first pitch')}.",
                )
            return detail, ""
        game, message = await self._detail_game_from_args(
            args,
            command_name,
            allow_upcoming=allow_upcoming,
        )
        if game is None:
            return None, message
        return await self.client.get_game_detail(game.game_pk), ""

    async def _try_win_probability(self, game_pk: int):
        try:
            return await self.client.get_win_probability(game_pk)
        except MLBAPIError:
            return None

    async def _try_win_probability_summary(self, game_pk: int, game: GameSummary):
        try:
            return await self.client.get_win_probability_summary(game_pk, game)
        except (AttributeError, MLBAPIError):
            return None


def _league_from_scope(scope: str) -> str | None:
    upper = scope.upper()
    if upper in {"AL", "AMERICAN"}:
        return "AL"
    if upper in {"NL", "NATIONAL"}:
        return "NL"
    return None


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _pop_stat_window(args: list[str]) -> int | None:
    if not args:
        return None
    last = args[-1].lower()
    match = fullmatch(r"(\d+)(?:d|days?)", last)
    if match:
        args.pop()
        return int(match.group(1))
    if len(args) >= 2 and last in STAT_WINDOW_WORDS and args[-2].isdigit():
        days = int(args[-2])
        del args[-2:]
        if args and args[-1].lower() == "last":
            args.pop()
        return days
    return None


def _pop_game_window(args: list[str]) -> int | None:
    if not args:
        return None
    last = args[-1].lower()
    match = fullmatch(r"(\d+)(?:g|games?)", last)
    if match:
        args.pop()
        return int(match.group(1))
    if len(args) >= 2 and last in GAME_WINDOW_WORDS and args[-2].isdigit():
        games = int(args[-2])
        del args[-2:]
        if args and args[-1].lower() == "last":
            args.pop()
        return games
    return None


def _pop_optional_season(args: list[str], default: int) -> tuple[int, list[str]]:
    if args and args[-1].isdigit() and len(args[-1]) == 4:
        return int(args.pop()), args
    return default, args


def _default_stat_group_for_position(position: str | None) -> str:
    normalized = (position or "").strip().lower()
    if normalized in {"p", "sp", "rp", "lhp", "rhp", "pitcher"}:
        return "pitching"
    if "pitcher" in normalized:
        return "pitching"
    return "hitting"


def _team_info(team: TeamRecord) -> TeamInfo:
    return TeamInfo(id=team.team_id, name=team.name, abbreviation=team.abbreviation)


def _transaction_title(
    team: TeamRecord | None, start_date: date, end_date: date
) -> str:
    scope = team.abbreviation if team else "MLB"
    if start_date == end_date:
        return f"{scope} transactions {start_date.isoformat()}"
    return f"{scope} transactions {start_date.isoformat()}..{end_date.isoformat()}"
