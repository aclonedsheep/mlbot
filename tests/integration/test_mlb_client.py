import json
from datetime import date
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from mlb_irc_bot.mlb.client import MLBStatsClient
from mlb_irc_bot.mlb.models import PlayerSearchResult


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


@pytest.mark.asyncio
@respx.mock
async def test_game_highlights_prefer_mp4_video_urls() -> None:
    route = respx.get("https://statsapi.mlb.com/api/v1/game/123/content").mock(
        return_value=httpx.Response(
            200,
            json={
                "highlights": {
                    "highlights": {
                        "items": [
                            {
                                "headline": "Big swing ties the game",
                                "slug": "big-swing-ties-the-game",
                                "description": "Big swing ties the game with a two-run homer.",
                                "duration": "00:00:39",
                                "playbacks": [
                                    {
                                        "name": "mp4Avc",
                                        "url": "https://clips.example/video.mp4",
                                    }
                                ],
                            }
                        ]
                    },
                    "live": {
                        "items": [
                            {
                                "title": "Walk-off single",
                                "id": "walk-off-single",
                                "duration": "00:00:28",
                            }
                        ]
                    },
                }
            },
        )
    )
    page_route = respx.get("https://www.mlb.com/video/walk-off-single").mock(
        return_value=httpx.Response(
            200,
            content=(
                b'<meta property="og:video" '
                b'content="https://clips.example/walk-off-single.mp4">'
            ),
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )

    async with MLBStatsClient() as client:
        highlights = await client.get_game_highlights(123)

    assert route.called
    assert page_route.called
    assert [highlight.title for highlight in highlights] == [
        "Walk-off single",
        "Big swing ties the game",
    ]
    assert highlights[0].url == "https://clips.example/walk-off-single.mp4"
    assert highlights[0].page_url == "https://www.mlb.com/video/walk-off-single"
    assert highlights[1].url == "https://clips.example/video.mp4"
    assert highlights[1].page_url == "https://www.mlb.com/video/big-swing-ties-the-game"
    assert highlights[1].tags == ("homers", "scoring")
    assert highlights[1].duration == "00:00:39"

    async with MLBStatsClient() as client:
        homer_highlights = await client.get_game_highlights(123, limit=None, tag="homers")

    assert [highlight.title for highlight in homer_highlights] == ["Big swing ties the game"]


@pytest.mark.asyncio
@respx.mock
async def test_enrich_home_run_data_matches_savant_play_id() -> None:
    route = respx.get("https://baseballsavant.mlb.com/leaderboard/home-runs").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "game_pk": "123",
                    "play_id": "play-hr",
                    "ct": "24",
                    "exit_velocity": "105.5",
                    "launch_angle": "28",
                    "hr_distance": "412",
                }
            ],
        )
    )
    feed = {
        "gamePk": 123,
        "gameData": {
            "game": {"pk": 123},
            "datetime": {"officialDate": "2026-06-01"},
        },
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "result": {"eventType": "home_run"},
                        "matchup": {"batter": {"id": 660271}},
                        "playEvents": [
                            {"playId": "pitch-1"},
                            {"playId": "play-hr", "hitData": {"launchSpeed": 104}},
                        ],
                    }
                ]
            }
        },
    }

    async with MLBStatsClient() as client:
        await client.enrich_home_run_data(feed)

    params = parse_qs(urlparse(str(route.calls.last.request.url)).query)
    assert params["type"] == ["details"]
    assert params["player_id"] == ["660271"]
    assert params["year"] == ["2026"]
    home_run_data = feed["liveData"]["plays"]["allPlays"][0]["homeRunData"]
    assert home_run_data["parks"] == 24
    assert home_run_data["otherParks"] == 23
    assert home_run_data["exitVelocity"] == 105.5
    assert home_run_data["launchAngle"] == 28.0


@pytest.mark.asyncio
@respx.mock
async def test_enrich_home_run_data_refreshes_stale_savant_cache() -> None:
    route = respx.get("https://baseballsavant.mlb.com/leaderboard/home-runs").mock(
        side_effect=[
            httpx.Response(200, json=[_savant_home_run_row("old-play", 10)]),
            httpx.Response(
                200,
                json=[
                    _savant_home_run_row("old-play", 10),
                    _savant_home_run_row("new-play", 30),
                ],
            ),
        ]
    )

    async with MLBStatsClient() as client:
        await client.enrich_home_run_data(_home_run_feed("old-play"))
        feed = _home_run_feed("new-play")
        await client.enrich_home_run_data(feed)

    assert route.call_count == 2
    assert feed["liveData"]["plays"]["allPlays"][0]["homeRunData"]["otherParks"] == 29


@pytest.mark.asyncio
@respx.mock
async def test_savant_leaderboards_parse_embedded_page_rows() -> None:
    player = _player()
    percentiles_route = respx.get(
        "https://baseballsavant.mlb.com/leaderboard/percentile-rankings"
    ).mock(
        return_value=httpx.Response(
            200,
            content=_savant_html(
                "leaderboard_data",
                [
                    {"player_id": "1", "percent_rank_xwoba": 10},
                    {"player_id": "660271", "percent_rank_xwoba": 98},
                ],
            ),
        )
    )
    expected_route = respx.get(
        "https://baseballsavant.mlb.com/leaderboard/expected_statistics"
    ).mock(
        return_value=httpx.Response(
            200,
            content=_savant_html(
                "data",
                [{"entity_id": 660271, "est_woba": ".420", "exit_velocity_avg": 94.2}],
            ),
        )
    )

    async with MLBStatsClient() as client:
        percentiles = await client.get_savant_percentiles(player, season=2026)
        expected = await client.get_savant_expected_stats(player, season=2026)

    assert percentiles.stats["percent_rank_xwoba"] == 98
    assert expected.stats["est_woba"] == ".420"
    params = parse_qs(urlparse(str(percentiles_route.calls.last.request.url)).query)
    assert params["type"] == ["batter"]
    assert params["year"] == ["2026"]
    params = parse_qs(urlparse(str(expected_route.calls.last.request.url)).query)
    assert params["min"] == ["0"]


@pytest.mark.asyncio
@respx.mock
async def test_savant_tracking_and_run_value_queries() -> None:
    player = _player()
    routes = {
        "bat": respx.get("https://baseballsavant.mlb.com/leaderboard/bat-tracking").mock(
            return_value=httpx.Response(
                200,
                content=_savant_html("data", [{"id": 660271, "avg_sweetspot_speed_mph": 75.8}]),
            )
        ),
        "runvalue": respx.get("https://baseballsavant.mlb.com/leaderboard/swing-take").mock(
            return_value=httpx.Response(
                200,
                content=_savant_html("data", [{"player_id": "660271", "runs_all": 16.8}]),
            )
        ),
        "fieldrv": respx.get(
            "https://baseballsavant.mlb.com/leaderboard/fielding-run-value"
        ).mock(
            return_value=httpx.Response(
                200,
                content=_savant_html("data", [{"id": 660271, "total_runs": 13.1}]),
            )
        ),
        "baserun": respx.get(
            "https://baseballsavant.mlb.com/leaderboard/baserunning-run-value"
        ).mock(
            return_value=httpx.Response(
                200,
                content=_savant_html("data", [{"entity_id": 660271, "runner_runs_tot": 4.0}]),
            )
        ),
        "arm": respx.get("https://baseballsavant.mlb.com/leaderboard/arm-strength").mock(
            return_value=httpx.Response(
                200,
                content=_savant_html("data", [{"player_id": "660271", "arm_overall": 87.3}]),
            )
        ),
        "speed": respx.get("https://baseballsavant.mlb.com/leaderboard/sprint_speed").mock(
            return_value=httpx.Response(
                200,
                content=_savant_html(
                    "data",
                    [{"runner_id": "660271", "r_sprint_speed_top50percent": 28.7}],
                ),
            )
        ),
    }

    async with MLBStatsClient() as client:
        bat = await client.get_savant_bat_tracking(player, season=2026)
        runvalue = await client.get_savant_run_value(player, season=2026)
        fieldrv = await client.get_savant_fielding_run_value(player, season=2026)
        baserun = await client.get_savant_baserunning_run_value(player, season=2026)
        arm = await client.get_savant_arm_strength(player, season=2026)
        speed = await client.get_savant_sprint_speed(player, season=2026)

    assert bat.stats["avg_sweetspot_speed_mph"] == 75.8
    assert runvalue.stats["runs_all"] == 16.8
    assert fieldrv.stats["total_runs"] == 13.1
    assert baserun.stats["runner_runs_tot"] == 4.0
    assert arm.stats["arm_overall"] == 87.3
    assert speed.stats["r_sprint_speed_top50percent"] == 28.7
    bat_params = parse_qs(urlparse(str(routes["bat"].calls.last.request.url)).query)
    assert bat_params["minSwings"] == ["1"]
    assert bat_params["seasonStart"] == ["2026"]
    fieldrv_params = parse_qs(urlparse(str(routes["fieldrv"].calls.last.request.url)).query)
    assert fieldrv_params["minInnings"] == ["0"]


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


def _home_run_feed(play_id: str) -> dict:
    return {
        "gamePk": 123,
        "gameData": {
            "game": {"pk": 123},
            "datetime": {"officialDate": "2026-06-01"},
        },
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "result": {"eventType": "home_run"},
                        "matchup": {"batter": {"id": 660271}},
                        "playEvents": [{"playId": play_id, "hitData": {"launchSpeed": 104}}],
                    }
                ]
            }
        },
    }


def _savant_home_run_row(play_id: str, parks: int) -> dict:
    return {
        "game_pk": "123",
        "play_id": play_id,
        "ct": str(parks),
        "exit_velocity": "105.5",
        "launch_angle": "28",
        "hr_distance": "412",
    }


def _player() -> PlayerSearchResult:
    return PlayerSearchResult(
        person_id=660271,
        full_name="Shohei Ohtani",
        team_name="Los Angeles Dodgers",
        position="DH",
        active=True,
    )


def _savant_html(variable: str, rows: list[dict], *, declaration: str = "var") -> bytes:
    return f"<html><script>{declaration} {variable} = {json.dumps(rows)};</script></html>".encode()
