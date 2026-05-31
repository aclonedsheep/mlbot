from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from mlb_irc_bot.mlb.models import (
    GameDetail,
    GameSummary,
    Leader,
    PitcherInfo,
    PlayerStats,
    StandingTeam,
    TeamLineup,
    TeamPitchers,
    TeamStats,
    Transaction,
    WinProbability,
)

MAX_IRC_LEN = 390


def format_schedule(games: list[GameSummary], target_date: date, tz: ZoneInfo) -> list[str]:
    if not games:
        return [f"MLB {target_date.isoformat()}: no games scheduled."]
    bits = [format_game_summary(game, tz) for game in games]
    return [_truncate(f"MLB {target_date.isoformat()}: " + "; ".join(bits))]


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
            return [f"{title}: no games live."]
    else:
        title = f"MLB {target_date.isoformat()}"
        if not games:
            return [f"{title}: no games scheduled."]

    games = sorted(games, key=lambda game: game.game_date or datetime.max.replace(tzinfo=tz))
    bits = [format_compact_game(game, tz) for game in games]
    return [_truncate(f"{title}: " + "; ".join(bits))]


def format_compact_game(game: GameSummary, tz: ZoneInfo) -> str:
    if game.is_final:
        return (
            f"{game.away.abbreviation} {game.away_score}-{game.home_score} "
            f"{game.home.abbreviation} F"
        )
    if game.is_live:
        state = format_linescore(game) or game.detailed_state or "Live"
        return (
            f"{game.away.abbreviation} {game.away_score}-{game.home_score} "
            f"{game.home.abbreviation} {state}"
        )
    return f"{game.away.abbreviation} vs {game.home.abbreviation} {_compact_time(game, tz)}"


def format_game_summary(game: GameSummary, tz: ZoneInfo) -> str:
    matchup = f"{game.away.abbreviation} @ {game.home.abbreviation}"
    if game.is_live:
        return f"{matchup}: {score(game)} {format_linescore(game)}"
    if game.is_final:
        return f"{matchup}: Final {score(game)}"
    when = "TBD"
    if game.game_date is not None:
        local = game.game_date.astimezone(tz)
        when = f"{local.strftime('%I').lstrip('0') or '0'}:{local.strftime('%M %p %Z')}"
    probables = _probables(game)
    venue = f" at {game.venue}" if game.venue else ""
    return f"{matchup}: {when}{venue}{probables}"


def format_game_detail(
    detail: GameDetail,
    tz: ZoneInfo,
    *,
    win_probability: WinProbability | None = None,
    active_pitchers: list[PitcherInfo] | None = None,
) -> list[str]:
    game = detail.summary
    line = format_game_summary(game, tz)
    if win_probability:
        line += f" | Win: {_format_win_probability(win_probability)}"
    if active_pitchers:
        line += f" | P: {_format_active_pitchers(active_pitchers)}"
    if detail.last_play:
        line += f" | Last play: {detail.last_play}"
    return [_truncate(line)]


def format_linescore(game: GameSummary) -> str:
    linescore = game.linescore
    if not linescore:
        return game.detailed_state or game.status
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
    return f"{inning}{outs}{count}{runners}".strip(", ")


def score(game: GameSummary) -> str:
    away_score = "-" if game.away_score is None else str(game.away_score)
    home_score = "-" if game.home_score is None else str(game.home_score)
    return f"{game.away.abbreviation} {away_score}, {game.home.abbreviation} {home_score}"


def format_standings(
    records: list[StandingTeam], *, title: str, wildcard: bool = False
) -> list[str]:
    if not records:
        return [f"{title}: no standings available."]
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
            bits.append(f"{rank}. {team.abbreviation} {team.wins}-{team.losses} {back} GB")
        if len(teams) > len(display_teams):
            bits.append(f"+{len(teams) - len(display_teams)} more")
        group_lines.append(f"{_short_group_name(group_name)}: " + ", ".join(bits))
    if len(group_lines) == 1:
        _, _, only_group = group_lines[0].partition(": ")
        return [_truncate(f"{title}: {only_group}")]
    return [_truncate(f"{title}: " + " | ".join(group_lines))]


def format_team_standing(record: StandingTeam) -> str:
    return _truncate(
        f"{record.abbreviation}: {record.wins}-{record.losses} "
        f"({record.pct}), {record.division_name} rank {record.division_rank}, "
        f"WC rank {record.wild_card_rank or '-'} ({record.wild_card_games_back} GB), "
        f"L10 {record.last_ten}, streak {record.streak or '-'}"
    )


def format_player_candidates(candidates: list[str]) -> str:
    return "Multiple players matched: " + "; ".join(candidates)


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
            f"No {stats.group} stats found for "
            f"{stats.player.full_name} {period}."
        )
    sections = [section for section in _player_stat_sections(stats) if section]
    return _truncate(
        f"{stats.player.full_name} {period} {stats.group}: "
        + " | ".join(sections)
    )


def format_leaders(category: str, leaders: list[Leader]) -> str:
    if not leaders:
        return f"No leaders found for {category}."
    bits = [
        f"{leader.rank}. {leader.player_name} {leader.value}"
        + (f" ({leader.team_name})" if leader.team_name else "")
        for leader in leaders
    ]
    return _truncate(f"{category} leaders: " + "; ".join(bits))


def format_boxscore(detail: GameDetail, pitcher_groups: list[TeamPitchers]) -> str:
    game = detail.summary
    away_line = _team_box_line(detail, "away")
    home_line = _team_box_line(detail, "home")
    state = "F" if game.is_final else (format_linescore(game) or game.detailed_state)
    bits = [
        f"Box {game.away.abbreviation} {away_line}, "
        f"{game.home.abbreviation} {home_line} {state}".strip()
    ]
    left_on_base = _left_on_base(detail)
    if left_on_base:
        bits.append("LOB " + left_on_base)
    pitcher_bits = _box_pitcher_bits(pitcher_groups)
    if pitcher_bits:
        bits.append("Pitching: " + "; ".join(pitcher_bits))
    return _truncate(" | ".join(bits))


def format_team_stats(stats_list: list[TeamStats]) -> str:
    if not stats_list:
        return "No team stats found."
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
            sections.append(f"{prefix}: {section}")
    if not sections:
        return f"No team stats found for {team.abbreviation} {period}."
    return _truncate(f"{team.abbreviation} teamstats {period}: " + " | ".join(sections))


def format_transactions(
    transactions: list[Transaction],
    *,
    title: str,
    limit: int = 5,
) -> str:
    if not transactions:
        return f"{title}: no transactions found."
    display = transactions[:limit]
    bits = [_transaction_bit(transaction) for transaction in display]
    if len(transactions) > limit:
        bits.append(f"+{len(transactions) - limit} more")
    return _truncate(f"{title}: " + "; ".join(bits))


def format_current_pitcher(
    game: GameSummary, requested_abbreviation: str, pitcher: PitcherInfo | None
) -> str:
    if pitcher is None:
        return (
            f"{requested_abbreviation}: current pitcher is not available for "
            f"{game.away.abbreviation} vs {game.home.abbreviation} ({game.detailed_state})."
        )
    pitching_line = _format_pitcher_game_stats(pitcher.game_stats)
    return _truncate(
        f"{requested_abbreviation} game pitcher: {pitcher.team.abbreviation} "
        f"{pitcher.full_name} - {pitching_line} "
        f"({game.away.abbreviation} vs {game.home.abbreviation}, "
        f"{game.detailed_state or game.status})"
    )


def format_probable_pitchers(game: GameSummary) -> str:
    away = game.away_probable_pitcher or "TBD"
    home = game.home_probable_pitcher or "TBD"
    return _truncate(
        f"Probable pitchers {game.away.abbreviation} vs {game.home.abbreviation}: "
        f"{game.away.abbreviation} {away}; {game.home.abbreviation} {home}"
    )


def format_pitchers(groups: list[TeamPitchers], game: GameSummary) -> list[str]:
    if not groups or not any(group.pitchers for group in groups):
        return [
            f"Pitchers are not available yet for "
            f"{game.away.abbreviation} vs {game.home.abbreviation}."
        ]
    bits = [
        f"{group.team.abbreviation}: "
        + "; ".join(_format_pitcher_listing(pitcher) for pitcher in group.pitchers)
        for group in groups
        if group.pitchers
    ]
    return [_truncate("Pitchers: " + " | ".join(bits))]


def format_lineup(lineup: TeamLineup | None, game: GameSummary, requested_abbreviation: str) -> str:
    if lineup is None or not lineup.entries:
        return (
            f"{requested_abbreviation} lineup is not available for "
            f"{game.away.abbreviation} vs {game.home.abbreviation}."
        )
    bits = [
        f"{entry.order}. {entry.full_name} {entry.position}".strip()
        for entry in lineup.entries
    ]
    return _truncate(f"{lineup.team.abbreviation} lineup: " + "; ".join(bits))


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
    return ", ".join(f"{team} {_format_percent(probability)}" for team, probability in values)


def _format_active_pitchers(pitchers: list[PitcherInfo]) -> str:
    return "; ".join(
        f"{pitcher.team.abbreviation} {pitcher.full_name} "
        f"{_format_pitcher_game_stats(pitcher.game_stats, compact=True)}"
        for pitcher in pitchers
    )


def _team_box_line(detail: GameDetail, side: str) -> str:
    team_line = ((_raw_linescore(detail).get("teams") or {}).get(side) or {})
    runs = _display(team_line.get("runs", 0))
    hits = _display(team_line.get("hits", 0))
    errors = _display(team_line.get("errors", 0))
    return f"{runs}-{hits}-{errors}"


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
        f"{game.away.abbreviation} {_display(away_lob or 0)}, "
        f"{game.home.abbreviation} {_display(home_lob or 0)}"
    )


def _box_pitcher_bits(groups: list[TeamPitchers]) -> list[str]:
    bits: list[str] = []
    for group in groups:
        if not group.pitchers:
            continue
        pitcher = group.pitchers[-1]
        bits.append(
            f"{group.team.abbreviation} {pitcher.full_name} "
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
        return f"last {days} days"
    return str(stats.season)


def _format_team_hitting_stats(stat: dict) -> str:
    bits = []
    slash = _slash_line(stat, ("avg", "obp", "slg"))
    if slash:
        ops = _first_value(stat, ("ops",))
        bits.append(f"{slash} OPS {_display(ops)}" if ops is not None else slash)
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


def _probables(game: GameSummary) -> str:
    if not game.away_probable_pitcher and not game.home_probable_pitcher:
        return ""
    away = game.away_probable_pitcher or "TBD"
    home = game.home_probable_pitcher or "TBD"
    return f" (probables: {away} vs {home})"


def _player_stat_period(stats: PlayerStats) -> str:
    if stats.start_date and stats.end_date:
        days = (stats.end_date - stats.start_date).days + 1
        return f"last {days} days"
    return str(stats.season)


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
        bits.append(f"{slash} OPS {_display(ops)}" if ops is not None else slash)
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
        bits.append(f"{_display(wins)}-{_display(losses)}")
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
    return f"{prefix}: " + ", ".join(bits) if bits else ""


def _format_pitcher_listing(pitcher: PitcherInfo) -> str:
    return f"{pitcher.full_name} {_format_pitcher_game_stats(pitcher.game_stats, compact=True)}"


def _format_pitcher_game_stats(stat: dict, *, compact: bool = False) -> str:
    if not stat:
        return "no game stats yet"
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
        return "no game stats yet"
    return (" " if compact else ", ").join(bits)


def _slash_line(stat: dict, keys: tuple[str, str, str]) -> str:
    values = [_first_value(stat, (key,)) for key in keys]
    if not any(value is not None for value in values):
        return ""
    return "/".join("-" if value is None else _display(value) for value in values)


def _counting_stats(stat: dict, pairs: tuple[tuple[str, str], ...]) -> list[str]:
    bits: list[str] = []
    for key, label in pairs:
        value = _first_value(stat, (key,))
        if value is not None:
            bits.append(f"{_display(value)} {label}")
    return bits


def _labeled_stats(stat: dict, pairs: tuple) -> list[str]:
    bits: list[str] = []
    for keys, label in pairs:
        if isinstance(keys, str):
            keys = (keys,)
        value = _first_value(stat, keys)
        if value is not None:
            bits.append(f"{label} {_display_labeled(value, label)}")
    return bits


def _value_labeled_stats(stat: dict, pairs: tuple) -> list[str]:
    bits: list[str] = []
    for keys, label in pairs:
        if isinstance(keys, str):
            keys = (keys,)
        value = _first_value(stat, keys)
        if value is not None:
            bits.append(f"{_display(value)} {label}")
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
    if len(value) <= MAX_IRC_LEN:
        return value
    return value[: MAX_IRC_LEN - 1].rstrip() + "..."


def _truncate_piece(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."
