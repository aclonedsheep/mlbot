from mlb_irc_bot.alerts.detectors import collect_alerts
from mlb_irc_bot.alerts.messages import consolidate_alerts
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
        == "HR: Mookie Betts homers. | LAD 4, NYY 0 | Top 6, 1 out | "
        "EV 105.5 mph, LA 28 deg, Dist 412 ft, Other parks 23/29"
    )
    assert (
        strip_irc_formatting(alerts_by_type["scoring"].message)
        == "Scoring play: Freddie Freeman singles. Will Smith scores. | "
        "LAD 4, NYY 0 | Top 6, 1 out"
    )
    assert alerts_by_type["home_run"].key == "999:hr:10"
    assert alerts_by_type["scoring"].key == "999:score:11"
    assert (
        strip_irc_formatting(alerts_by_type["bases_loaded"].message)
        == "Bases loaded: LAD 4, NYY 0 | Top 6, 1 out | "
        "Los Angeles Dodgers batting, Shohei Ohtani up."
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


def test_bases_loaded_alert_uses_next_batter_when_linescore_batter_is_runner() -> None:
    feed = {
        "gameData": {
            "game": {"pk": 824829},
            "teams": {
                "away": {"abbreviation": "SEA"},
                "home": {"abbreviation": "BAL"},
            },
        },
        "liveData": {
            "linescore": {
                "currentInning": 3,
                "inningHalf": "Bottom",
                "outs": 1,
                "teams": {
                    "away": {"runs": 0},
                    "home": {"runs": 0},
                },
                "offense": {
                    "team": {"id": 110, "name": "Baltimore Orioles"},
                    "batter": {"id": 683002, "fullName": "Gunnar Henderson"},
                    "onDeck": {"id": 624413, "fullName": "Pete Alonso"},
                    "first": {"id": 683002, "fullName": "Gunnar Henderson"},
                    "second": {"id": 621493, "fullName": "Taylor Ward"},
                    "third": {"id": 677942, "fullName": "Blaze Alexander"},
                },
            },
            "plays": {
                "currentPlay": {
                    "about": {"atBatIndex": 21, "isComplete": True},
                    "matchup": {
                        "batter": {"id": 683002, "fullName": "Gunnar Henderson"}
                    },
                    "result": {"event": "Walk", "description": "Gunnar Henderson walks."},
                },
                "allPlays": [
                    {
                        "about": {"atBatIndex": 21, "isComplete": True},
                        "matchup": {
                            "batter": {"id": 683002, "fullName": "Gunnar Henderson"}
                        },
                        "result": {
                            "event": "Walk",
                            "description": "Gunnar Henderson walks.",
                        },
                    }
                ],
            },
        },
    }

    alerts = collect_alerts(feed)
    bases_loaded = next(alert for alert in alerts if alert.alert_type == "bases_loaded")

    assert strip_irc_formatting(bases_loaded.message) == (
        "Bases loaded: SEA 0, BAL 0 | Bottom 3, 1 out | "
        "Baltimore Orioles batting, Pete Alonso up."
    )


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
        "Hard hit: Bo Bichette doubles. | TOR 3, BAL 4 | Top 8, 2 outs | "
        "EV 111.2 mph, LA 24 deg, Dist 390 ft"
    )
    assert by_type["barrel"].startswith(
        "Barrel: Bo Bichette doubles. | TOR 3, BAL 4 | Top 8, 2 outs | "
        "EV 111.2 mph, LA 24 deg, Dist 390 ft"
    )
    assert by_type["late_threat"].startswith(
        "Late threat: Toronto Blue Jays has the tying run at the plate"
    )
    assert by_type["weather"].startswith(
        "Game info: TOR @ BAL - first pitch 2026-06-06 18:12:00.000 UTC"
    )


def test_batted_ball_alerts_include_hitter_when_result_text_is_generic() -> None:
    feed = {
        "gamePk": 777,
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "about": {"atBatIndex": 31},
                        "result": {"event": "Double", "eventType": "double"},
                        "matchup": {"batter": {"fullName": "Cal Raleigh"}},
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
                ],
            },
        },
    }

    alerts = collect_alerts(feed)
    by_type = {alert.alert_type: strip_irc_formatting(alert.message) for alert in alerts}
    batch = consolidate_alerts(alerts)[0]

    assert by_type["hard_hit"] == (
        "Hard hit: Cal Raleigh - Double | EV 111.2 mph, LA 24 deg, Dist 390 ft"
    )
    assert by_type["barrel"] == (
        "Barrel: Cal Raleigh - Double | EV 111.2 mph, LA 24 deg, Dist 390 ft"
    )
    assert strip_irc_formatting(batch.message) == (
        "Barrel: Cal Raleigh - Double | EV 111.2 mph, LA 24 deg, Dist 390 ft"
    )


def test_consolidate_alerts_combines_overlapping_play_alerts() -> None:
    feed = {
        "gamePk": 777,
        "gameData": {
            "teams": {
                "away": {"id": 141, "abbreviation": "TOR"},
                "home": {"id": 110, "abbreviation": "BAL"},
            },
        },
        "winProbabilityPlays": [
            {
                "homeTeamWinProbabilityAdded": -18.4,
                "leverageIndex": 3.2,
                "about": {"atBatIndex": 31, "inning": 8, "halfInning": "top"},
                "matchup": {"batter": {"fullName": "Bo Bichette"}},
                "result": {"description": "Bo Bichette doubles."},
            }
        ],
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

    alerts = collect_alerts(feed)
    batches = consolidate_alerts(alerts)

    assert len(batches) == 1
    assert {alert.alert_type for alert in batches[0].components} == {
        "scoring",
        "lead_change",
        "win_probability",
        "high_leverage",
        "hard_hit",
        "barrel",
    }
    assert batches[0].key == "777:play:31"
    assert strip_irc_formatting(batches[0].message) == (
        "Lead change: TOR takes the lead on Bo Bichette doubles. | "
        "TOR 2, BAL 1 | Top 8 | WP TOR +18.4% | LI 3.2 | "
        "Barrel Bo Bichette: EV 111.2 mph, LA 24 deg, Dist 390 ft"
    )


def test_consolidate_alerts_uses_barrel_detail_over_hard_hit() -> None:
    feed = {
        "gamePk": 777,
        "gameData": {
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
                        "about": {"atBatIndex": 30, "inning": 6, "halfInning": "top"},
                        "result": {
                            "event": "Single",
                            "description": "Toronto opens the scoring.",
                            "awayScore": 1,
                            "homeScore": 0,
                        },
                    },
                    {
                        "about": {"atBatIndex": 31, "inning": 6, "halfInning": "top"},
                        "result": {
                            "event": "Double",
                            "eventType": "double",
                            "description": "Bo Bichette doubles. Runner scores.",
                            "awayScore": 2,
                            "homeScore": 0,
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

    batch = consolidate_alerts(collect_alerts(feed))[0]
    plain = strip_irc_formatting(batch.message)

    assert plain == (
        "Scoring play: Bo Bichette doubles. Runner scores. | "
        "Barrel Bo Bichette: EV 111.2 mph, LA 24 deg, Dist 390 ft"
    )
    assert "Hard hit EV" not in plain


def test_collect_alerts_detects_tie_go_ahead_and_walkoff_scoring_state() -> None:
    feed = {
        "gameData": {
            "game": {"pk": 888},
            "status": {"abstractGameState": "Final", "detailedState": "Final"},
            "teams": {
                "away": {"abbreviation": "TOR"},
                "home": {"abbreviation": "BAL"},
            },
        },
        "liveData": {
            "plays": {
                "scoringPlays": [0, 1, 2, 3],
                "allPlays": [
                    {
                        "about": {"atBatIndex": 1, "inning": 2, "halfInning": "top"},
                        "result": {
                            "event": "Single",
                            "description": "Toronto opens the scoring.",
                            "awayScore": 1,
                            "homeScore": 0,
                        },
                    },
                    {
                        "about": {"atBatIndex": 2, "inning": 4, "halfInning": "bottom"},
                        "result": {
                            "event": "Double",
                            "description": "Baltimore ties the game.",
                            "awayScore": 1,
                            "homeScore": 1,
                        },
                    },
                    {
                        "about": {"atBatIndex": 3, "inning": 7, "halfInning": "top"},
                        "result": {
                            "event": "Home Run",
                            "description": "Toronto goes back in front.",
                            "awayScore": 3,
                            "homeScore": 1,
                        },
                    },
                    {
                        "about": {"atBatIndex": 4, "inning": 9, "halfInning": "bottom"},
                        "result": {
                            "event": "Single",
                            "description": "Baltimore walks it off.",
                            "awayScore": 3,
                            "homeScore": 4,
                        },
                    },
                ],
            },
        },
    }

    alerts = collect_alerts(feed)
    by_type = {
        alert.alert_type: strip_irc_formatting(alert.message)
        for alert in alerts
        if alert.alert_type in {"tie_game", "lead_change", "walkoff"}
    }

    assert by_type["tie_game"] == (
        "Tie game: BAL ties it on Baltimore ties the game. | TOR 1, BAL 1 | Bottom 4"
    )
    assert by_type["lead_change"] == (
        "Go-ahead: TOR takes the lead on Toronto goes back in front. | "
        "TOR 3, BAL 1 | Top 7"
    )
    assert by_type["walkoff"] == (
        "Walk-off: BAL wins on Baltimore walks it off. | TOR 3, BAL 4 | Bottom 9"
    )
    first_run_message = "Go-ahead: TOR takes the lead on Toronto opens"
    assert not any(
        strip_irc_formatting(alert.message).startswith(first_run_message)
        for alert in alerts
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
