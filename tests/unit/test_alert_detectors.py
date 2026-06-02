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
                    "first": {"id": 1},
                    "second": {"id": 2},
                    "third": {"id": 3},
                },
            },
            "plays": {
                "scoringPlays": [0],
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
                        "playEvents": [{"details": {"isPitch": True}} for _ in range(5)],
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
    assert strip_irc_formatting(alerts_by_type["home_run"].message) == "HR: Mookie Betts homers."
    assert (
        strip_irc_formatting(alerts_by_type["bases_loaded"].message)
        == "Bases loaded: Los Angeles Dodgers, Top 6, 1 out(s)."
    )
    assert BOLD in alerts_by_type["home_run"].message
    assert COLOR in alerts_by_type["home_run"].message


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
