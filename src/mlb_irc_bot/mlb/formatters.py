from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from mlb_irc_bot import irc_format as irc
from mlb_irc_bot.mlb.models import (
    GameDetail,
    GameLogEntry,
    GameSummary,
    Leader,
    PitchArsenalEntry,
    PitcherInfo,
    PlayerStats,
    StandingTeam,
    TeamInfo,
    TeamLeaderGroup,
    TeamLineup,
    TeamPitchers,
    TeamRanking,
    TeamStats,
    TopPerformer,
    Transaction,
    WinProbability,
    WinProbabilitySummary,
)

MAX_IRC_LEN = 390


def format_schedule(games: list[GameSummary], target_date: date, tz: ZoneInfo) -> list[str]:
    title = f"MLB {target_date.isoformat()}"
    if not games:
        return [f"{irc.title(title)}: {irc.muted('no games scheduled.')}"]
    bits = [format_game_summary(game, tz) for game in games]
    return [_truncate(f"{irc.title(title)}: " + "; ".join(bits))]


def format_compact_schedule(
    games: list[GameSummary],
    target_date: date,
    tz: ZoneInfo,
    *,
    live_only: bool = False,
) -> list[str]:
    if live_only:
        games = [game for game in games if game.is_live]
        title = "MLB live"
        if not games:
            return [f"{irc.title(title)}: {irc.muted('no games live.')}"]
    else:
        title = f"MLB {target_date.isoformat()}"
        if not games:
            return [f"{irc.title(title)}: {irc.muted('no games scheduled.')}"]

    games = sorted(games, key=lambda game: game.game_date or datetime.max.replace(tzinfo=tz))
    bits = [format_compact_game(game, tz) for game in games]
    return [_truncate(f"{irc.title(title)}: " + "; ".join(bits))]


def format_compact_game(game: GameSummary, tz: ZoneInfo) -> str:
    if game.is_final:
        return (
            f"{_team_abbr(game.away, home=False)} "
            f"{irc.value(f'{game.away_score}-{game.home_score}')} "
            f"{_team_abbr(game.home, home=True)} {irc.muted('F')}"
        )
    if game.is_live:
        state = format_linescore(game) or game.detailed_state or "Live"
        return (
            f"{_team_abbr(game.away, home=False)} "
            f"{irc.value(f'{game.away_score}-{game.home_score}')} "
            f"{_team_abbr(game.home, home=True)} {state}"
        )
    return (
        f"{_team_abbr(game.away, home=False)} vs "
        f"{_team_abbr(game.home, home=True)} {irc.value(_compact_time(game, tz))}"
    )


def format_game_summary(game: GameSummary, tz: ZoneInfo) -> str:
    matchup = f"{_team_abbr(game.away, home=False)} @ {_team_abbr(game.home, home=True)}"
    if game.is_live:
        return f"{matchup}: {score(game)} {format_linescore(game)}"
    if game.is_final:
        return f"{matchup}: {irc.muted('Final')} {score(game)}"
    when = "TBD"
    if game.game_date is not None:
        local = game.game_date.astimezone(tz)
        when = f"{local.strftime('%I').lstrip('0') or '0'}:{local.strftime('%M %p %Z')}"
    probables = _probables(game)
    venue = f" at {game.venue}" if game.venue else ""
    return f"{matchup}: {irc.value(when)}{venue}{probables}"


def format_game_detail(
    detail: GameDetail,
    tz: ZoneInfo,
    *,
    win_probability: WinProbability | None = None,
    win_probability_summary: WinProbabilitySummary | None = None,
    active_pitchers: list[PitcherInfo] | None = None,
) -> list[str]:
    game = detail.summary
    line = format_game_summary(game, tz)
    if win_probability_summary and win_probability_summary.current:
        win_text = _format_win_probability(win_probability_summary.current)
        line += f" | {irc.section('Win')}: {win_text}"
    elif win_probability:
        line += f" | {irc.section('Win')}: {_format_win_probability(win_probability)}"
    if win_probability_summary and win_probability_summary.biggest_swing:
        swing_text = _format_win_probability_swing(win_probability_summary)
        line += f" | {irc.section('Swing')}: {swing_text}"
    if active_pitchers:
        line += f" | {irc.section('P')}: {_format_active_pitchers(active_pitchers)}"
    if detail.last_play:
        line += f" | {irc.section('Last play')}: {detail.last_play}"
    return [_truncate(line)]


def format_linescore(game: GameSummary) -> str:
    linescore = game.linescore
    if not linescore:
        return irc.live(game.detailed_state or game.status)
    inning = ""
    if linescore.inning_half and linescore.current_inning:
        inning = f"{linescore.inning_half} {linescore.current_inning}"
    elif linescore.current_inning:
        inning = f"Inning {linescore.current_inning}"
    count = ""
    if linescore.balls is not None and linescore.strikes is not None:
        count = f", {linescore.balls}-{linescore.strikes}"
    outs = "" if linescore.outs is None else f", {linescore.outs} out"
    if linescore.outs not in (None, 1):
        outs += "s"
    runners = f", runners: {','.join(linescore.runners)}" if linescore.runners else ""
    return irc.live(f"{inning}{outs}{count}{runners}".strip(", "))


def score(game: GameSummary) -> str:
    away_score = "-" if game.away_score is None else str(game.away_score)
    home_score = "-" if game.home_score is None else str(game.home_score)
    return (
        f"{_team_abbr(game.away, home=False)} {irc.value(away_score)}, "
        f"{_team_abbr(game.home, home=True)} {irc.value(home_score)}"
    )


def _team_abbr(team: TeamInfo, *, home: bool) -> str:
    return irc.team(team.abbreviation, home=home)


def format_standings(
    records: list[StandingTeam], *, title: str, wildcard: bool = False
) -> list[str]:
    if not records:
        return [f"{irc.title(title)}: {irc.muted('no standings available.')}"]
    group_attr = "league_name" if wildcard else "division_name"
    grouped: dict[str, list[StandingTeam]] = defaultdict(list)
    for record in records:
        grouped[getattr(record, group_attr) or "MLB"].append(record)

    group_lines = []
    for group_name in sorted(grouped):
        teams = sorted(
            grouped[group_name],
            key=lambda item: _rank_key(item.wild_card_rank if wildcard else item.division_rank),
        )
        display_teams = teams[:6 if wildcard else 3]
        bits = []
        for team in display_teams:
            back = team.wild_card_games_back if wildcard else team.games_back
            rank = team.wild_card_rank if wildcard else team.division_rank
            bits.append(
                f"{irc.value(f'{rank}.')} {irc.team(team.abbreviation)} "
                f"{irc.value(f'{team.wins}-{team.losses}')} {irc.value(back)} GB"
            )
        if len(teams) > len(display_teams):
            bits.append(irc.muted(f"+{len(teams) - len(display_teams)} more"))
        group_lines.append(f"{irc.section(_short_group_name(group_name))}: " + ", ".join(bits))
    if len(group_lines) == 1:
        _, _, only_group = group_lines[0].partition(": ")
        return [_truncate(f"{irc.title(title)}: {only_group}")]
    return [_truncate(f"{irc.title(title)}: " + " | ".join(group_lines))]


def format_team_standing(record: StandingTeam) -> str:
    return _truncate(
        f"{irc.team(record.abbreviation)}: {irc.value(f'{record.wins}-{record.losses}')} "
        f"({irc.value(record.pct)}), {record.division_name} {irc.section('rank')} "
        f"{irc.value(record.division_rank)}, {irc.section('WC rank')} "
        f"{irc.value(record.wild_card_rank or '-')} "
        f"({irc.value(record.wild_card_games_back)} GB), "
        f"{irc.section('L10')} {irc.value(record.last_ten)}, "
        f"{irc.section('streak')} {irc.value(record.streak or '-')}"
    )


def format_player_candidates(candidates: list[str]) -> str:
    return f"{irc.warning('Multiple players matched')}: " + "; ".join(candidates)


def format_player_stats(stats: PlayerStats) -> str:
    period = _player_stat_period(stats)
    if not any(
        (
            stats.stats,
            stats.advanced_stats,
            stats.sabermetric_stats,
            stats.expected_stats,
        )
    ):
        return (
            f"{irc.muted('No')} {irc.stat_label(stats.group)} stats found for "
            f"{irc.bold(stats.player.full_name)} {irc.value(period)}."
        )
    sections = [section for section in _player_stat_sections(stats) if section]
    return _truncate(
        f"{irc.title(stats.player.full_name)} {irc.value(period)} {irc.stat_label(stats.group)}: "
        + " | ".join(sections)
    )


def format_leaders(category: str, leaders: list[Leader]) -> str:
    if not leaders:
        return f"{irc.muted('No leaders found')} for {irc.stat_label(category)}."
    bits = [
        f"{irc.value(f'{leader.rank}.')} {irc.bold(leader.player_name)} "
        f"{irc.value(leader.value)}"
        + (f" ({irc.muted(leader.team_name)})" if leader.team_name else "")
        for leader in leaders
    ]
    return _truncate(f"{irc.title(category)} leaders: " + "; ".join(bits))


def format_boxscore(
    detail: GameDetail,
    pitcher_groups: list[TeamPitchers],
    *,
    top_performers: list[TopPerformer] | None = None,
    win_probability_summary: WinProbabilitySummary | None = None,
) -> str:
    game = detail.summary
    away_line = _team_box_line(detail, "away")
    home_line = _team_box_line(detail, "home")
    state = (
        irc.muted("F")
        if game.is_final
        else (format_linescore(game) or irc.live(game.detailed_state))
    )
    bits = [
        f"{irc.title('Box')} {_team_abbr(game.away, home=False)} {away_line}, "
        f"{_team_abbr(game.home, home=True)} {home_line} {state}".strip()
    ]
    left_on_base = _left_on_base(detail)
    if left_on_base:
        bits.append(f"{irc.section('LOB')} " + left_on_base)
    pitcher_bits = _box_pitcher_bits(pitcher_groups)
    if pitcher_bits:
        bits.append(f"{irc.section('Pitching')}: " + "; ".join(pitcher_bits))
    if top_performers:
        bits.append(f"{irc.section('Stars')}: " + _top_performer_bits(top_performers))
    if win_probability_summary and win_probability_summary.biggest_swing:
        swing_text = _format_win_probability_swing(win_probability_summary)
        bits.append(f"{irc.section('Swing')}: {swing_text}")
    return _truncate(" | ".join(bits))


def format_team_stats(stats_list: list[TeamStats]) -> str:
    if not stats_list:
        return f"{irc.muted('No team stats found.')}"
    team = stats_list[0].team
    period = _team_stat_period(stats_list[0])
    sections = []
    for stats in stats_list:
        if not stats.stats:
            continue
        prefix = "hit" if stats.group == "hitting" else "pitch"
        if stats.group == "pitching":
            section = _format_team_pitching_stats(stats.stats)
        else:
            section = _format_team_hitting_stats(stats.stats)
        if section:
            sections.append(f"{irc.section(prefix)}: {section}")
    if not sections:
        return (
            f"{irc.muted('No team stats found')} for {irc.team(team.abbreviation)} "
            f"{irc.value(period)}."
        )
    return _truncate(
        f"{irc.team(team.abbreviation)} {irc.title('teamstats')} {irc.value(period)}: "
        + " | ".join(sections)
    )


def format_win_probability_summary(
    game: GameSummary, summary: WinProbabilitySummary
) -> str:
    if summary.current is None and summary.biggest_swing is None:
        return (
            f"{irc.title('WP')} {_team_abbr(game.away, home=False)} @ "
            f"{_team_abbr(game.home, home=True)}: {irc.muted('not available')}."
        )
    bits = []
    if summary.current:
        bits.append(f"{irc.section('Now')}: {_format_win_probability(summary.current)}")
    if summary.biggest_swing:
        bits.append(f"{irc.section('Swing')}: {_format_win_probability_swing(summary)}")
    return _truncate(
        f"{irc.title('WP')} {_team_abbr(game.away, home=False)} @ "
        f"{_team_abbr(game.home, home=True)}: " + " | ".join(bits)
    )


def format_top_performers(
    game: GameSummary, performers: list[TopPerformer]
) -> str:
    if not performers:
        return (
            f"{irc.title('Stars')} {_team_abbr(game.away, home=False)} @ "
            f"{_team_abbr(game.home, home=True)}: {irc.muted('not available')}."
        )
    return _truncate(
        f"{irc.title('Stars')} {_team_abbr(game.away, home=False)} @ "
        f"{_team_abbr(game.home, home=True)}: " + _top_performer_bits(performers)
    )


def format_weather(detail: GameDetail) -> str:
    game = detail.summary
    weather = ((detail.raw.get("gameData") or {}).get("weather") or {})
    if not weather:
        return (
            f"{irc.title('Weather')} {_team_abbr(game.away, home=False)} @ "
            f"{_team_abbr(game.home, home=True)}: {irc.muted('not available')}."
        )
    bits = []
    condition = weather.get("condition")
    temp = weather.get("temp")
    wind = weather.get("wind")
    if condition:
        bits.append(str(condition))
    if temp:
        bits.append(f"{temp}F")
    if wind:
        bits.append(f"wind {wind}")
    return _truncate(
        f"{irc.title('Weather')} {_team_abbr(game.away, home=False)} @ "
        f"{_team_abbr(game.home, home=True)}: " + ", ".join(bits)
    )


def format_replay(detail: GameDetail) -> str:
    game = detail.summary
    review = ((detail.raw.get("gameData") or {}).get("review") or {})
    if not review:
        return (
            f"{irc.title('Replay')} {_team_abbr(game.away, home=False)} @ "
            f"{_team_abbr(game.home, home=True)}: {irc.muted('not available')}."
        )
    bits = []
    for side, team in (("away", game.away), ("home", game.home)):
        data = review.get(side) or {}
        if "used" not in data and "remaining" not in data:
            continue
        bits.append(
            f"{_team_abbr(team, home=side == 'home')} "
            f"{irc.value(_display(data.get('remaining', '-')))} left, "
            f"{irc.value(_display(data.get('used', 0)))} used"
        )
    if not bits:
        return (
            f"{irc.title('Replay')} {_team_abbr(game.away, home=False)} @ "
            f"{_team_abbr(game.home, home=True)}: {irc.muted('not available')}."
        )
    return _truncate(
        f"{irc.title('Replay')} {_team_abbr(game.away, home=False)} @ "
        f"{_team_abbr(game.home, home=True)}: " + "; ".join(bits)
    )


def format_game_log(
    player_name: str,
    group: str,
    entries: list[GameLogEntry],
) -> str:
    if not entries:
        return f"{irc.muted('No game log found')} for {irc.bold(player_name)}."
    bits = [_game_log_bit(group, entry) for entry in entries]
    return _truncate(
        f"{irc.title(player_name)} {irc.value(f'last {len(entries)} games')} "
        f"{irc.stat_label(group)}: " + "; ".join(bits)
    )


def format_team_leaders(team: TeamInfo, groups: list[TeamLeaderGroup]) -> str:
    if not groups:
        return (
            f"{irc.team(team.abbreviation)} {irc.title('leaders')}: "
            f"{irc.muted('not available')}."
        )
    bits = []
    for group in groups:
        if not group.leaders:
            continue
        leaders = ", ".join(
            f"{irc.bold(leader.player_name)} {irc.value(leader.value)}"
            for leader in group.leaders[:3]
        )
        if leaders:
            bits.append(f"{irc.section(group.category)}: {leaders}")
    if not bits:
        return (
            f"{irc.team(team.abbreviation)} {irc.title('leaders')}: "
            f"{irc.muted('not available')}."
        )
    return _truncate(
        f"{irc.team(team.abbreviation)} {irc.title('leaders')}: " + " | ".join(bits)
    )


def format_team_rankings(category: str, rankings: list[TeamRanking]) -> str:
    if not rankings:
        return f"{irc.muted('No team rankings found')} for {irc.stat_label(category)}."
    bits = [
        f"{irc.value(f'{ranking.rank}.')} {irc.team(ranking.team.abbreviation)} "
        f"{irc.value(ranking.value)}"
        for ranking in rankings
    ]
    return _truncate(f"{irc.title(category)} team rankings: " + "; ".join(bits))


def format_pitch_arsenal(player_name: str, entries: list[PitchArsenalEntry]) -> str:
    if not entries:
        return f"{irc.muted('No pitch arsenal found')} for {irc.bold(player_name)}."
    bits = []
    for entry in entries[:5]:
        detail = []
        if entry.percentage is not None:
            detail.append(_format_percent_value(entry.percentage))
        if entry.average_speed is not None:
            detail.append(f"{entry.average_speed:.1f} mph")
        if entry.count is not None:
            detail.append(f"{entry.count} pit")
        bits.append(f"{irc.bold(entry.pitch_type)} " + ", ".join(detail))
    return _truncate(f"{irc.title(player_name)} {irc.stat_label('arsenal')}: " + "; ".join(bits))


def format_defense(stats: PlayerStats) -> str:
    stat = stats.stats
    if not stat:
        return f"{irc.muted('No defense stats found')} for {irc.bold(stats.player.full_name)}."
    bits = _labeled_stats(
        stat,
        (
            ("totalOutsAboveAverage", "OAA"),
            ("fieldingRunsPrevented", "Runs Prevented"),
            ("attempts", "Att"),
        ),
    )
    if not bits:
        return f"{irc.muted('No defense stats found')} for {irc.bold(stats.player.full_name)}."
    return _truncate(
        f"{irc.title(stats.player.full_name)} {irc.value(str(stats.season))} "
        f"{irc.stat_label('defense')}: " + ", ".join(bits)
    )


def format_transactions(
    transactions: list[Transaction],
    *,
    title: str,
    limit: int = 5,
) -> str:
    if not transactions:
        return f"{irc.title(title)}: {irc.muted('no transactions found.')}"
    display = transactions[:limit]
    bits = [_transaction_bit(transaction) for transaction in display]
    if len(transactions) > limit:
        bits.append(irc.muted(f"+{len(transactions) - limit} more"))
    return _truncate(f"{irc.title(title)}: " + "; ".join(bits))


def format_current_pitcher(
    game: GameSummary, requested_abbreviation: str, pitcher: PitcherInfo | None
) -> str:
    if pitcher is None:
        return (
            f"{irc.team(requested_abbreviation)}: current pitcher is "
            f"{irc.muted('not available')} for "
            f"{_team_abbr(game.away, home=False)} vs {_team_abbr(game.home, home=True)} "
            f"({irc.live(game.detailed_state)})."
        )
    pitching_line = _format_pitcher_game_stats(pitcher.game_stats)
    return _truncate(
        f"{irc.team(requested_abbreviation)} game pitcher: "
        f"{irc.team(pitcher.team.abbreviation)} "
        f"{irc.bold(pitcher.full_name)} - {pitching_line} "
        f"({_team_abbr(game.away, home=False)} vs {_team_abbr(game.home, home=True)}, "
        f"{irc.live(game.detailed_state or game.status)})"
    )


def format_probable_pitchers(game: GameSummary) -> str:
    away = game.away_probable_pitcher or "TBD"
    home = game.home_probable_pitcher or "TBD"
    return _truncate(
        f"{irc.title('Probable pitchers')} {_team_abbr(game.away, home=False)} vs "
        f"{_team_abbr(game.home, home=True)}: "
        f"{_team_abbr(game.away, home=False)} {irc.bold(away)}; "
        f"{_team_abbr(game.home, home=True)} {irc.bold(home)}"
    )


def format_pitchers(groups: list[TeamPitchers], game: GameSummary) -> list[str]:
    if not groups or not any(group.pitchers for group in groups):
        return [
            f"{irc.title('Pitchers')} are {irc.muted('not available yet')} for "
            f"{_team_abbr(game.away, home=False)} vs {_team_abbr(game.home, home=True)}."
        ]
    bits = [
        f"{irc.team(group.team.abbreviation)}: "
        + "; ".join(_format_pitcher_listing(pitcher) for pitcher in group.pitchers)
        for group in groups
        if group.pitchers
    ]
    return [_truncate(f"{irc.title('Pitchers')}: " + " | ".join(bits))]


def format_lineup(lineup: TeamLineup | None, game: GameSummary, requested_abbreviation: str) -> str:
    if lineup is None or not lineup.entries:
        return (
            f"{irc.team(requested_abbreviation)} lineup is {irc.muted('not available')} for "
            f"{_team_abbr(game.away, home=False)} vs {_team_abbr(game.home, home=True)}."
        )
    bits = [
        f"{irc.value(f'{entry.order}.')} {irc.bold(entry.full_name)} "
        f"{irc.stat_label(entry.position)}".strip()
        for entry in lineup.entries
    ]
    return _truncate(
        f"{irc.team(lineup.team.abbreviation)} {irc.title('lineup')}: " + "; ".join(bits)
    )


def _format_win_probability(win_probability: WinProbability) -> str:
    values = [
        (win_probability.away.abbreviation, win_probability.away_probability),
        (win_probability.home.abbreviation, win_probability.home_probability),
    ]
    values = [(team, probability) for team, probability in values if probability is not None]
    total = sum(probability for _, probability in values)
    scale = 100 if values and total <= 1.01 else 1
    values = [(team, probability * scale) for team, probability in values]
    values.sort(key=lambda item: item[1], reverse=True)
    return ", ".join(
        f"{irc.team(team)} {irc.value(_format_percent(probability))}"
        for team, probability in values
    )


def _format_win_probability_swing(summary: WinProbabilitySummary) -> str:
    swing = summary.biggest_swing
    if swing is None:
        return irc.muted("not available")
    inning = ""
    if swing.half_inning and swing.inning:
        inning = f" {swing.half_inning.title()} {swing.inning}"
    description = f" - {swing.description}" if swing.description else ""
    return (
        f"{irc.team(swing.team.abbreviation)} "
        f"{irc.value('+' + _format_percent_value(swing.probability_added))}"
        f"{inning}{description}"
    )


def _format_active_pitchers(pitchers: list[PitcherInfo]) -> str:
    return "; ".join(
        f"{irc.team(pitcher.team.abbreviation)} {irc.bold(pitcher.full_name)} "
        f"{_format_pitcher_game_stats(pitcher.game_stats, compact=True)}"
        for pitcher in pitchers
    )


def _top_performer_bits(performers: list[TopPerformer]) -> str:
    return "; ".join(_format_top_performer(performer) for performer in performers)


def _format_top_performer(performer: TopPerformer) -> str:
    team = f"{irc.team(performer.team.abbreviation)} " if performer.team else ""
    stats = (
        _format_batter_game_stats(performer.batting_stats)
        or _format_pitcher_game_stats(performer.pitching_stats, compact=True)
    )
    score = (
        f" {irc.stat_label('GS')} {irc.value(performer.game_score)}"
        if performer.game_score is not None
        else ""
    )
    stats = f" - {stats}" if stats else ""
    return f"{team}{irc.bold(performer.player_name)}{score}{stats}"


def _team_box_line(detail: GameDetail, side: str) -> str:
    team_line = ((_raw_linescore(detail).get("teams") or {}).get(side) or {})
    runs = _display(team_line.get("runs", 0))
    hits = _display(team_line.get("hits", 0))
    errors = _display(team_line.get("errors", 0))
    return irc.value(f"{runs}-{hits}-{errors}")


def _left_on_base(detail: GameDetail) -> str:
    linescore_teams = _raw_linescore(detail).get("teams") or {}
    away_lob = (linescore_teams.get("away") or {}).get("leftOnBase")
    home_lob = (linescore_teams.get("home") or {}).get("leftOnBase")
    if away_lob is None and home_lob is None:
        box_teams = _raw_boxscore(detail).get("teams") or {}
        away_lob = (
            ((box_teams.get("away") or {}).get("teamStats") or {})
            .get("batting", {})
            .get("leftOnBase")
        )
        home_lob = (
            ((box_teams.get("home") or {}).get("teamStats") or {})
            .get("batting", {})
            .get("leftOnBase")
        )
    if away_lob is None and home_lob is None:
        return ""
    game = detail.summary
    return (
        f"{_team_abbr(game.away, home=False)} {irc.value(_display(away_lob or 0))}, "
        f"{_team_abbr(game.home, home=True)} {irc.value(_display(home_lob or 0))}"
    )


def _box_pitcher_bits(groups: list[TeamPitchers]) -> list[str]:
    bits: list[str] = []
    for group in groups:
        if not group.pitchers:
            continue
        pitcher = group.pitchers[-1]
        bits.append(
            f"{irc.team(group.team.abbreviation)} {irc.bold(pitcher.full_name)} "
            f"{_format_pitcher_game_stats(pitcher.game_stats, compact=True)}"
        )
    return bits


def _raw_linescore(detail: GameDetail) -> dict:
    return (
        (detail.raw.get("liveData") or {}).get("linescore")
        or detail.raw.get("linescore")
        or {}
    )


def _raw_boxscore(detail: GameDetail) -> dict:
    return (
        (detail.raw.get("liveData") or {}).get("boxscore")
        or detail.raw.get("boxscore")
        or {}
    )


def _team_stat_period(stats: TeamStats) -> str:
    if stats.start_date and stats.end_date:
        days = (stats.end_date - stats.start_date).days + 1
        period = f"last {days} days"
    else:
        period = str(stats.season)
    if stats.split_label:
        period += f" {stats.split_label}"
    return period


def _format_team_hitting_stats(stat: dict) -> str:
    bits = []
    slash = _slash_line(stat, ("avg", "obp", "slg"))
    if slash:
        ops = _first_value(stat, ("ops",))
        bits.append(
            f"{slash} {irc.stat_label('OPS')} {irc.value(_display(ops))}"
            if ops is not None
            else slash
        )
    bits.extend(
        _counting_stats(
            stat,
            (
                ("runs", "R"),
                ("homeRuns", "HR"),
                ("hits", "H"),
                ("stolenBases", "SB"),
                ("strikeOuts", "K"),
                ("baseOnBalls", "BB"),
            ),
        )
    )
    return ", ".join(bits)


def _format_team_pitching_stats(stat: dict) -> str:
    bits = _labeled_stats(
        stat,
        (
            ("era", "ERA"),
            ("whip", "WHIP"),
            ("inningsPitched", "IP"),
            ("strikeOuts", "K"),
            ("baseOnBalls", "BB"),
            ("homeRuns", "HR"),
            ("strikeoutWalkRatio", "K/BB"),
        ),
    )
    return ", ".join(bits)


def _transaction_bit(transaction: Transaction) -> str:
    if transaction.description:
        bit = transaction.description
    else:
        team = transaction.to_team or transaction.from_team
        team_label = f"{team.abbreviation}: " if team else ""
        bit = f"{team_label}{transaction.player_name} {transaction.type_description}".strip()
    return _truncate_piece(bit, 105)


def _format_percent(value: float) -> str:
    if 0 < value < 1:
        return f"{value:.1f}%"
    return f"{value:.0f}%"


def _format_percent_value(value: float) -> str:
    return f"{value:.1f}%".replace(".0%", "%")


def _probables(game: GameSummary) -> str:
    if not game.away_probable_pitcher and not game.home_probable_pitcher:
        return ""
    away = game.away_probable_pitcher or "TBD"
    home = game.home_probable_pitcher or "TBD"
    return f" ({irc.section('probables')}: {irc.bold(away)} vs {irc.bold(home)})"


def _player_stat_period(stats: PlayerStats) -> str:
    if stats.games_limit is not None:
        period = f"last {stats.games_limit} games"
    elif stats.start_date and stats.end_date:
        days = (stats.end_date - stats.start_date).days + 1
        period = f"last {days} days"
    else:
        period = str(stats.season)
    if stats.split_label:
        period += f" {stats.split_label}"
    return period


def _player_stat_sections(stats: PlayerStats) -> list[str]:
    if stats.group == "pitching":
        return [
            _format_pitching_stats(stats.stats),
            _prefixed_stats(
                "adv",
                stats.advanced_stats,
                (
                    ("strikeoutsPer9", "K/9"),
                    ("baseOnBallsPer9", "BB/9"),
                    ("homeRunsPer9", "HR/9"),
                    ("hitsPer9", "H/9"),
                    (("strikesoutsToWalks", "strikeoutWalkRatio"), "K/BB"),
                    ("pitchesPerInning", "P/IP"),
                    ("whiffPercentage", "Whiff%"),
                ),
            ),
            _prefixed_stats(
                "sabr",
                stats.sabermetric_stats,
                (
                    ("fip", "FIP"),
                    ("xfip", "xFIP"),
                    ("fipMinus", "FIP-"),
                    ("eraMinus", "ERA-"),
                    ("war", "WAR"),
                    ("ra9War", "RA9-WAR"),
                ),
            ),
            _prefixed_stats(
                "exp",
                stats.expected_stats,
                (
                    ("avg", "xAVG"),
                    ("slg", "xSLG"),
                    ("woba", "xwOBA"),
                    ("wobaCon", "xwOBAcon"),
                ),
            ),
        ]
    if stats.group == "fielding":
        return [
            _format_fielding_stats(stats.stats),
            _prefixed_stats(
                "adv",
                stats.advanced_stats,
                (
                    ("catcherCaughtStealingPercentage", "CS%"),
                    ("rangeFactorPerGame", "RF/G"),
                    ("rangeFactorPer9Inn", "RF/9"),
                ),
            ),
        ]
    return [
        _format_hitting_stats(stats.stats),
        _prefixed_stats(
            "adv",
            stats.advanced_stats,
            (
                ("babip", "BABIP"),
                ("iso", "ISO"),
                ("extraBaseHits", "XBH"),
                ("pitchesPerPlateAppearance", "P/PA"),
                ("walksPerPlateAppearance", "BB/PA"),
                ("strikeoutsPerPlateAppearance", "K/PA"),
            ),
        ),
        _prefixed_stats(
            "sabr",
            stats.sabermetric_stats,
            (
                ("woba", "wOBA"),
                ("wRcPlus", "wRC+"),
                ("war", "WAR"),
                ("wRaa", "wRAA"),
                ("baseRunning", "BsR"),
            ),
        ),
        _prefixed_stats(
            "exp",
            stats.expected_stats,
            (
                ("avg", "xAVG"),
                ("slg", "xSLG"),
                ("woba", "xwOBA"),
                ("wobaCon", "xwOBAcon"),
            ),
        ),
    ]


def _format_hitting_stats(stat: dict) -> str:
    bits: list[str] = []
    slash = _slash_line(stat, ("avg", "obp", "slg"))
    if slash:
        ops = _first_value(stat, ("ops",))
        bits.append(
            f"{slash} {irc.stat_label('OPS')} {irc.value(_display(ops))}"
            if ops is not None
            else slash
        )
    bits.extend(
        _counting_stats(
            stat,
            (
                ("homeRuns", "HR"),
                ("rbi", "RBI"),
                ("runs", "R"),
                ("hits", "H"),
                ("stolenBases", "SB"),
                ("plateAppearances", "PA"),
                ("baseOnBalls", "BB"),
                ("strikeOuts", "K"),
            ),
        )
    )
    return ", ".join(bits)


def _format_pitching_stats(stat: dict) -> str:
    bits: list[str] = []
    wins = _first_value(stat, ("wins",))
    losses = _first_value(stat, ("losses",))
    if wins is not None and losses is not None:
        bits.append(irc.value(f"{_display(wins)}-{_display(losses)}"))
    bits.extend(
        _labeled_stats(
            stat,
            (
                ("era", "ERA"),
                ("whip", "WHIP"),
                ("inningsPitched", "IP"),
                ("strikeOuts", "K"),
                ("baseOnBalls", "BB"),
                ("hits", "H"),
                ("earnedRuns", "ER"),
                ("homeRuns", "HR"),
                ("saves", "SV"),
            ),
        )
    )
    return ", ".join(bits)


def _format_batter_game_stats(stat: dict) -> str:
    if not stat:
        return ""
    summary = stat.get("summary")
    if summary:
        return str(summary)
    bits = []
    hits = _first_value(stat, ("hits",))
    at_bats = _first_value(stat, ("atBats",))
    if hits is not None and at_bats is not None:
        bits.append(irc.value(f"{_display(hits)}-{_display(at_bats)}"))
    bits.extend(
        _counting_stats(
            stat,
            (
                ("homeRuns", "HR"),
                ("rbi", "RBI"),
                ("runs", "R"),
                ("hits", "H"),
                ("baseOnBalls", "BB"),
                ("strikeOuts", "K"),
            ),
        )
    )
    return ", ".join(bits)


def _format_fielding_stats(stat: dict) -> str:
    return ", ".join(
        _labeled_stats(
            stat,
            (
                ("gamesPlayed", "G"),
                ("chances", "TC"),
                ("putOuts", "PO"),
                ("assists", "A"),
                ("errors", "E"),
                ("fielding", "FLD"),
            ),
        )
    )


def _prefixed_stats(prefix: str, stat: dict, pairs: tuple) -> str:
    bits = _labeled_stats(stat, pairs)
    return f"{irc.stat_label(prefix)}: " + ", ".join(bits) if bits else ""


def _format_pitcher_listing(pitcher: PitcherInfo) -> str:
    return (
        f"{irc.bold(pitcher.full_name)} "
        f"{_format_pitcher_game_stats(pitcher.game_stats, compact=True)}"
    )


def _format_pitcher_game_stats(stat: dict, *, compact: bool = False) -> str:
    if not stat:
        return irc.muted("no game stats yet")
    pairs = (
        ("inningsPitched", "IP"),
        ("hits", "H"),
        ("runs", "R"),
        ("earnedRuns", "ER"),
        ("baseOnBalls", "BB"),
        ("strikeOuts", "K"),
        (("pitchesThrown", "numberOfPitches"), "pit"),
    )
    bits = _value_labeled_stats(stat, pairs)
    if not bits:
        return irc.muted("no game stats yet")
    return (" " if compact else ", ").join(bits)


def _game_log_bit(group: str, entry: GameLogEntry) -> str:
    date_text = entry.date.isoformat()[5:] if entry.date else "date?"
    opponent = entry.opponent.abbreviation if entry.opponent else "OPP"
    prefix = f"{date_text} {'vs' if entry.is_home else '@'} {irc.team(opponent)}"
    if group == "pitching":
        stat_text = _format_pitcher_game_stats(entry.stats, compact=True)
    else:
        stat_text = _format_batter_game_stats(entry.stats) or _format_hitting_stats(entry.stats)
    return f"{prefix}: {stat_text}"


def _slash_line(stat: dict, keys: tuple[str, str, str]) -> str:
    values = [_first_value(stat, (key,)) for key in keys]
    if not any(value is not None for value in values):
        return ""
    return irc.value("/".join("-" if value is None else _display(value) for value in values))


def _counting_stats(stat: dict, pairs: tuple[tuple[str, str], ...]) -> list[str]:
    bits: list[str] = []
    for key, label in pairs:
        value = _first_value(stat, (key,))
        if value is not None:
            bits.append(f"{irc.value(_display(value))} {irc.stat_label(label)}")
    return bits


def _labeled_stats(stat: dict, pairs: tuple) -> list[str]:
    bits: list[str] = []
    for keys, label in pairs:
        if isinstance(keys, str):
            keys = (keys,)
        value = _first_value(stat, keys)
        if value is not None:
            bits.append(f"{irc.stat_label(label)} {irc.value(_display_labeled(value, label))}")
    return bits


def _value_labeled_stats(stat: dict, pairs: tuple) -> list[str]:
    bits: list[str] = []
    for keys, label in pairs:
        if isinstance(keys, str):
            keys = (keys,)
        value = _first_value(stat, keys)
        if value is not None:
            bits.append(f"{irc.value(_display(value))} {irc.stat_label(label)}")
    return bits


def _first_value(stat: dict, keys: tuple[str, ...]) -> object | None:
    for key in keys:
        value = stat.get(key)
        if value not in (None, ""):
            return value
    return None


def _display(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _display_labeled(value: object, label: str) -> str:
    if not isinstance(value, float):
        return _display(value)
    if label in {"WAR", "RA9-WAR", "RAR", "wRAA", "BsR"}:
        return f"{value:.1f}"
    if label in {"wRC+", "FIP-", "ERA-"}:
        return f"{value:.0f}"
    if label in {"FIP", "xFIP"}:
        return f"{value:.2f}"
    if label in {"wOBA", "xwOBA", "xwOBAcon"}:
        return f"{value:.3f}".lstrip("0")
    return _display(value)


def _compact_time(game: GameSummary, tz: ZoneInfo) -> str:
    if game.game_date is None:
        return "TBD"
    local = game.game_date.astimezone(tz)
    return f"{local.strftime('%I').lstrip('0') or '0'}:{local.strftime('%M%p').lower()}"


def _rank_key(value: str) -> tuple[int, str]:
    try:
        return (int(value), value)
    except ValueError:
        return (999, value)


def _short_group_name(value: str) -> str:
    return (
        value.replace("American League", "AL")
        .replace("National League", "NL")
        .replace(" Division", "")
    )


def _truncate(value: str) -> str:
    return irc.truncate_irc(value, MAX_IRC_LEN)


def _truncate_piece(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."
