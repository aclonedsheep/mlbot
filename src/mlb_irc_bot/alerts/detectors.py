from collections import defaultdict
from typing import Any

from mlb_irc_bot import irc_format as irc
from mlb_irc_bot.alerts.messages import Alert

JsonDict = dict[str, Any]


def collect_alerts(
    feed: JsonDict,
    *,
    hard_hit_threshold_mph: float = 110.0,
    win_probability_threshold: float = 15.0,
    high_leverage_threshold: float = 2.5,
) -> list[Alert]:
    alerts: list[Alert] = []
    alerts.extend(_scoring_alerts(feed))
    alerts.extend(_home_run_alerts(feed))
    alerts.extend(_win_probability_alerts(feed, win_probability_threshold))
    alerts.extend(_high_leverage_alerts(feed, high_leverage_threshold))
    alerts.extend(_batted_ball_alerts(feed, hard_hit_threshold_mph))
    alerts.extend(_late_threat_alerts(feed))
    alerts.extend(_game_info_alerts(feed))
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
        f"{_alert_label('Final', irc.IRCColor.GRAY)}: "
        f"{irc.team(summary.away.abbreviation)} {irc.value(summary.away_score)}, "
        f"{irc.team(summary.home.abbreviation, home=True)} {irc.value(summary.home_score)}"
    )
    return Alert(key=key, alert_type="final", game_pk=summary.game_pk, message=message)


def _home_run_alerts(feed: JsonDict) -> list[Alert]:
    game_pk = _game_pk(feed)
    alerts = []
    scoring_indices = set(_plays(feed).get("scoringPlays") or [])
    for index, play in enumerate(_all_plays(feed)):
        if index in scoring_indices or not _is_home_run_play(play):
            continue
        alerts.append(_home_run_alert(game_pk, play, index))
    return alerts


def _scoring_alerts(feed: JsonDict) -> list[Alert]:
    game_pk = _game_pk(feed)
    plays = _all_plays(feed)
    scoring_indices = set(_plays(feed).get("scoringPlays") or [])
    alerts = []
    for index in sorted(scoring_indices):
        if index >= len(plays):
            continue
        play = plays[index]
        if _is_home_run_play(play):
            alerts.append(_home_run_alert(game_pk, play, index))
            continue
        result = play.get("result") or {}
        description = result.get("description") or result.get("event") or "Run scored"
        key = f"{game_pk}:score:{play.get('about', {}).get('atBatIndex', index)}"
        alerts.append(
            Alert(
                key=key,
                alert_type="scoring",
                game_pk=game_pk,
                message=f"{_alert_label('Scoring play', irc.IRCColor.RED)}: {description}",
            )
        )
    return alerts


def _home_run_alert(game_pk: int | None, play: JsonDict, index: int) -> Alert:
    result = play.get("result") or {}
    batter = _person_name(play.get("matchup", {}).get("batter"))
    description = result.get("description") or f"Home run by {batter}"
    details = _home_run_details(play)
    detail_text = f" | {details}" if details else ""
    key = f"{game_pk}:hr:{play.get('about', {}).get('atBatIndex', index)}"
    return Alert(
        key=key,
        alert_type="home_run",
        game_pk=game_pk,
        message=f"{_alert_label('HR', irc.IRCColor.ORANGE)}: {description}{detail_text}",
    )


def _is_home_run_play(play: JsonDict) -> bool:
    result = play.get("result") or {}
    event = (result.get("eventType") or result.get("event") or "").lower()
    return event in {"home_run", "home run"}


def _win_probability_alerts(feed: JsonDict, threshold: float) -> list[Alert]:
    game_pk = _game_pk(feed)
    alerts: list[Alert] = []
    for index, play in enumerate(_win_probability_plays(feed)):
        added = _home_win_probability_added(play)
        if added is None or abs(added) < threshold:
            continue
        team = _team_abbreviation(feed, "home" if added >= 0 else "away")
        about = play.get("about") or {}
        result = play.get("result") or {}
        description = result.get("description") or result.get("event") or "Win probability swing"
        key = f"{game_pk}:wp_swing:{about.get('atBatIndex', index)}"
        alerts.append(
            Alert(
                key=key,
                alert_type="win_probability",
                game_pk=game_pk,
                message=(
                    f"{_alert_label('WP swing', irc.IRCColor.LIGHT_CYAN)}: "
                    f"{irc.team(team)} {irc.value('+' + _format_percent(abs(added)))} "
                    f"{_play_inning_text(about)}: "
                    f"{description}"
                ),
            )
        )
    return alerts


def _high_leverage_alerts(feed: JsonDict, threshold: float) -> list[Alert]:
    game_pk = _game_pk(feed)
    alerts: list[Alert] = []
    for index, play in enumerate(_win_probability_plays(feed)):
        leverage = _first_float(play.get("leverageIndex"))
        if leverage is None or leverage < threshold:
            continue
        about = play.get("about") or {}
        result = play.get("result") or {}
        batter = _person_name((play.get("matchup") or {}).get("batter")) or "Batter"
        description = result.get("description") or result.get("event") or "plate appearance"
        key = f"{game_pk}:high_leverage:{about.get('atBatIndex', index)}"
        alerts.append(
            Alert(
                key=key,
                alert_type="high_leverage",
                game_pk=game_pk,
                message=(
                    f"{_alert_label('High leverage', irc.IRCColor.PURPLE)}: "
                    f"{irc.value(f'LI {_format_number(leverage)}')} "
                    f"{_play_inning_text(about)}, "
                    f"{irc.bold(batter)} - {description}"
                ),
            )
        )
    return alerts


def _batted_ball_alerts(feed: JsonDict, hard_hit_threshold: float) -> list[Alert]:
    game_pk = _game_pk(feed)
    alerts: list[Alert] = []
    for index, play in enumerate(_all_plays(feed)):
        if _is_home_run_play(play):
            continue
        hit_data = _batted_ball_hit_data(play)
        if not hit_data:
            continue
        exit_velocity = _first_float(hit_data.get("launchSpeed"))
        launch_angle = _first_float(hit_data.get("launchAngle"))
        distance = _first_float(hit_data.get("totalDistance"))
        if exit_velocity is None:
            continue
        play_id = _batted_ball_play_id(play) or str(
            (play.get("about") or {}).get("atBatIndex", index)
        )
        result = play.get("result") or {}
        description = result.get("description") or result.get("event") or "Batted ball"
        details = _batted_ball_details(exit_velocity, launch_angle, distance)
        if exit_velocity >= hard_hit_threshold:
            alerts.append(
                Alert(
                    key=f"{game_pk}:hard_hit:{play_id}",
                    alert_type="hard_hit",
                    game_pk=game_pk,
                    message=(
                        f"{_alert_label('Hard hit', irc.IRCColor.ORANGE)}: "
                        f"{description} | {details}"
                    ),
                )
            )
        if _is_barrel_or_sweet_spot(exit_velocity, launch_angle):
            alerts.append(
                Alert(
                    key=f"{game_pk}:barrel:{play_id}",
                    alert_type="barrel",
                    game_pk=game_pk,
                    message=(
                        f"{_alert_label('Barrel', irc.IRCColor.YELLOW)}: "
                        f"{description} | {details}"
                    ),
                )
            )
    return alerts


def _late_threat_alerts(feed: JsonDict) -> list[Alert]:
    game_pk = _game_pk(feed)
    linescore = _linescore(feed)
    inning = int(linescore.get("currentInning") or 0)
    if inning < 7:
        return []
    offense = linescore.get("offense") or {}
    offense_team_name = _person_name(offense.get("team")) or "Offense"
    offense_side = _side_for_team(feed, offense.get("team") or {})
    if offense_side not in {"away", "home"}:
        return []
    defense_side = "home" if offense_side == "away" else "away"
    teams = linescore.get("teams") or {}
    offense_runs = _first_int((teams.get(offense_side) or {}).get("runs"))
    defense_runs = _first_int((teams.get(defense_side) or {}).get("runs"))
    if offense_runs is None or defense_runs is None:
        return []
    runners = sum(1 for base in ("first", "second", "third") if offense.get(base))
    deficit = defense_runs - offense_runs
    if deficit < 0:
        return []
    if deficit == 0:
        threat = "go-ahead run at the plate"
    elif deficit <= runners:
        threat = "tying run on base"
    elif deficit == runners + 1:
        threat = "tying run at the plate"
    else:
        return []
    half = linescore.get("inningHalf") or ""
    outs = linescore.get("outs", 0)
    batter = _current_batter(feed, offense) or "batter"
    score_text = _score_text(feed, linescore)
    key = f"{game_pk}:late_threat:{inning}:{half}:{outs}:{offense_team_name}:{runners}:{deficit}"
    return [
        Alert(
            key=key,
            alert_type="late_threat",
            game_pk=game_pk,
            message=(
                f"{_alert_label('Late threat', irc.IRCColor.RED)}: "
                f"{irc.bold(offense_team_name)} has the {threat}, "
                f"{_inning_text(half, inning)}, {score_text}, "
                f"{irc.value(_outs_text(outs))}, {irc.bold(batter)} up."
            ),
        )
    ]


def _game_info_alerts(feed: JsonDict) -> list[Alert]:
    game_pk = _game_pk(feed)
    game_data = _game_data(feed)
    weather = game_data.get("weather") or {}
    game_info = game_data.get("gameInfo") or {}
    parts = []
    first_pitch = game_info.get("firstPitch")
    if first_pitch:
        first_pitch_text = str(first_pitch).replace("T", " ").replace("Z", " UTC")
        parts.append(f"first pitch {irc.value(first_pitch_text)}")
    delay = game_info.get("delayDurationMinutes")
    if delay:
        parts.append(f"delay {irc.value(str(delay))} min")
    weather_bits = []
    if weather.get("condition"):
        weather_bits.append(str(weather.get("condition")))
    if weather.get("temp"):
        weather_bits.append(f"{weather.get('temp')}F")
    if weather.get("wind"):
        weather_bits.append(f"wind {weather.get('wind')}")
    if weather_bits:
        parts.append(", ".join(weather_bits))
    if not parts:
        return []
    away = _team_abbreviation(feed, "away")
    home = _team_abbreviation(feed, "home")
    return [
        Alert(
            key=f"{game_pk}:game_info",
            alert_type="weather",
            game_pk=game_pk,
            message=(
                f"{_alert_label('Game info', irc.IRCColor.LIGHT_BLUE)}: "
                f"{irc.team(away)} @ {irc.team(home, home=True)} - "
                + "; ".join(parts)
            ),
        )
    ]


def _bases_loaded_alerts(feed: JsonDict) -> list[Alert]:
    game_pk = _game_pk(feed)
    linescore = _linescore(feed)
    offense = linescore.get("offense") or {}
    if not all(offense.get(base) for base in ("first", "second", "third")):
        return []
    inning = linescore.get("currentInning")
    half = linescore.get("inningHalf") or ""
    team = _person_name(offense.get("team")) or "Offense"
    context = _bases_loaded_context(feed, linescore, offense, team, half, inning)
    key = f"{game_pk}:bases_loaded:{inning}:{half}:{team}"
    return [
        Alert(
            key=key,
            alert_type="bases_loaded",
            game_pk=game_pk,
            message=f"{_alert_label('Bases loaded', irc.IRCColor.ORANGE)}: {context}.",
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
    star = _top_performer_text(feed)
    star_text = f" | {star}" if star else ""
    return [
        Alert(
            key=f"{game_pk}:final",
            alert_type="final",
            game_pk=game_pk,
            message=(
                f"{_alert_label('Final', irc.IRCColor.GRAY)}: "
                f"{irc.team(away_team)} {irc.value(away_runs)}, "
                f"{irc.team(home_team, home=True)} {irc.value(home_runs)}"
                f"{star_text}"
            ),
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
                message=(
                    f"{_alert_label('No-hit bid', irc.IRCColor.RED)}: "
                    f"{irc.team(pitching_abbr)} has held {irc.team(batting_abbr, home=True)} "
                    f"hitless through inning {irc.value(inning)}."
                ),
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
                    message=(
                        f"{_alert_label('Cycle completed', irc.IRCColor.GREEN)}: "
                        f"{irc.bold(player_name)} has singled, doubled, "
                        "tripled, and homered."
                    ),
                )
            )
        elif len(missing) == 1:
            alerts.append(
                Alert(
                    key=f"{game_pk}:cycle_watch:{player_id}:{missing[0]}",
                    alert_type="cycle_watch",
                    game_pk=game_pk,
                    message=(
                        f"{_alert_label('Cycle watch', irc.IRCColor.PURPLE)}: "
                        f"{irc.bold(player_name)} needs a {irc.value(missing[0])}."
                    ),
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
        group_key = (int(about.get("inning") or 0), about.get("halfInning") or "", int(pitcher))
        grouped[group_key].append(play)

    alerts = []
    for (inning, half, pitcher_id), plays in grouped.items():
        if len(plays) != 3:
            continue
        if not all(
            "strikeout" in ((play.get("result") or {}).get("event") or "").lower()
            for play in plays
        ):
            continue
        pitch_count = sum(_pitch_count(play) for play in plays)
        if pitch_count != 9:
            continue
        pitcher_name = _person_name((plays[0].get("matchup") or {}).get("pitcher"))
        pitcher_name = pitcher_name or str(pitcher_id)
        key = f"{game_pk}:immaculate:{pitcher_id}:{inning}:{half}"
        alerts.append(
            Alert(
                key=key,
                alert_type="immaculate",
                game_pk=game_pk,
                    message=(
                        f"{_alert_label('Immaculate inning', irc.IRCColor.LIGHT_CYAN)}: "
                        f"{irc.bold(pitcher_name)} struck out the side "
                        f"on {irc.value(9)} pitches in the {irc.bold(f'{half} {inning}')}."
                    ),
            )
        )
    return alerts


def _home_run_details(play: JsonDict) -> str:
    advanced = play.get("homeRunData") or play.get("homeRunDetails") or {}
    hit_data = _batted_ball_hit_data(play)
    exit_velocity = _first_float(
        hit_data.get("launchSpeed"),
        advanced.get("exitVelocity"),
        advanced.get("exit_velocity"),
    )
    launch_angle = _first_float(
        hit_data.get("launchAngle"),
        advanced.get("launchAngle"),
        advanced.get("launch_angle"),
    )
    distance = _first_float(
        hit_data.get("totalDistance"),
        advanced.get("distance"),
        advanced.get("hrDistance"),
        advanced.get("hr_distance"),
    )
    other_parks = _first_int(advanced.get("otherParks"), advanced.get("other_parks"))
    if other_parks is None:
        parks = _first_int(
            advanced.get("parks"),
            advanced.get("parkCount"),
            advanced.get("park_count"),
            advanced.get("ct"),
        )
        if parks is not None:
            other_parks = max(parks - 1, 0)

    parts = []
    if exit_velocity is not None:
        parts.append(f"EV {irc.value(_format_number(exit_velocity))} mph")
    if launch_angle is not None:
        parts.append(f"LA {irc.value(_format_number(launch_angle))} deg")
    if distance is not None:
        parts.append(f"Dist {irc.value(_format_number(distance))} ft")
    if other_parks is not None:
        parts.append(f"Other parks {irc.value(f'{other_parks}/29')}")
    return ", ".join(parts)


def _batted_ball_hit_data(play: JsonDict) -> JsonDict:
    if play.get("hitData"):
        return play.get("hitData") or {}
    for event in reversed(play.get("playEvents") or []):
        if event.get("hitData"):
            return event.get("hitData") or {}
    return {}


def _batted_ball_play_id(play: JsonDict) -> str:
    fallback = ""
    for event in reversed(play.get("playEvents") or []):
        play_id = str(event.get("playId") or "")
        if event.get("hitData") and play_id:
            return play_id
        if play_id and not fallback:
            fallback = play_id
    return fallback


def _batted_ball_details(
    exit_velocity: float,
    launch_angle: float | None,
    distance: float | None,
) -> str:
    parts = [f"EV {irc.value(_format_number(exit_velocity))} mph"]
    if launch_angle is not None:
        parts.append(f"LA {irc.value(_format_number(launch_angle))} deg")
    if distance is not None:
        parts.append(f"Dist {irc.value(_format_number(distance))} ft")
    return ", ".join(parts)


def _is_barrel_or_sweet_spot(exit_velocity: float, launch_angle: float | None) -> bool:
    if launch_angle is None:
        return False
    return exit_velocity >= 95 and 8 <= launch_angle <= 32


def _win_probability_plays(feed: JsonDict) -> list[JsonDict]:
    return list(feed.get("winProbabilityPlays") or [])


def _home_win_probability_added(play: JsonDict) -> float | None:
    home_added = _first_float(play.get("homeTeamWinProbabilityAdded"))
    if home_added is not None:
        return home_added
    away_added = _first_float(play.get("awayTeamWinProbabilityAdded"))
    if away_added is not None:
        return -away_added
    return None


def _bases_loaded_context(
    feed: JsonDict,
    linescore: JsonDict,
    offense: JsonDict,
    team: str,
    half: str,
    inning: Any,
) -> str:
    parts = [f"{irc.bold(team)} batting"]
    inning_text = _inning_text(half, inning)
    if inning_text:
        parts.append(irc.bold(inning_text))
    score_text = _score_text(feed, linescore)
    if score_text:
        parts.append(score_text)
    parts.append(irc.value(_outs_text(linescore.get("outs", 0))))
    batter = _current_batter(feed, offense)
    if batter:
        parts.append(f"{irc.bold(batter)} up")
    return ", ".join(parts)


def _inning_text(half: str, inning: Any) -> str:
    if half and inning:
        return f"{half} {inning}"
    if inning:
        return f"Inning {inning}"
    return str(half or "")


def _play_inning_text(about: JsonDict) -> str:
    return _inning_text(str(about.get("halfInning") or "").title(), about.get("inning"))


def _score_text(feed: JsonDict, linescore: JsonDict) -> str:
    teams = linescore.get("teams") or {}
    away_runs = (teams.get("away") or {}).get("runs")
    home_runs = (teams.get("home") or {}).get("runs")
    if away_runs is None and home_runs is None:
        return ""
    away_team = _team_abbreviation(feed, "away")
    home_team = _team_abbreviation(feed, "home")
    away_score = "-" if away_runs is None else str(away_runs)
    home_score = "-" if home_runs is None else str(home_runs)
    return (
        f"{irc.team(away_team)} {irc.value(away_score)}, "
        f"{irc.team(home_team, home=True)} {irc.value(home_score)}"
    )


def _outs_text(value: Any) -> str:
    outs = int(value or 0)
    suffix = "out" if outs == 1 else "outs"
    return f"{outs} {suffix}"


def _current_batter(feed: JsonDict, offense: JsonDict) -> str:
    batter = _person_name(offense.get("batter"))
    if batter:
        return batter
    batter = _person_name((_plays(feed).get("currentPlay") or {}).get("matchup", {}).get("batter"))
    if batter:
        return batter
    plays = _all_plays(feed)
    if not plays:
        return ""
    return _person_name((plays[-1].get("matchup") or {}).get("batter"))


def _first_float(*values: Any) -> float | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_int(*values: Any) -> int | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return None


def _format_number(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _format_percent(value: float) -> str:
    return f"{value:.1f}%".replace(".0%", "%")


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


def _top_performer_text(feed: JsonDict) -> str:
    boxscore = ((feed.get("liveData") or {}).get("boxscore") or feed.get("boxscore") or {})
    performers = boxscore.get("topPerformers") or []
    if not performers:
        return ""
    performer = performers[0]
    player = performer.get("player") or {}
    person = player.get("person") or player
    player_name = _person_name(person)
    stats = player.get("stats") or {}
    batting = stats.get("batting") or {}
    pitching = stats.get("pitching") or {}
    summary = batting.get("summary") or pitching.get("summary")
    if not player_name:
        return ""
    if summary:
        return f"{irc.section('Star')}: {irc.bold(player_name)} {summary}"
    return f"{irc.section('Star')}: {irc.bold(player_name)}"


def _team_abbreviation(feed: JsonDict, side: str) -> str:
    team = (((feed.get("gameData") or {}).get("teams") or {}).get(side) or {})
    return team.get("abbreviation") or team.get("teamName") or side.upper()


def _side_for_team(feed: JsonDict, team: JsonDict) -> str:
    team_id = team.get("id")
    team_name = team.get("name") or team.get("abbreviation")
    for side in ("away", "home"):
        raw_team = (((feed.get("gameData") or {}).get("teams") or {}).get(side) or {})
        if team_id is not None and raw_team.get("id") == team_id:
            return side
        if team_name and team_name in {
            raw_team.get("name"),
            raw_team.get("abbreviation"),
            raw_team.get("teamName"),
        }:
            return side
    return ""


def _person_name(value: JsonDict | None) -> str:
    if not value:
        return ""
    return value.get("fullName") or value.get("name") or value.get("abbreviation") or ""


def _alert_label(text: str, color: irc.IRCColor) -> str:
    return irc.style(text, fg=color, bold=True)
