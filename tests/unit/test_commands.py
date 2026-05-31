from datetime import UTC, date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from mlb_irc_bot.commands import CommandRouter
from mlb_irc_bot.mlb.models import (
    GameSummary,
    Leader,
    PlayerSearchResult,
    PlayerStats,
    StandingTeam,
    TeamInfo,
)


class FakeClient:
    def __init__(self) -> None:
        self.schedule_calls = []
        self.standings_calls = []
        self.leader_calls = []

    async def get_schedule(
        self, target_date: date, team_id: int | None = None
    ) -> list[GameSummary]:
        self.schedule_calls.append((target_date, team_id))
        return [
            GameSummary(
                game_pk=123,
                game_date=datetime(2026, 6, 1, 23, 5, tzinfo=UTC),
                official_date=target_date,
                status="Preview",
                abstract_state="Preview",
                detailed_state="Scheduled",
                away=TeamInfo(id=119, name="Los Angeles Dodgers", abbreviation="LAD"),
                home=TeamInfo(id=147, name="New York Yankees", abbreviation="NYY"),
                venue="Yankee Stadium",
                away_probable_pitcher="Dodger Arm",
                home_probable_pitcher="Yankee Arm",
            )
        ]

    async def get_game_detail(self, game_pk: int):  # pragma: no cover - not used here
        raise AssertionError(f"unexpected live detail lookup {game_pk}")

    async def get_standings(self, *, season: int, standings_type: str, league: str | None):
        self.standings_calls.append((season, standings_type, league))
        return [
            StandingTeam(
                team_id=147,
                team_name="New York Yankees",
                abbreviation="NYY",
                league_name="American League",
                division_name="AL East",
                wins=34,
                losses=20,
                pct=".630",
                games_back="-",
                wild_card_games_back="+2.0",
                division_rank="1",
                league_rank="1",
                wild_card_rank="1",
                streak="W2",
                last_ten="7-3",
            )
        ]

    async def search_people(self, name: str):
        return [
            PlayerSearchResult(1, "John Smith", "A Team", "P", True),
            PlayerSearchResult(2, "John Smith Jr.", "B Team", "CF", True),
        ]

    async def get_player_stats(self, player: PlayerSearchResult, *, group: str, season: int):
        return PlayerStats(player, group, season, {"avg": ".300", "homeRuns": 12, "rbi": 40})

    async def get_leaders(self, category: str, *, season: int, limit: int):
        self.leader_calls.append((category, season, limit))
        return [Leader(rank="1", value="20", player_name="Slugger", team_name="Club")]


def settings() -> SimpleNamespace:
    return SimpleNamespace(command_prefix="@", zoneinfo=lambda: ZoneInfo("America/New_York"))


def fixed_now() -> datetime:
    return datetime(2026, 5, 31, 10, 0, tzinfo=ZoneInfo("America/New_York"))


@pytest.mark.asyncio
async def test_mlb_tomorrow_uses_next_day_schedule() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlb tomorrow")

    assert client.schedule_calls == [(date(2026, 6, 1), None)]
    assert replies[0] == "MLB 2026-06-01: 1 game(s)"
    assert "LAD @ NYY" in replies[1]


@pytest.mark.asyncio
async def test_mlb_team_tomorrow_uses_team_id() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlb NYY tomorrow")

    assert client.schedule_calls == [(date(2026, 6, 1), 147)]
    assert replies == [
        "LAD @ NYY: 7:05 PM EDT at Yankee Stadium (probables: Dodger Arm vs Yankee Arm)"
    ]


@pytest.mark.asyncio
async def test_wildcard_command_requests_wildcard_standings() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@wildcard AL")

    assert client.standings_calls == [(2026, "wildCard", "AL")]
    assert replies[0] == "Wildcard AL"
    assert "NYY 34-20" in replies[1]


@pytest.mark.asyncio
async def test_sstats_returns_candidates_for_ambiguous_player() -> None:
    router = CommandRouter(client=FakeClient(), settings=settings(), now=fixed_now)

    replies = await router.handle_message("@sstats John")

    assert replies == [
        "Multiple players matched: John Smith (A Team, P); John Smith Jr. (B Team, CF)"
    ]


@pytest.mark.asyncio
async def test_leaders_normalizes_category_alias() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@leaders hr 3")

    assert client.leader_calls == [("homeRuns", 2026, 3)]
    assert replies == ["homeRuns leaders: 1. Slugger 20 (Club)"]
