import shlex
from collections.abc import Callable
from datetime import date, datetime, timedelta
from re import fullmatch

from mlb_irc_bot.config import Settings
from mlb_irc_bot.mlb.client import (
    MLBAPIError,
    MLBStatsClient,
    current_pitcher_for_team,
    lineup_for_team,
    normalize_leader_category,
    pitchers_by_team,
)
from mlb_irc_bot.mlb.formatters import (
    format_compact_schedule,
    format_current_pitcher,
    format_game_detail,
    format_game_summary,
    format_leaders,
    format_lineup,
    format_pitchers,
    format_player_candidates,
    format_player_stats,
    format_probable_pitchers,
    format_standings,
    format_team_standing,
)
from mlb_irc_bot.mlb.models import GameSummary
from mlb_irc_bot.mlb.teams import TEAM_DIRECTORY, TeamDirectory

DATE_WORDS = {"today", "tomorrow", "yesterday"}
STAT_GROUPS = {"hitting", "pitching", "fielding"}
STAT_WINDOW_WORDS = {"day", "days"}
MAX_STAT_WINDOW_DAYS = 60


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
            if command == "leaders":
                return await self._leaders(args)
            if command == "help":
                return self._help(args)
        except MLBAPIError as exc:
            return [f"MLB API error: {exc}"]
        except ValueError as exc:
            return [f"Command error: {exc}"]
        return [
            f"Unknown command: {self.settings.command_prefix}{command}. "
            f"Try {self.settings.command_prefix}help."
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
            return format_game_detail(detail, self.settings.zoneinfo())

        if first in DATE_WORDS or _is_iso_date(first):
            return await self._schedule_for_date(self._date_for(first))

        team = self.teams.resolve(args[0])
        if team is None:
            return [
                f"Unknown team '{args[0]}'. "
                "Try an MLB abbreviation like NYY, LAD, SEA, or BOS."
            ]

        target_date = self._date_for(args[1]) if len(args) > 1 else self._date_for("today")
        games = await self.client.get_schedule(target_date, team_id=team.team_id)
        if not games:
            return [f"{team.abbreviation}: no MLB game found for {target_date.isoformat()}."]
        game = games[0]
        if game.is_live:
            detail = await self.client.get_game_detail(game.game_pk)
            return format_game_detail(detail, self.settings.zoneinfo())
        return [format_game_summary(game, self.settings.zoneinfo())]

    async def _schedule_for_date(self, target_date: date) -> list[str]:
        games = await self.client.get_schedule(target_date)
        return format_compact_schedule(games, target_date, self.settings.zoneinfo())

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
            return [f"No standings record found for {team.abbreviation}."]
        if wildcard:
            title = f"{league} wildcard standings" if league else "Wildcard standings"
        else:
            title = f"{league} standings" if league else "Standings"
        return format_standings(records, title=title, wildcard=wildcard)

    async def _season_stats(self, args: list[str]) -> list[str]:
        if not args:
            return [self._sstats_usage()]
        season, group, window_days, remaining = self._parse_sstats_args(args)
        name = " ".join(remaining).strip()
        if not name:
            return [self._sstats_usage()]

        matches = await self.client.search_people(name)
        if not matches:
            return [f"No player found for '{name}'."]
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
        end_date = start_date = None
        if window_days is not None:
            end_date = self.now().date()
            start_date = end_date - timedelta(days=window_days - 1)
        stats = await self.client.get_player_stats(
            player,
            group=group,
            season=season,
            start_date=start_date,
            end_date=end_date,
        )
        return [format_player_stats(stats)]

    async def _leaders(self, args: list[str]) -> list[str]:
        if not args:
            return [f"Usage: {self.settings.command_prefix}leaders <category> [limit]"]
        category = normalize_leader_category(args[0])
        limit = 5
        if len(args) > 1 and args[1].isdigit():
            limit = max(1, min(int(args[1]), 10))
        leaders = await self.client.get_leaders(category, season=self.now().year, limit=limit)
        return [format_leaders(category, leaders)]

    def _help(self, args: list[str]) -> list[str]:
        prefix = self.settings.command_prefix
        topic = args[0].lower() if args else ""
        if topic == "mlb":
            return [
                f"{prefix}mlb [today|tomorrow|yesterday] | "
                f"{prefix}mlb * | "
                f"{prefix}mlb TEAM [today|tomorrow|yesterday] | "
                f"{prefix}mlb game GAMEPK"
            ]
        if topic in {"mlbpitcher", "mlbpitchers", "mlblineup"}:
            return [
                f"{prefix}mlbpitcher TEAM, {prefix}mlbpitchers TEAM, "
                f"{prefix}mlblineup TEAM"
            ]
        if topic == "standings":
            return [f"{prefix}standings [AL|NL|TEAM] and {prefix}wildcard [AL|NL|all]"]
        if topic == "sstats":
            return [
                f"{prefix}sstats <player name> [hitting|pitching|fielding] "
                f"[season] [7 days|14 days|30 days]"
            ]
        if topic == "leaders":
            return [f"{prefix}leaders <category> [limit], e.g. {prefix}leaders homeRuns 5"]
        return [
            "Commands: "
            f"{prefix}mlb, {prefix}mlb TEAM, {prefix}mlb tomorrow, {prefix}standings, "
            f"{prefix}wildcard, {prefix}mlbpitcher, {prefix}mlbpitchers, "
            f"{prefix}mlblineup, {prefix}sstats, {prefix}leaders, {prefix}help <command>"
        ]

    def _sstats_usage(self) -> str:
        return (
            f"Usage: {self.settings.command_prefix}sstats <player name> "
            "[hitting|pitching|fielding] [season] [7 days|14 days|30 days]"
        )

    def _parse_sstats_args(self, args: list[str]) -> tuple[int, str, int | None, list[str]]:
        season = self.now().year
        group = "hitting"
        window_days: int | None = None
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
            parsed_window = _pop_stat_window(remaining)
            if parsed_window is not None:
                window_days = parsed_window
                changed = True

        if window_days is not None and not 1 <= window_days <= MAX_STAT_WINDOW_DAYS:
            raise ValueError(
                f"stats time window must be 1-{MAX_STAT_WINDOW_DAYS} days."
            )
        return season, group, window_days, remaining

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
            return None, f"Usage: {self.settings.command_prefix}{command_name} TEAM"
        team = self.teams.resolve(args[0])
        if team is None:
            return None, f"Unknown team '{args[0]}'. Try an MLB abbreviation like NYY or LAD."
        target_date = self._date_for("today")
        games = await self.client.get_schedule(target_date, team_id=team.team_id)
        if not games:
            return None, f"{team.abbreviation}: no MLB game found for {target_date.isoformat()}."
        return games[0], team.abbreviation


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
        return days
    return None
