import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from mlb_irc_bot.irc_format import strip_irc_formatting
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


@pytest.mark.asyncio
async def test_scheduler_run_forever_survives_poll_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    game = _game_summary()
    scheduler = LiveScheduler(
        client=FakeClient(game),
        store=FakeStore(),
        settings=settings(),
        send_alert=_capture([]),
    )
    poll_calls = 0

    async def fake_poll_once() -> None:
        nonlocal poll_calls
        poll_calls += 1
        if poll_calls == 1:
            raise RuntimeError("temporary scheduler failure")
        raise asyncio.CancelledError()

    async def fake_sleep(_seconds: float) -> None:
        return None

    scheduler.poll_once = fake_poll_once  # type: ignore[method-assign]
    monkeypatch.setattr("mlb_irc_bot.scheduler.asyncio.sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await scheduler.run_forever()

    assert poll_calls == 2


@pytest.mark.asyncio
async def test_scheduler_send_failure_does_not_stop_remaining_alerts() -> None:
    first_game = _game_summary(game_pk=123)
    second_game = _game_summary(game_pk=456)
    client = FakeClient(first_game, second_game)
    store = FakeStore()
    send_attempts = 0

    async def send_alert(_message: str) -> None:
        nonlocal send_attempts
        send_attempts += 1
        if send_attempts == 1:
            raise RuntimeError("temporary IRC send failure")

    scheduler = LiveScheduler(
        client=client,
        store=store,
        settings=settings(),
        send_alert=send_alert,
    )

    await scheduler.poll_once()

    assert client.detail_calls == [123, 456]
    assert send_attempts == 2
    assert store.sent_keys == ["456:game_info"]


@pytest.mark.asyncio
async def test_scheduler_sends_one_consolidated_message_for_overlapping_play_alerts() -> None:
    game = _game_summary()
    raw = {
        "gamePk": game.game_pk,
        "gameData": {
            "game": {"pk": game.game_pk},
            "teams": {
                "away": {"id": 141, "abbreviation": "TOR"},
                "home": {"id": 110, "abbreviation": "BAL"},
            },
        },
        "liveData": {
            "plays": {
                "scoringPlays": [1],
                "allPlays": [
                    {
                        "about": {"atBatIndex": 30, "inning": 7, "halfInning": "bottom"},
                        "result": {
                            "event": "Single",
                            "description": "Baltimore takes the lead.",
                            "awayScore": 0,
                            "homeScore": 1,
                        },
                    },
                    {
                        "about": {"atBatIndex": 31, "inning": 8, "halfInning": "top"},
                        "result": {
                            "event": "Double",
                            "eventType": "double",
                            "description": "Bo Bichette doubles.",
                            "awayScore": 2,
                            "homeScore": 1,
                        },
                        "matchup": {"batter": {"fullName": "Bo Bichette"}},
                        "playEvents": [
                            {
                                "playId": "bbe-1",
                                "hitData": {
                                    "launchSpeed": 111.2,
                                    "launchAngle": 24.0,
                                    "totalDistance": 390.0,
                                },
                            }
                        ],
                    },
                ],
            },
        },
    }
    win_probability_plays = [
        {
            "homeTeamWinProbabilityAdded": -18.4,
            "leverageIndex": 3.2,
            "about": {"atBatIndex": 31, "inning": 8, "halfInning": "top"},
            "matchup": {"batter": {"fullName": "Bo Bichette"}},
            "result": {"description": "Bo Bichette doubles."},
            "playEvents": [
                {
                    "preCount": {"outs": 1},
                    "offense": {
                        "batter": {"fullName": "Bo Bichette"},
                        "second": {"fullName": "Runner Two"},
                    },
                }
            ],
        }
    ]
    client = FakeClient(
        game,
        raw_by_game={game.game_pk: raw},
        win_probability_plays_by_game={game.game_pk: win_probability_plays},
    )
    store = FakeStore()
    sent_messages: list[str] = []
    scheduler = LiveScheduler(
        client=client,
        store=store,
        settings=settings(),
        send_alert=_capture(sent_messages),
    )

    await scheduler.poll_once()

    assert len(sent_messages) == 1
    assert strip_irc_formatting(sent_messages[0]) == (
        "Lead change: TOR takes the lead on Bo Bichette doubles. | "
        "TOR 2, BAL 1 | Top 8 | WP TOR +18.4% | "
        "LI 3.2 (down 1, tying run on 2B, 1 out) | "
        "Barrel Bo Bichette: EV 111.2 mph, LA 24 deg, Dist 390 ft"
    )
    assert set(store.sent_keys) == {
        "123:play:31",
        "123:score:31",
        "123:lead_change:31",
        "123:wp_swing:31",
        "123:high_leverage:31",
        "123:hard_hit:bbe-1",
        "123:barrel:bbe-1",
    }


@pytest.mark.asyncio
async def test_scheduler_suppresses_existing_alerts_for_live_game_on_first_poll() -> None:
    game = _game_summary(
        status="In Progress",
        abstract_state="Live",
        detailed_state="In Progress",
    )
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
    await scheduler.poll_once()

    assert client.detail_calls == [123, 123]
    assert sent_messages == []
    assert store.sent_keys == []


@pytest.mark.asyncio
async def test_scheduler_sends_deferred_home_run_park_followup() -> None:
    game = _game_summary()
    raw = _home_run_raw(game.game_pk)
    client = FakeClient(game, raw_by_game={game.game_pk: raw})
    store = FakeStore()
    sent_messages: list[str] = []
    scheduler = LiveScheduler(
        client=client,
        store=store,
        settings=settings(near_start_poll_seconds=0),
        send_alert=_capture(sent_messages),
    )

    await scheduler.poll_once()
    raw["liveData"]["plays"]["allPlays"][0]["homeRunData"] = {"parks": 24}
    await scheduler.poll_once()
    await scheduler.poll_once()

    assert len(sent_messages) == 2
    assert strip_irc_formatting(sent_messages[0]) == (
        "HR: Rafael Flores Jr. homers on a fly ball to center field. | "
        "EV 108.7 mph, LA 26 deg, Dist 440 ft"
    )
    assert strip_irc_formatting(sent_messages[1]) == (
        "HR parks: Rafael Flores Jr. 80% (24/30) | Dist 440 ft | "
        "TOR 1, BAL 0 | Top 3"
    )
    assert store.sent_keys.count("123:hr_parks:5") == 1


@pytest.mark.asyncio
async def test_scheduler_skips_home_run_park_followup_when_original_had_parks() -> None:
    game = _game_summary()
    raw = _home_run_raw(game.game_pk, parks=24)
    client = FakeClient(game, raw_by_game={game.game_pk: raw})
    store = FakeStore()
    sent_messages: list[str] = []
    scheduler = LiveScheduler(
        client=client,
        store=store,
        settings=settings(near_start_poll_seconds=0),
        send_alert=_capture(sent_messages),
    )

    await scheduler.poll_once()
    await scheduler.poll_once()

    assert len(sent_messages) == 1
    assert strip_irc_formatting(sent_messages[0]) == (
        "HR: Rafael Flores Jr. homers on a fly ball to center field. | "
        "EV 108.7 mph, LA 26 deg, Dist 440 ft, "
        "HR parks 80% (24/30)"
    )
    assert "123:hr_parks:5" not in store.sent_keys


class FakeClient:
    def __init__(
        self,
        *games: GameSummary,
        raw_by_game: dict[int, dict] | None = None,
        win_probability_plays_by_game: dict[int, list[dict]] | None = None,
    ) -> None:
        self.games = list(games)
        self.raw_by_game = raw_by_game or {}
        self.win_probability_plays_by_game = win_probability_plays_by_game or {}
        self.detail_calls: list[int] = []

    async def get_schedule(self, _target_date):
        return self.games

    async def get_game_detail(self, game_pk: int) -> GameDetail:
        self.detail_calls.append(game_pk)
        game = next(game for game in self.games if game.game_pk == game_pk)
        raw = self.raw_by_game.get(game_pk)
        if raw is not None:
            return GameDetail(summary=game, raw=raw)
        return GameDetail(
            summary=game,
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
        return self.win_probability_plays_by_game.get(_game_pk, [])


class FakeStore:
    def __init__(self) -> None:
        self.sent_keys: list[str] = []
        self.messages: dict[str, str] = {}

    async def seen(self, alert_key: str) -> bool:
        return alert_key in self.sent_keys

    async def message_for(self, alert_key: str) -> str | None:
        return self.messages.get(alert_key)

    async def mark_sent(
        self,
        *,
        alert_key: str,
        alert_type: str,
        game_pk: int | None,
        message: str,
    ) -> None:
        self.sent_keys.append(alert_key)
        self.messages.setdefault(alert_key, message)


def _capture(messages: list[str]):
    async def send_alert(message: str) -> None:
        messages.append(message)

    return send_alert


def settings(**overrides) -> SimpleNamespace:
    values = {
        "zoneinfo": lambda: ZoneInfo("UTC"),
        "schedule_poll_seconds": 300,
        "active_game_poll_seconds": 15,
        "near_start_poll_seconds": 60,
        "alert_hard_hit_threshold_mph": 110.0,
        "alert_win_probability_threshold": 15.0,
        "alert_high_leverage_threshold": 2.5,
        "enable_alert_home_runs": True,
        "enable_alert_scoring": True,
        "enable_alert_bases_loaded": True,
        "enable_alert_finals": True,
        "enable_alert_no_hitter": True,
        "enable_alert_immaculate": True,
        "enable_alert_cycle": True,
        "enable_alert_win_probability": True,
        "enable_alert_high_leverage": True,
        "enable_alert_hard_hit": True,
        "enable_alert_barrel": True,
        "enable_alert_late_threat": True,
        "enable_alert_weather": True,
        "enable_alert_lead_changes": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _game_summary(
    game_date: datetime | None = None,
    game_pk: int = 123,
    status: str = "Preview",
    abstract_state: str = "Preview",
    detailed_state: str = "Scheduled",
) -> GameSummary:
    game_date = game_date or datetime.now(UTC) + timedelta(minutes=30)
    return GameSummary(
        game_pk=game_pk,
        game_date=game_date,
        official_date=game_date.date(),
        status=status,
        abstract_state=abstract_state,
        detailed_state=detailed_state,
        away=TeamInfo(id=141, name="Toronto Blue Jays", abbreviation="TOR"),
        home=TeamInfo(id=110, name="Baltimore Orioles", abbreviation="BAL"),
    )


def _home_run_raw(game_pk: int, parks: int | None = None) -> dict:
    play = {
        "about": {
            "atBatIndex": 5,
            "inning": 3,
            "halfInning": "top",
            "isTopInning": True,
        },
        "result": {
            "event": "Home Run",
            "eventType": "home_run",
            "description": "Rafael Flores Jr. homers on a fly ball to center field.",
            "awayScore": 1,
            "homeScore": 0,
        },
        "matchup": {"batter": {"fullName": "Rafael Flores Jr."}},
        "playEvents": [
            {
                "playId": "hr-play",
                "hitData": {
                    "launchSpeed": 108.7,
                    "launchAngle": 26.0,
                    "totalDistance": 440.0,
                },
            }
        ],
    }
    if parks is not None:
        play["homeRunData"] = {"parks": parks}
    return {
        "gamePk": game_pk,
        "gameData": {
            "game": {"pk": game_pk},
            "teams": {
                "away": {"id": 141, "abbreviation": "TOR"},
                "home": {"id": 110, "abbreviation": "BAL"},
            },
        },
        "liveData": {"plays": {"allPlays": [play]}},
    }
