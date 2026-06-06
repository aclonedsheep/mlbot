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
                                "hitData": {"launchSpeed": 105.5, "launchAngle": 28.0},
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
        == "HR: Mookie Betts homers. | EV 105.5 mph, LA 28 deg, Other parks 23/29"
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
