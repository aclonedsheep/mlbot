from datetime import date
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from mlb_irc_bot.mlb.client import MLBStatsClient


@pytest.mark.asyncio
@respx.mock
async def test_schedule_uses_hydration_and_parses_linescore() -> None:
    route = respx.get("https://statsapi.mlb.com/api/v1/schedule").mock(
        return_value=httpx.Response(200, json=_schedule_payload())
    )

    async with MLBStatsClient() as client:
        games = await client.get_schedule(date(2026, 5, 31), team_id=147)

    assert route.called
    params = parse_qs(urlparse(str(route.calls.last.request.url)).query)
    assert params["hydrate"] == ["team,linescore,probablePitcher,flags"]
    assert params["teamId"] == ["147"]
    assert games[0].game_pk == 123
    assert games[0].linescore.current_inning == 7
    assert games[0].is_live


@pytest.mark.asyncio
@respx.mock
async def test_game_detail_falls_back_when_live_feed_404s() -> None:
    respx.get("https://statsapi.mlb.com/api/v1.1/game/123/feed/live").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://statsapi.mlb.com/api/v1/game/123/feed/live").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://statsapi.mlb.com/api/v1/schedule").mock(
        return_value=httpx.Response(200, json=_schedule_payload())
    )
    respx.get("https://statsapi.mlb.com/api/v1/game/123/linescore").mock(
        return_value=httpx.Response(200, json={"currentInning": 7})
    )
    respx.get("https://statsapi.mlb.com/api/v1/game/123/boxscore").mock(
        return_value=httpx.Response(200, json={"teams": {}})
    )
    respx.get("https://statsapi.mlb.com/api/v1/game/123/playByPlay").mock(
        return_value=httpx.Response(
            200,
            json={"allPlays": [{"result": {"description": "Last play happened."}}]},
        )
    )

    async with MLBStatsClient() as client:
        detail = await client.get_game_detail(123)

    assert detail.summary.game_pk == 123
    assert detail.raw["linescore"]["currentInning"] == 7
    assert detail.last_play == "Last play happened."


@pytest.mark.asyncio
@respx.mock
async def test_game_detail_uses_v11_live_feed() -> None:
    route = respx.get("https://statsapi.mlb.com/api/v1.1/game/123/feed/live").mock(
        return_value=httpx.Response(
            200,
            json={
                "gamePk": 123,
                "gameData": {
                    "game": {"pk": 123},
                    "datetime": {
                        "dateTime": "2026-05-31T23:05:00Z",
                        "officialDate": "2026-05-31",
                    },
                    "status": {
                        "abstractGameState": "Live",
                        "detailedState": "In Progress",
                    },
                    "teams": {
                        "away": {
                            "id": 119,
                            "name": "Los Angeles Dodgers",
                            "abbreviation": "LAD",
                        },
                        "home": {
                            "id": 147,
                            "name": "New York Yankees",
                            "abbreviation": "NYY",
                        },
                    },
                },
                "liveData": {
                    "linescore": {
                        "teams": {"away": {"runs": 3}, "home": {"runs": 2}},
                    },
                    "plays": {
                        "allPlays": [
                            {"result": {"description": "A live play happened."}}
                        ]
                    },
                },
            },
        )
    )

    async with MLBStatsClient() as client:
        detail = await client.get_game_detail(123)

    assert route.called
    assert detail.summary.is_live
    assert detail.summary.away_score == 3
    assert detail.last_play == "A live play happened."


def _schedule_payload() -> dict:
    return {
        "dates": [
            {
                "games": [
                    {
                        "gamePk": 123,
                        "gameDate": "2026-05-31T23:05:00Z",
                        "officialDate": "2026-05-31",
                        "status": {
                            "abstractGameState": "Live",
                            "detailedState": "In Progress",
                        },
                        "teams": {
                            "away": {
                                "score": 3,
                                "team": {
                                    "id": 119,
                                    "name": "Los Angeles Dodgers",
                                    "abbreviation": "LAD",
                                },
                                "probablePitcher": {"fullName": "Dodger Arm"},
                            },
                            "home": {
                                "score": 2,
                                "team": {
                                    "id": 147,
                                    "name": "New York Yankees",
                                    "abbreviation": "NYY",
                                },
                                "probablePitcher": {"fullName": "Yankee Arm"},
                            },
                        },
                        "venue": {"name": "Yankee Stadium"},
                        "linescore": {
                            "currentInning": 7,
                            "inningHalf": "Top",
                            "balls": 1,
                            "strikes": 2,
                            "outs": 1,
                            "offense": {"first": {"id": 1}},
                        },
                    }
                ]
            }
        ]
    }
