from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from mlb_irc_bot.mlb.models import GameDetail, GameSummary, TeamInfo
from mlb_irc_bot.scheduler import LiveScheduler


@pytest.mark.asyncio
async def test_scheduler_sends_game_info_for_near_start_games() -> None:
    game = _game_summary()
    client = FakeClient(game)
    store = FakeStore()
    sent_messages: list[str] = []
    scheduler = LiveScheduler(
        client=client,
        store=store,
        settings=settings(),
        send_alert=_capture(sent_messages),
    )

    await scheduler.poll_once()

    assert client.detail_calls == [game.game_pk]
    assert len(sent_messages) == 1
    assert "Game info" in sent_messages[0]
    assert "TOR" in sent_messages[0]
    assert "BAL" in sent_messages[0]
    assert store.sent_keys == ["123:game_info"]


@pytest.mark.asyncio
async def test_scheduler_skips_upcoming_games_that_are_not_near_start() -> None:
    game = _game_summary(game_date=datetime.now(UTC) + timedelta(hours=6))
    client = FakeClient(game)
    sent_messages: list[str] = []
    scheduler = LiveScheduler(
        client=client,
        store=FakeStore(),
        settings=settings(),
        send_alert=_capture(sent_messages),
    )

    await scheduler.poll_once()

    assert client.detail_calls == []
    assert sent_messages == []


@pytest.mark.asyncio
async def test_scheduler_throttles_near_start_detail_polls() -> None:
    game = _game_summary()
    client = FakeClient(game)
    sent_messages: list[str] = []
    scheduler = LiveScheduler(
        client=client,
        store=FakeStore(),
        settings=settings(),
        send_alert=_capture(sent_messages),
    )

    await scheduler.poll_once()
    await scheduler.poll_once()

    assert client.detail_calls == [game.game_pk]


class FakeClient:
    def __init__(self, game: GameSummary) -> None:
        self.game = game
        self.detail_calls: list[int] = []

    async def get_schedule(self, _target_date):
        return [self.game]

    async def get_game_detail(self, game_pk: int) -> GameDetail:
        self.detail_calls.append(game_pk)
        return GameDetail(
            summary=self.game,
            raw={
                "gamePk": game_pk,
                "gameData": {
                    "game": {"pk": game_pk},
                    "teams": {
                        "away": {"id": 141, "abbreviation": "TOR"},
                        "home": {"id": 110, "abbreviation": "BAL"},
                    },
                    "weather": {"condition": "Sunny", "temp": "82", "wind": "3 mph, L To R"},
                    "gameInfo": {"firstPitch": "2026-06-06T18:12:00.000Z"},
                },
            },
        )

    async def enrich_home_run_data(self, _feed) -> None:
        return None

    async def get_win_probability_plays(self, _game_pk: int):
        return []


class FakeStore:
    def __init__(self) -> None:
        self.sent_keys: list[str] = []

    async def seen(self, alert_key: str) -> bool:
        return alert_key in self.sent_keys

    async def mark_sent(
        self,
        *,
        alert_key: str,
        alert_type: str,
        game_pk: int | None,
        message: str,
    ) -> None:
        self.sent_keys.append(alert_key)


def _capture(messages: list[str]):
    async def send_alert(message: str) -> None:
        messages.append(message)

    return send_alert


def settings() -> SimpleNamespace:
    return SimpleNamespace(
        zoneinfo=lambda: ZoneInfo("UTC"),
        schedule_poll_seconds=300,
        active_game_poll_seconds=15,
        near_start_poll_seconds=60,
        alert_hard_hit_threshold_mph=110.0,
        alert_win_probability_threshold=15.0,
        alert_high_leverage_threshold=2.5,
        enable_alert_home_runs=True,
        enable_alert_scoring=True,
        enable_alert_bases_loaded=True,
        enable_alert_finals=True,
        enable_alert_no_hitter=True,
        enable_alert_immaculate=True,
        enable_alert_cycle=True,
        enable_alert_win_probability=True,
        enable_alert_high_leverage=True,
        enable_alert_hard_hit=True,
        enable_alert_barrel=True,
        enable_alert_late_threat=True,
        enable_alert_weather=True,
    )


def _game_summary(game_date: datetime | None = None) -> GameSummary:
    game_date = game_date or datetime.now(UTC) + timedelta(minutes=30)
    return GameSummary(
        game_pk=123,
        game_date=game_date,
        official_date=game_date.date(),
        status="Preview",
        abstract_state="Preview",
        detailed_state="Scheduled",
        away=TeamInfo(id=141, name="Toronto Blue Jays", abbreviation="TOR"),
        home=TeamInfo(id=110, name="Baltimore Orioles", abbreviation="BAL"),
    )
