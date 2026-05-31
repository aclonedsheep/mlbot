import shlex
from collections.abc import Callable
from datetime import date, datetime, timedelta

from mlb_irc_bot.config import Settings
from mlb_irc_bot.mlb.client import MLBAPIError, MLBStatsClient, normalize_leader_category
from mlb_irc_bot.mlb.formatters import (
    format_game_detail,
    format_game_summary,
    format_leaders,
    format_player_candidates,
    format_player_stats,
    format_schedule,
    format_standings,
    format_team_standing,
)
from mlb_irc_bot.mlb.teams import TEAM_DIRECTORY, TeamDirectory

DATE_WORDS = {"today", "tomorrow", "yesterday"}
STAT_GROUPS = {"hitting", "pitching", "fielding"}


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
        return [f"Unknown command: {self.settings.command_prefix}{command}. Try {self.settings.command_prefix}help."]

    async def _mlb(self, args: list[str]) -> list[str]:
        if not args:
            return await self._schedule_for_date(self._date_for("today"))

        first = args[0].lower()
        if first == "game" and len(args) >= 2 and args[1].isdigit():
            detail = await self.client.get_game_detail(int(args[1]))
            return format_game_detail(detail, self.settings.zoneinfo())

        if first in DATE_WORDS or _is_iso_date(first):
            return await self._schedule_for_date(self._date_for(first))

        team = self.teams.resolve(args[0])
        if team is None:
            return [f"Unknown team '{args[0]}'. Try an MLB abbreviation like NYY, LAD, SEA, or BOS."]

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
        return format_schedule(games, target_date, self.settings.zoneinfo())

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
        title = ("Wildcard" if wildcard else "Standings") + (
            f" {league}" if league else ""
        )
        return format_standings(records, title=title, wildcard=wildcard)

    async def _season_stats(self, args: list[str]) -> list[str]:
        if not args:
            return [f"Usage: {self.settings.command_prefix}sstats <player name> [hitting|pitching|fielding] [season]"]
        season = self.now().year
        group = "hitting"
        remaining = list(args)
        if remaining and remaining[-1].isdigit() and len(remaining[-1]) == 4:
            season = int(remaining.pop())
        if remaining and remaining[-1].lower() in STAT_GROUPS:
            group = remaining.pop().lower()
        name = " ".join(remaining).strip()
        if not name:
            return [f"Usage: {self.settings.command_prefix}sstats <player name> [hitting|pitching|fielding] [season]"]

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
                f"{player.full_name} ({player.team_name or 'no team'}, {player.position or 'unknown'})"
                for player in matches[:5]
            ]
            return [format_player_candidates(candidates)]
        stats = await self.client.get_player_stats(player, group=group, season=season)
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
                f"{prefix}mlb [today|tomorrow|yesterday] | {prefix}mlb TEAM [today|tomorrow|yesterday] | {prefix}mlb game GAMEPK"
            ]
        if topic == "standings":
            return [f"{prefix}standings [AL|NL|TEAM] and {prefix}wildcard [AL|NL|all]"]
        if topic == "sstats":
            return [f"{prefix}sstats <player name> [hitting|pitching|fielding] [season]"]
        if topic == "leaders":
            return [f"{prefix}leaders <category> [limit], e.g. {prefix}leaders homeRuns 5"]
        return [
            "Commands: "
            f"{prefix}mlb, {prefix}mlb TEAM, {prefix}mlb tomorrow, {prefix}standings, "
            f"{prefix}wildcard, {prefix}sstats, {prefix}leaders, {prefix}help <command>"
        ]

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
            raise ValueError(f"unknown date '{value}'. Use today, tomorrow, yesterday, or YYYY-MM-DD.") from exc


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
