from collections import defaultdict
from typing import Any

from mlb_irc_bot.alerts.messages import Alert

JsonDict = dict[str, Any]


def collect_alerts(feed: JsonDict) -> list[Alert]:
    alerts: list[Alert] = []
    alerts.extend(_home_run_alerts(feed))
    alerts.extend(_scoring_alerts(feed))
    alerts.extend(_bases_loaded_alerts(feed))
    alerts.extend(_final_alerts(feed))
    alerts.extend(_no_hit_alerts(feed))
    alerts.extend(_cycle_alerts(feed))
    alerts.extend(_immaculate_alerts(feed))
    return alerts


def final_alert_from_summary(summary: Any) -> Alert | None:
    if not getattr(summary, "is_final", False):
        return None
    key = f"{summary.game_pk}:final"
    message = (
        f"Final: {summary.away.abbreviation} {summary.away_score}, "
        f"{summary.home.abbreviation} {summary.home_score}"
    )
    return Alert(key=key, alert_type="final", game_pk=summary.game_pk, message=message)


def _home_run_alerts(feed: JsonDict) -> list[Alert]:
    game_pk = _game_pk(feed)
    alerts = []
    for index, play in enumerate(_all_plays(feed)):
        result = play.get("result") or {}
        event = (result.get("eventType") or result.get("event") or "").lower()
        if event not in {"home_run", "home run"}:
            continue
        batter = _person_name(play.get("matchup", {}).get("batter"))
        description = result.get("description") or f"Home run by {batter}"
        key = f"{game_pk}:hr:{play.get('about', {}).get('atBatIndex', index)}"
        alerts.append(Alert(key=key, alert_type="home_run", game_pk=game_pk, message=f"HR: {description}"))
    return alerts


def _scoring_alerts(feed: JsonDict) -> list[Alert]:
    game_pk = _game_pk(feed)
    plays = _all_plays(feed)
    scoring_indices = set(_plays(feed).get("scoringPlays") or [])
    alerts = []
    for index in scoring_indices:
        if index >= len(plays):
            continue
        play = plays[index]
        result = play.get("result") or {}
        description = result.get("description") or result.get("event") or "Run scored"
        key = f"{game_pk}:score:{play.get('about', {}).get('atBatIndex', index)}"
        alerts.append(Alert(key=key, alert_type="scoring", game_pk=game_pk, message=f"Scoring play: {description}"))
    return alerts


def _bases_loaded_alerts(feed: JsonDict) -> list[Alert]:
    game_pk = _game_pk(feed)
    linescore = _linescore(feed)
    offense = linescore.get("offense") or {}
    if not all(offense.get(base) for base in ("first", "second", "third")):
        return []
    inning = linescore.get("currentInning")
    half = linescore.get("inningHalf") or ""
    team = _person_name(offense.get("team")) or "Offense"
    key = f"{game_pk}:bases_loaded:{inning}:{half}:{team}"
    return [
        Alert(
            key=key,
            alert_type="bases_loaded",
            game_pk=game_pk,
            message=f"Bases loaded: {team}, {half} {inning}, {linescore.get('outs', 0)} out(s).",
        )
    ]


def _final_alerts(feed: JsonDict) -> list[Alert]:
    game_pk = _game_pk(feed)
    status = (_game_data(feed).get("status") or {}).get("abstractGameState", "").lower()
    detailed = (_game_data(feed).get("status") or {}).get("detailedState", "").lower()
    if status != "final" and detailed not in {"final", "game over", "completed early"}:
        return []
    linescore = _linescore(feed)
    teams = linescore.get("teams") or {}
    away_team = _team_abbreviation(feed, "away")
    home_team = _team_abbreviation(feed, "home")
    away_runs = (teams.get("away") or {}).get("runs")
    home_runs = (teams.get("home") or {}).get("runs")
    return [
        Alert(
            key=f"{game_pk}:final",
            alert_type="final",
            game_pk=game_pk,
            message=f"Final: {away_team} {away_runs}, {home_team} {home_runs}",
        )
    ]


def _no_hit_alerts(feed: JsonDict) -> list[Alert]:
    game_pk = _game_pk(feed)
    linescore = _linescore(feed)
    inning = int(linescore.get("currentInning") or 0)
    if inning < 6:
        return []
    teams = linescore.get("teams") or {}
    alerts = []
    for batting_side, pitching_side in (("away", "home"), ("home", "away")):
        batting = teams.get(batting_side) or {}
        if batting.get("hits") not in (0, "0"):
            continue
        pitching_abbr = _team_abbreviation(feed, pitching_side)
        batting_abbr = _team_abbreviation(feed, batting_side)
        key = f"{game_pk}:no_hit:{pitching_side}:{inning}"
        alerts.append(
            Alert(
                key=key,
                alert_type="no_hitter",
                game_pk=game_pk,
                message=f"No-hit bid: {pitching_abbr} has held {batting_abbr} hitless through inning {inning}.",
            )
        )
    return alerts


def _cycle_alerts(feed: JsonDict) -> list[Alert]:
    game_pk = _game_pk(feed)
    alerts = []
    for player_id, player in _boxscore_players(feed).items():
        batting = ((player.get("stats") or {}).get("batting") or {})
        hit_counts = {
            "single": int(batting.get("singles") or 0),
            "double": int(batting.get("doubles") or 0),
            "triple": int(batting.get("triples") or 0),
            "home run": int(batting.get("homeRuns") or 0),
        }
        missing = [name for name, count in hit_counts.items() if count == 0]
        player_name = _person_name(player.get("person")) or player_id.replace("ID", "")
        if not missing:
            alerts.append(
                Alert(
                    key=f"{game_pk}:cycle:{player_id}",
                    alert_type="cycle",
                    game_pk=game_pk,
                    message=f"Cycle completed: {player_name} has singled, doubled, tripled, and homered.",
                )
            )
        elif len(missing) == 1:
            alerts.append(
                Alert(
                    key=f"{game_pk}:cycle_watch:{player_id}:{missing[0]}",
                    alert_type="cycle_watch",
                    game_pk=game_pk,
                    message=f"Cycle watch: {player_name} needs a {missing[0]}.",
                )
            )
    return alerts


def _immaculate_alerts(feed: JsonDict) -> list[Alert]:
    game_pk = _game_pk(feed)
    grouped: dict[tuple[int, str, int], list[JsonDict]] = defaultdict(list)
    for play in _all_plays(feed):
        about = play.get("about") or {}
        pitcher = ((play.get("matchup") or {}).get("pitcher") or {}).get("id")
        if pitcher is None:
            continue
        grouped[(int(about.get("inning") or 0), about.get("halfInning") or "", int(pitcher))].append(play)

    alerts = []
    for (inning, half, pitcher_id), plays in grouped.items():
        if len(plays) != 3:
            continue
        if not all("strikeout" in ((play.get("result") or {}).get("event") or "").lower() for play in plays):
            continue
        pitch_count = sum(_pitch_count(play) for play in plays)
        if pitch_count != 9:
            continue
        pitcher_name = _person_name((plays[0].get("matchup") or {}).get("pitcher")) or str(pitcher_id)
        key = f"{game_pk}:immaculate:{pitcher_id}:{inning}:{half}"
        alerts.append(
            Alert(
                key=key,
                alert_type="immaculate",
                game_pk=game_pk,
                message=f"Immaculate inning: {pitcher_name} struck out the side on 9 pitches in the {half} {inning}.",
            )
        )
    return alerts


def _pitch_count(play: JsonDict) -> int:
    events = play.get("playEvents") or []
    return sum(1 for event in events if (event.get("details") or {}).get("isPitch"))


def _game_pk(feed: JsonDict) -> int | None:
    return (
        feed.get("gamePk")
        or ((feed.get("gameData") or {}).get("game") or {}).get("pk")
        or feed.get("game_pk")
    )


def _game_data(feed: JsonDict) -> JsonDict:
    return feed.get("gameData") or {}


def _linescore(feed: JsonDict) -> JsonDict:
    if "linescore" in feed:
        return feed.get("linescore") or {}
    return ((feed.get("liveData") or {}).get("linescore") or {})


def _plays(feed: JsonDict) -> JsonDict:
    if "playByPlay" in feed:
        return feed.get("playByPlay") or {}
    return ((feed.get("liveData") or {}).get("plays") or {})


def _all_plays(feed: JsonDict) -> list[JsonDict]:
    return list(_plays(feed).get("allPlays") or [])


def _boxscore_players(feed: JsonDict) -> dict[str, JsonDict]:
    if "boxscore" in feed:
        boxscore = feed.get("boxscore") or {}
    else:
        boxscore = ((feed.get("liveData") or {}).get("boxscore") or {})
    players = {}
    for side in ("away", "home"):
        players.update(((boxscore.get("teams") or {}).get(side) or {}).get("players") or {})
    return players


def _team_abbreviation(feed: JsonDict, side: str) -> str:
    team = (((feed.get("gameData") or {}).get("teams") or {}).get(side) or {})
    return team.get("abbreviation") or team.get("teamName") or side.upper()


def _person_name(value: JsonDict | None) -> str:
    if not value:
        return ""
    return value.get("fullName") or value.get("name") or value.get("abbreviation") or ""
