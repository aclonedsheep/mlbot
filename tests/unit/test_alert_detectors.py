from mlb_irc_bot.alerts.detectors import collect_alerts
from mlb_irc_bot.irc_format import BOLD, COLOR, strip_irc_formatting


def test_collect_alerts_detects_live_events() -> None:
    feed = {
        "gameData": {
            "game": {"pk": 999},
            "status": {"abstractGameState": "Final", "detailedState": "Final"},
            "teams": {
                "away": {"abbreviation": "LAD"},
                "home": {"abbreviation": "NYY"},
            },
        },
        "liveData": {
            "linescore": {
                "currentInning": 6,
                "inningHalf": "Top",
                "outs": 1,
                "teams": {
                    "away": {"runs": 4, "hits": 5},
                    "home": {"runs": 0, "hits": 0},
                },
                "offense": {
                    "team": {"name": "Los Angeles Dodgers"},
                    "batter": {"fullName": "Shohei Ohtani"},
                    "first": {"id": 1},
                    "second": {"id": 2},
                    "third": {"id": 3},
                },
            },
            "plays": {
                "scoringPlays": [0, 1],
                "allPlays": [
                    {
                        "about": {"atBatIndex": 10, "inning": 1, "halfInning": "top"},
                        "result": {
                            "event": "Home Run",
                            "eventType": "home_run",
                            "description": "Mookie Betts homers.",
                        },
                        "matchup": {
                            "batter": {"fullName": "Mookie Betts"},
                            "pitcher": {"id": 50, "fullName": "Pitcher A"},
                        },
                        "playEvents": [
                            {"details": {"isPitch": True}} for _ in range(4)
                        ]
                        + [
                            {
                                "details": {"isPitch": True},
                                "hitData": {
                                    "launchSpeed": 105.5,
                                    "launchAngle": 28.0,
                                    "totalDistance": 412.0,
                                },
                            }
                        ],
                        "homeRunData": {"parks": 24},
                    },
                    {
                        "about": {"atBatIndex": 11, "inning": 1, "halfInning": "top"},
                        "result": {
                            "event": "Single",
                            "eventType": "single",
                            "description": "Freddie Freeman singles. Will Smith scores.",
                        },
                        "matchup": {
                            "batter": {"fullName": "Freddie Freeman"},
                            "pitcher": {"id": 50, "fullName": "Pitcher A"},
                        },
                    },
                    *_strikeout_half_inning(),
                ],
            },
            "boxscore": {
                "teams": {
                    "away": {
                        "players": {
                            "ID1": {
                                "person": {"fullName": "Cycle Watcher"},
                                "stats": {
                                    "batting": {
                                        "singles": 1,
                                        "doubles": 1,
                                        "triples": 1,
                                        "homeRuns": 0,
                                    }
                                },
                            },
                            "ID2": {
                                "person": {"fullName": "Cycle Finisher"},
                                "stats": {
                                    "batting": {
                                        "singles": 1,
                                        "doubles": 1,
                                        "triples": 1,
                                        "homeRuns": 1,
                                    }
                                },
                            },
                        }
                    },
                    "home": {"players": {}},
                }
            },
        },
    }

    alerts = collect_alerts(feed)
    alert_types = {alert.alert_type for alert in alerts}
    alerts_by_type = {alert.alert_type: alert for alert in alerts}

    assert {
        "home_run",
        "scoring",
        "bases_loaded",
        "final",
        "no_hitter",
        "cycle_watch",
        "cycle",
        "immaculate",
    } <= alert_types
    assert (
        strip_irc_formatting(alerts_by_type["home_run"].message)
        == "HR: Mookie Betts homers. | EV 105.5 mph, LA 28 deg, Dist 412 ft, "
        "Other parks 23/29"
    )
    assert (
        strip_irc_formatting(alerts_by_type["scoring"].message)
        == "Scoring play: Freddie Freeman singles. Will Smith scores."
    )
    assert alerts_by_type["home_run"].key == "999:hr:10"
    assert alerts_by_type["scoring"].key == "999:score:11"
    assert (
        strip_irc_formatting(alerts_by_type["bases_loaded"].message)
        == "Bases loaded: Los Angeles Dodgers batting, Top 6, LAD 4, NYY 0, "
        "1 out, Shohei Ohtani up."
    )
    assert BOLD in alerts_by_type["home_run"].message
    assert COLOR in alerts_by_type["home_run"].message


def test_home_run_scoring_play_is_only_a_home_run_alert() -> None:
    feed = {
        "gameData": {"game": {"pk": 999}},
        "liveData": {
            "plays": {
                "scoringPlays": [0],
                "allPlays": [
                    {
                        "about": {"atBatIndex": 10},
                        "result": {
                            "event": "Home Run",
                            "eventType": "home_run",
                            "description": "Mookie Betts homers.",
                        },
                        "matchup": {"batter": {"fullName": "Mookie Betts"}},
                    }
                ],
            }
        },
    }

    alerts = collect_alerts(feed)

    assert [alert.alert_type for alert in alerts] == ["home_run"]
    assert alerts[0].key == "999:hr:10"
    assert strip_irc_formatting(alerts[0].message) == "HR: Mookie Betts homers."


def test_collect_alerts_detects_new_contextual_alerts() -> None:
    feed = {
        "gamePk": 777,
        "gameData": {
            "teams": {
                "away": {"id": 141, "abbreviation": "TOR"},
                "home": {"id": 110, "abbreviation": "BAL"},
            },
            "weather": {"condition": "Sunny", "temp": "82", "wind": "3 mph, L To R"},
            "gameInfo": {"firstPitch": "2026-06-06T18:12:00.000Z"},
        },
        "winProbabilityPlays": [
            {
                "homeTeamWinProbabilityAdded": 18.4,
                "leverageIndex": 3.2,
                "about": {"atBatIndex": 30, "inning": 8, "halfInning": "bottom"},
                "matchup": {"batter": {"fullName": "Clutch Hitter"}},
                "result": {"description": "Clutch Hitter doubles."},
            }
        ],
        "liveData": {
            "linescore": {
                "currentInning": 8,
                "inningHalf": "Top",
                "outs": 2,
                "teams": {
                    "away": {"runs": 3},
                    "home": {"runs": 4},
                },
                "offense": {
                    "team": {"id": 141, "name": "Toronto Blue Jays"},
                    "batter": {"fullName": "Tying Batter"},
                },
            },
            "plays": {
                "allPlays": [
                    {
                        "about": {"atBatIndex": 31},
                        "result": {
                            "event": "Double",
                            "eventType": "double",
                            "description": "Bo Bichette doubles.",
                        },
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
                    }
                ]
            },
        },
    }

    alerts = collect_alerts(feed)
    by_type = {alert.alert_type: strip_irc_formatting(alert.message) for alert in alerts}

    assert by_type["win_probability"].startswith(
        "WP swing: BAL +18.4% Bottom 8: Clutch Hitter doubles."
    )
    assert by_type["high_leverage"].startswith(
        "High leverage: LI 3.2 Bottom 8, Clutch Hitter - Clutch Hitter doubles."
    )
    assert by_type["hard_hit"].startswith(
        "Hard hit: Bo Bichette doubles. | EV 111.2 mph, LA 24 deg, Dist 390 ft"
    )
    assert by_type["barrel"].startswith(
        "Barrel: Bo Bichette doubles. | EV 111.2 mph, LA 24 deg, Dist 390 ft"
    )
    assert by_type["late_threat"].startswith(
        "Late threat: Toronto Blue Jays has the tying run at the plate"
    )
    assert by_type["weather"].startswith(
        "Game info: TOR @ BAL - first pitch 2026-06-06 18:12:00.000 UTC"
    )


def _strikeout_half_inning() -> list[dict]:
    plays = []
    for index in range(3):
        plays.append(
            {
                "about": {"atBatIndex": 20 + index, "inning": 4, "halfInning": "bottom"},
                "result": {"event": "Strikeout", "description": "Strikeout."},
                "matchup": {"pitcher": {"id": 99, "fullName": "Nine Pitcher"}},
                "playEvents": [{"details": {"isPitch": True}} for _ in range(3)],
            }
        )
    return plays
