from collections import defaultdict
from typing import Any

from mlb_irc_bot import irc_format as irc
from mlb_irc_bot.alerts.messages import Alert

JsonDict = dict[str, Any]
PRIORITY_WALKOFF = 0
PRIORITY_HOME_RUN = 10
PRIORITY_SCORING_STATE = 20
PRIORITY_SCORING = 30
PRIORITY_WIN_PROBABILITY = 40
PRIORITY_HIGH_LEVERAGE = 50
PRIORITY_BARREL = 60
PRIORITY_HARD_HIT = 70

DETAIL_SCORING_STATE = 10
DETAIL_WIN_PROBABILITY = 20
DETAIL_HIGH_LEVERAGE = 30
DETAIL_BARREL = 40
DETAIL_HARD_HIT = 50
MLB_PARK_COUNT = 30
BASES: tuple[tuple[str, str], ...] = (
    ("first", "1B"),
    ("second", "2B"),
    ("third", "3B"),
)
SCORING_BASE_ORDER = ("3B", "2B", "1B")


def collect_alerts(
    feed: JsonDict,
    *,
    hard_hit_threshold_mph: float = 110.0,
    win_probability_threshold: float = 15.0,
    high_leverage_threshold: float = 2.5,
) -> list[Alert]:
    alerts: list[Alert] = []
    alerts.extend(_scoring_alerts(feed))
    alerts.extend(_scoring_state_alerts(feed))
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
        alerts.append(_home_run_alert(feed, game_pk, play, index))
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
            alerts.append(_home_run_alert(feed, game_pk, play, index))
            continue
        result = play.get("result") or {}
        description = result.get("description") or result.get("event") or "Run scored"
        key = f"{game_pk}:score:{play.get('about', {}).get('atBatIndex', index)}"
        alerts.append(
            Alert(
                key=key,
                alert_type="scoring",
                game_pk=game_pk,
                group_key=_play_group_key(game_pk, play, index),
                priority=PRIORITY_SCORING,
                message=(
                    f"{_alert_label('Scoring play', irc.IRCColor.RED)}: "
                    f"{description}{_game_update_suffix(feed)}"
                ),
            )
        )
    return alerts


def _scoring_state_alerts(feed: JsonDict) -> list[Alert]:
    game_pk = _game_pk(feed)
    plays = _all_plays(feed)
    scoring_indices = set(_plays(feed).get("scoringPlays") or [])
    alerts: list[Alert] = []
    previous_away = 0
    previous_home = 0
    for index, play in enumerate(plays):
        result = play.get("result") or {}
        away_score = _first_int(result.get("awayScore"), result.get("away_score"))
        home_score = _first_int(result.get("homeScore"), result.get("home_score"))
        if away_score is None or home_score is None:
            continue
        score_changed = away_score != previous_away or home_score != previous_home
        if index in scoring_indices or score_changed:
            alerts.extend(
                _scoring_state_alerts_for_play(
                    feed,
                    game_pk,
                    play,
                    index,
                    previous_away=previous_away,
                    previous_home=previous_home,
                    away_score=away_score,
                    home_score=home_score,
                )
            )
        previous_away = away_score
        previous_home = home_score
    return alerts


def _scoring_state_alerts_for_play(
    feed: JsonDict,
    game_pk: int | None,
    play: JsonDict,
    index: int,
    *,
    previous_away: int,
    previous_home: int,
    away_score: int,
    home_score: int,
) -> list[Alert]:
    previous_leader = _leader_side(previous_away, previous_home)
    current_leader = _leader_side(away_score, home_score)
    if previous_leader == current_leader:
        return []
    if previous_leader is None and previous_away == 0 and previous_home == 0:
        return []

    about = play.get("about") or {}
    at_bat = about.get("atBatIndex", index)
    description = _play_description(play)
    context = _play_score_context(feed, play, away_score, home_score)
    group_key = _play_group_key(game_pk, play, index)
    if _is_walkoff_play(feed, play, previous_away, previous_home, away_score, home_score):
        team = _team_abbreviation(feed, "home")
        return [
            Alert(
                key=f"{game_pk}:walkoff:{at_bat}",
                alert_type="walkoff",
                game_pk=game_pk,
                group_key=group_key,
                priority=PRIORITY_WALKOFF,
                detail_order=DETAIL_SCORING_STATE,
                detail_key="scoring_state",
                detail_text=f"{irc.section('Walk-off')} {irc.team(team, home=True)}",
                message=(
                    f"{_alert_label('Walk-off', irc.IRCColor.GREEN)}: "
                    f"{irc.team(team, home=True)} wins "
                    f"on {description}{context}"
                ),
            )
        ]

    if current_leader is None and previous_leader is not None:
        scoring_side = _scoring_side(previous_away, previous_home, away_score, home_score)
        team = _team_abbreviation(feed, scoring_side or "away")
        return [
            Alert(
                key=f"{game_pk}:tie_game:{at_bat}",
                alert_type="tie_game",
                game_pk=game_pk,
                group_key=group_key,
                priority=PRIORITY_SCORING_STATE,
                detail_order=DETAIL_SCORING_STATE,
                detail_key="scoring_state",
                detail_text=(
                    f"{irc.section('Tie game')} "
                    f"{irc.team(team, home=scoring_side == 'home')}"
                ),
                message=(
                    f"{_alert_label('Tie game', irc.IRCColor.YELLOW)}: "
                    f"{irc.team(team, home=scoring_side == 'home')} ties it "
                    f"on {description}{context}"
                ),
            )
        ]

    if current_leader is not None:
        team = _team_abbreviation(feed, current_leader)
        label = "Lead change" if previous_leader is not None else "Go-ahead"
        return [
            Alert(
                key=f"{game_pk}:lead_change:{at_bat}",
                alert_type="lead_change",
                game_pk=game_pk,
                group_key=group_key,
                priority=PRIORITY_SCORING_STATE,
                detail_order=DETAIL_SCORING_STATE,
                detail_key="scoring_state",
                detail_text=(
                    f"{irc.section(label)} "
                    f"{irc.team(team, home=current_leader == 'home')}"
                ),
                message=(
                    f"{_alert_label(label, irc.IRCColor.RED)}: "
                    f"{irc.team(team, home=current_leader == 'home')} takes the lead "
                    f"on {description}{context}"
                ),
            )
        ]
    return []


def _home_run_alert(
    feed: JsonDict, game_pk: int | None, play: JsonDict, index: int
) -> Alert:
    result = play.get("result") or {}
    batter = _person_name(play.get("matchup", {}).get("batter"))
    description = result.get("description") or f"Home run by {batter}"
    context = _game_update_suffix(feed)
    details = _home_run_details(play)
    detail_text = f" | {details}" if details else ""
    key = f"{game_pk}:hr:{play.get('about', {}).get('atBatIndex', index)}"
    return Alert(
        key=key,
        alert_type="home_run",
        game_pk=game_pk,
        group_key=_play_group_key(game_pk, play, index),
        priority=PRIORITY_HOME_RUN,
        message=(
            f"{_alert_label('HR', irc.IRCColor.ORANGE)}: "
            f"{description}{context}{detail_text}"
        ),
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
        context = _game_update_suffix(feed)
        key = f"{game_pk}:wp_swing:{about.get('atBatIndex', index)}"
        detail_team = irc.team(team, home=added >= 0)
        detail_value = irc.value("+" + _format_percent(abs(added)))
        alerts.append(
            Alert(
                key=key,
                alert_type="win_probability",
                game_pk=game_pk,
                group_key=_play_group_key(game_pk, play, index),
                priority=PRIORITY_WIN_PROBABILITY,
                detail_order=DETAIL_WIN_PROBABILITY,
                detail_key="win_probability",
                detail_text=f"{irc.section('WP')} {detail_team} {detail_value}",
                message=(
                    f"{_alert_label('WP swing', irc.IRCColor.LIGHT_CYAN)}: "
                    f"{detail_team} {detail_value} "
                    f"{_play_inning_text(about)}: "
                    f"{description}{context}"
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
        context = _game_update_suffix(feed)
        key = f"{game_pk}:high_leverage:{about.get('atBatIndex', index)}"
        leverage_text = _format_number(leverage)
        situation = _high_leverage_situation_text(feed, play)
        situation_text = f" ({situation})" if situation else ""
        alerts.append(
            Alert(
                key=key,
                alert_type="high_leverage",
                game_pk=game_pk,
                group_key=_play_group_key(game_pk, play, index),
                priority=PRIORITY_HIGH_LEVERAGE,
                detail_order=DETAIL_HIGH_LEVERAGE,
                detail_key="high_leverage",
                detail_text=(
                    f"{irc.section('LI')} {irc.value(leverage_text)}{situation_text}"
                ),
                message=(
                    f"{_alert_label('High leverage', irc.IRCColor.PURPLE)}: "
                    f"{irc.value(f'LI {leverage_text}')}{situation_text} "
                    f"{_play_inning_text(about)}, "
                    f"{irc.bold(batter)} - {description}{context}"
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
        description = _batted_ball_description(play)
        context = _game_update_suffix(feed)
        details = _batted_ball_details(exit_velocity, launch_angle, distance)
        detail_subject = _batted_ball_detail_subject(play)
        group_key = _play_group_key(game_pk, play, index)
        if exit_velocity >= hard_hit_threshold:
            alerts.append(
                Alert(
                    key=f"{game_pk}:hard_hit:{play_id}",
                    alert_type="hard_hit",
                    game_pk=game_pk,
                    group_key=group_key,
                    priority=PRIORITY_HARD_HIT,
                    detail_order=DETAIL_HARD_HIT,
                    detail_key="batted_ball",
                    detail_text=f"{irc.section('Hard hit')} {detail_subject}{details}",
                    message=(
                        f"{_alert_label('Hard hit', irc.IRCColor.ORANGE)}: "
                        f"{description}{context} | {details}"
                    ),
                )
            )
        if _is_barrel_or_sweet_spot(exit_velocity, launch_angle, hard_hit_threshold):
            alerts.append(
                Alert(
                    key=f"{game_pk}:barrel:{play_id}",
                    alert_type="barrel",
                    game_pk=game_pk,
                    group_key=group_key,
                    priority=PRIORITY_BARREL,
                    detail_order=DETAIL_BARREL,
                    detail_key="batted_ball",
                    detail_text=f"{irc.section('Barrel')} {detail_subject}{details}",
                    message=(
                        f"{_alert_label('Barrel', irc.IRCColor.YELLOW)}: "
                        f"{description}{context} | {details}"
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
    context = _bases_loaded_context(feed, linescore, offense, team)
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
        context = _game_update_suffix(feed, linescore)
        key = f"{game_pk}:no_hit:{pitching_side}:{inning}"
        alerts.append(
            Alert(
                key=key,
                alert_type="no_hitter",
                game_pk=game_pk,
                message=(
                    f"{_alert_label('No-hit bid', irc.IRCColor.RED)}: "
                    f"{irc.team(pitching_abbr)} has held {irc.team(batting_abbr, home=True)} "
                    f"hitless through inning {irc.value(inning)}{context}."
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
        context = _game_update_suffix(feed)
        if not missing:
            alerts.append(
                Alert(
                    key=f"{game_pk}:cycle:{player_id}",
                    alert_type="cycle",
                    game_pk=game_pk,
                    message=(
                        f"{_alert_label('Cycle completed', irc.IRCColor.GREEN)}: "
                        f"{irc.bold(player_name)} has singled, doubled, "
                        f"tripled, and homered{context}."
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
                        f"{irc.bold(player_name)} needs a {irc.value(missing[0])}{context}."
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
        context = _game_update_suffix(feed)
        key = f"{game_pk}:immaculate:{pitcher_id}:{inning}:{half}"
        alerts.append(
            Alert(
                key=key,
                alert_type="immaculate",
                game_pk=game_pk,
                message=(
                    f"{_alert_label('Immaculate inning', irc.IRCColor.LIGHT_CYAN)}: "
                    f"{irc.bold(pitcher_name)} struck out the side "
                    f"on {irc.value(9)} pitches in the {irc.bold(f'{half} {inning}')}"
                    f"{context}."
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
    parks = _first_int(
        advanced.get("parks"),
        advanced.get("parkCount"),
        advanced.get("park_count"),
        advanced.get("ct"),
    )
    if parks is None:
        other_parks = _first_int(advanced.get("otherParks"), advanced.get("other_parks"))
        if other_parks is not None:
            parks = other_parks + 1

    parts = []
    if exit_velocity is not None:
        parts.append(f"EV {irc.value(_format_number(exit_velocity))} mph")
    if launch_angle is not None:
        parts.append(f"LA {irc.value(_format_number(launch_angle))} deg")
    if distance is not None:
        parts.append(f"Dist {irc.value(_format_number(distance))} ft")
    if parks is not None:
        park_percent = parks / MLB_PARK_COUNT * 100
        park_text = f"{_format_percent(park_percent)} ({parks}/{MLB_PARK_COUNT})"
        parts.append(f"HR parks {irc.value(park_text)}")
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


def _batted_ball_description(play: JsonDict) -> str:
    result = play.get("result") or {}
    description = result.get("description") or result.get("event") or "Batted ball"
    batter = _person_name((play.get("matchup") or {}).get("batter"))
    if not batter or batter.casefold() in str(description).casefold():
        return str(description)
    return f"{batter} - {description}"


def _batted_ball_detail_subject(play: JsonDict) -> str:
    batter = _person_name((play.get("matchup") or {}).get("batter"))
    return f"{irc.bold(batter)}: " if batter else ""


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


def _is_barrel_or_sweet_spot(
    exit_velocity: float,
    launch_angle: float | None,
    exit_velocity_threshold: float,
) -> bool:
    if launch_angle is None:
        return False
    return exit_velocity >= exit_velocity_threshold and 8 <= launch_angle <= 32


def _high_leverage_situation_text(feed: JsonDict, play: JsonDict) -> str:
    base_codes = _play_start_base_codes(play)
    base_state = _base_state_text(base_codes) or _men_on_base_split_text(play)
    score_delta = _batting_score_delta(feed, play)
    parts = [
        part
        for part in (
            _score_delta_text(score_delta),
            _run_pressure_text(score_delta, base_codes),
        )
        if part
    ]
    if base_state and (len(base_codes) != 1 or not parts):
        parts.append(base_state)
    outs = _play_start_outs(play)
    if outs is not None:
        parts.append(_outs_text(outs))
    return ", ".join(parts)


def _play_start_base_codes(play: JsonDict) -> tuple[str, ...]:
    offense = _play_start_offense(play)
    if offense is not None:
        return tuple(label for key, label in BASES if offense.get(key))

    splits = ((play.get("matchup") or {}).get("splits") or {})
    men_on = str(splits.get("menOnBase") or "").replace("_", " ").strip().lower()
    if men_on == "loaded":
        return tuple(label for _, label in BASES)

    starts = {
        str((runner.get("movement") or {}).get("start") or "").upper()
        for runner in play.get("runners") or []
    }
    return tuple(label for _, label in BASES if label in starts)


def _play_start_offense(play: JsonDict) -> JsonDict | None:
    for event in reversed(play.get("playEvents") or []):
        if "offense" in event:
            return event.get("offense") or {}
    if "offense" in play:
        return play.get("offense") or {}
    return None


def _base_state_text(base_codes: tuple[str, ...]) -> str:
    if not base_codes:
        return ""
    if len(base_codes) == 3:
        return "bases loaded"
    label = "/".join(base_codes)
    prefix = "runner" if len(base_codes) == 1 else "runners"
    return f"{prefix} on {label}"


def _men_on_base_split_text(play: JsonDict) -> str:
    splits = ((play.get("matchup") or {}).get("splits") or {})
    men_on = str(splits.get("menOnBase") or "").replace("_", " ").strip().lower()
    if not men_on or men_on == "empty":
        return ""
    if men_on == "loaded":
        return "bases loaded"
    if men_on == "risp":
        return "runner in scoring position"
    if men_on in {"men on", "menon", "on"}:
        return "men on base"
    return men_on


def _batting_score_delta(feed: JsonDict, play: JsonDict) -> int | None:
    score = _play_start_score(feed, play) or _play_result_score(play)
    if score is None:
        return None
    away_score, home_score = score
    if away_score is None or home_score is None:
        return None
    side = _batting_side_for_play(play)
    if side == "away":
        return away_score - home_score
    if side == "home":
        return home_score - away_score
    return None


def _play_start_score(feed: JsonDict, play: JsonDict) -> tuple[int, int] | None:
    target_at_bat = (play.get("about") or {}).get("atBatIndex", play.get("atBatIndex"))
    if target_at_bat is None:
        return None
    previous_score: tuple[int, int] | None = None
    for candidate in _all_plays(feed):
        candidate_at_bat = (candidate.get("about") or {}).get(
            "atBatIndex",
            candidate.get("atBatIndex"),
        )
        if candidate_at_bat == target_at_bat:
            return previous_score
        candidate_score = _play_result_score(candidate)
        if candidate_score is not None:
            previous_score = candidate_score
    return None


def _play_result_score(play: JsonDict) -> tuple[int, int] | None:
    result = play.get("result") or {}
    away_score = _first_int(result.get("awayScore"), result.get("away_score"))
    home_score = _first_int(result.get("homeScore"), result.get("home_score"))
    if away_score is None or home_score is None:
        return None
    return away_score, home_score


def _batting_side_for_play(play: JsonDict) -> str:
    about = play.get("about") or {}
    is_top = about.get("isTopInning")
    if isinstance(is_top, bool):
        return "away" if is_top else "home"
    half = str(about.get("halfInning") or "").lower()
    if half.startswith("top"):
        return "away"
    if half.startswith("bottom"):
        return "home"
    return ""


def _score_delta_text(score_delta: int | None) -> str:
    if score_delta is None:
        return ""
    if score_delta < 0:
        return f"down {abs(score_delta)}"
    if score_delta > 0:
        return f"up {score_delta}"
    return "tie game"


def _run_pressure_text(
    score_delta: int | None,
    base_codes: tuple[str, ...],
) -> str:
    if score_delta is None:
        return ""
    scoring_order = [base for base in SCORING_BASE_ORDER if base in base_codes]
    if score_delta < 0:
        deficit = abs(score_delta)
        if deficit <= len(scoring_order):
            return f"tying run on {scoring_order[deficit - 1]}"
        if deficit == len(scoring_order) + 1:
            return "tying run at plate"
        return ""
    if score_delta == 0:
        if scoring_order:
            return f"go-ahead run on {scoring_order[0]}"
        return "go-ahead run at plate"
    return ""


def _play_start_outs(play: JsonDict) -> int | None:
    for event in reversed(play.get("playEvents") or []):
        outs = _first_int((event.get("preCount") or {}).get("outs"))
        if outs is not None:
            return outs
    for event in reversed(play.get("playEvents") or []):
        outs = _first_int((event.get("count") or {}).get("outs"))
        if outs is not None:
            return outs
    outs = _first_int((play.get("count") or {}).get("outs"))
    if outs is None:
        return None
    if (play.get("result") or {}).get("isOut") is True and outs > 0:
        return outs - 1
    return outs


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
) -> str:
    parts = []
    update = _game_update_text(feed, linescore)
    if update:
        parts.append(update)
    batting_parts = [f"{irc.bold(team)} batting"]
    batter = _current_batter(feed, offense)
    if batter:
        batting_parts.append(f"{irc.bold(batter)} up")
    parts.append(", ".join(batting_parts))
    return " | ".join(parts)


def _inning_text(half: str, inning: Any) -> str:
    if half and inning:
        return f"{half} {inning}"
    if inning:
        return f"Inning {inning}"
    return str(half or "")


def _play_inning_text(about: JsonDict) -> str:
    return _inning_text(str(about.get("halfInning") or "").title(), about.get("inning"))


def _leader_side(away_score: int, home_score: int) -> str | None:
    if away_score > home_score:
        return "away"
    if home_score > away_score:
        return "home"
    return None


def _scoring_side(
    previous_away: int,
    previous_home: int,
    away_score: int,
    home_score: int,
) -> str | None:
    away_delta = away_score - previous_away
    home_delta = home_score - previous_home
    if away_delta > home_delta:
        return "away"
    if home_delta > away_delta:
        return "home"
    return None


def _play_description(play: JsonDict) -> str:
    result = play.get("result") or {}
    return result.get("description") or result.get("event") or "the scoring play"


def _play_group_key(game_pk: int | None, play: JsonDict, index: int) -> str | None:
    if game_pk is None:
        return None
    at_bat = (play.get("about") or {}).get("atBatIndex", index)
    if at_bat is None:
        return None
    return f"{game_pk}:play:{at_bat}"


def _play_score_context(
    feed: JsonDict,
    play: JsonDict,
    away_score: int,
    home_score: int,
) -> str:
    about = play.get("about") or {}
    score_text = _score_value_text(feed, away_score, home_score)
    inning_text = _play_inning_text(about)
    parts = [part for part in (score_text, inning_text) if part]
    return " | " + " | ".join(parts) if parts else ""


def _score_value_text(feed: JsonDict, away_score: int, home_score: int) -> str:
    away_team = _team_abbreviation(feed, "away")
    home_team = _team_abbreviation(feed, "home")
    return (
        f"{irc.team(away_team)} {irc.value(away_score)}, "
        f"{irc.team(home_team, home=True)} {irc.value(home_score)}"
    )


def _is_walkoff_play(
    feed: JsonDict,
    play: JsonDict,
    previous_away: int,
    previous_home: int,
    away_score: int,
    home_score: int,
) -> bool:
    about = play.get("about") or {}
    half = str(about.get("halfInning") or "").lower()
    inning = _first_int(about.get("inning")) or 0
    return (
        _is_final_feed(feed)
        and half == "bottom"
        and inning >= 9
        and previous_home <= previous_away
        and home_score > away_score
    )


def _is_final_feed(feed: JsonDict) -> bool:
    status = (_game_data(feed).get("status") or {})
    values = {
        str(status.get("abstractGameState") or "").lower(),
        str(status.get("detailedState") or "").lower(),
    }
    return bool(values & {"final", "game over", "completed early"})


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


def _game_update_suffix(feed: JsonDict, linescore: JsonDict | None = None) -> str:
    update = _game_update_text(feed, linescore)
    return f" | {update}" if update else ""


def _game_update_text(feed: JsonDict, linescore: JsonDict | None = None) -> str:
    linescore = linescore or _linescore(feed)
    if not linescore:
        return ""
    parts = []
    score_text = _score_text(feed, linescore)
    if score_text:
        parts.append(score_text)
    state_text = _inning_outs_text(linescore)
    if state_text:
        parts.append(state_text)
    return " | ".join(parts)


def _inning_outs_text(linescore: JsonDict) -> str:
    inning_text = _inning_text(
        str(linescore.get("inningHalf") or ""),
        linescore.get("currentInning"),
    )
    outs = linescore.get("outs")
    outs_text = "" if outs is None else _outs_text(outs)
    if inning_text and outs_text:
        return f"{inning_text}, {outs_text}"
    return inning_text or outs_text


def _outs_text(value: Any) -> str:
    outs = int(value or 0)
    suffix = "out" if outs == 1 else "outs"
    return f"{outs} {suffix}"


def _current_batter(feed: JsonDict, offense: JsonDict) -> str:
    base_runners = [
        runner
        for runner in (offense.get("first"), offense.get("second"), offense.get("third"))
        if runner
    ]
    current_play = _plays(feed).get("currentPlay") or {}
    current_play_batter = (current_play.get("matchup") or {}).get("batter")
    if not (current_play.get("about") or {}).get("isComplete"):
        batter = _active_batter_name(current_play_batter, base_runners)
        if batter:
            return batter
    offense_batter = offense.get("batter")
    batter = _active_batter_name(offense_batter, base_runners)
    if batter:
        return batter
    if _is_listed_runner(offense_batter, base_runners):
        batter = _person_name(offense.get("onDeck"))
        if batter:
            return batter
    batter = _active_batter_name(current_play_batter, base_runners)
    if batter:
        return batter
    plays = _all_plays(feed)
    if not plays:
        return ""
    return _active_batter_name((plays[-1].get("matchup") or {}).get("batter"), base_runners)


def _active_batter_name(person: JsonDict | None, base_runners: list[JsonDict]) -> str:
    if _is_listed_runner(person, base_runners):
        return ""
    return _person_name(person)


def _is_listed_runner(person: JsonDict | None, base_runners: list[JsonDict]) -> bool:
    if not person:
        return False
    person_id = person.get("id")
    person_name = _person_name(person).casefold()
    for runner in base_runners:
        runner_id = runner.get("id")
        if person_id is not None and runner_id is not None and str(person_id) == str(runner_id):
            return True
        runner_name = _person_name(runner).casefold()
        if person_name and runner_name and person_name == runner_name:
            return True
    return False


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
