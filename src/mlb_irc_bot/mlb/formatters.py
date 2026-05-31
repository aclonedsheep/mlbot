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
)

MAX_IRC_LEN = 390


def format_schedule(games: list[GameSummary], target_date: date, tz: ZoneInfo) -> list[str]:
    if not games:
        return [f"MLB {target_date.isoformat()}: no games scheduled."]
    lines = [f"MLB {target_date.isoformat()}: {len(games)} game(s)"]
    lines.extend(_truncate(format_game_summary(game, tz)) for game in games)
    return lines


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


def format_game_detail(detail: GameDetail, tz: ZoneInfo) -> list[str]:
    game = detail.summary
    line = format_game_summary(game, tz)
    lines = [line]
    if detail.last_play:
        lines.append(_truncate(f"Last play: {detail.last_play}"))
    return lines


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

    lines = [title]
    for group_name in sorted(grouped):
        teams = sorted(
            grouped[group_name],
            key=lambda item: _rank_key(item.wild_card_rank if wildcard else item.division_rank),
        )
        bits = []
        for team in teams:
            back = team.wild_card_games_back if wildcard else team.games_back
            rank = team.wild_card_rank if wildcard else team.division_rank
            bits.append(f"{rank}. {team.abbreviation} {team.wins}-{team.losses} ({back} GB)")
        lines.append(_truncate(f"{group_name}: " + "; ".join(bits)))
    return lines


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
    keys = {
        "hitting": ("avg", "homeRuns", "rbi", "runs", "hits", "stolenBases", "ops"),
        "pitching": ("era", "wins", "losses", "strikeOuts", "whip", "inningsPitched"),
        "fielding": ("games", "assists", "putOuts", "errors", "fielding"),
    }.get(stats.group, ())
    if not stats.stats:
        return (
            f"No {stats.group} season stats found for "
            f"{stats.player.full_name} in {stats.season}."
        )
    bits = [f"{key} {stats.stats[key]}" for key in keys if key in stats.stats]
    return _truncate(f"{stats.player.full_name} {stats.season} {stats.group}: " + ", ".join(bits))


def format_leaders(category: str, leaders: list[Leader]) -> str:
    if not leaders:
        return f"No leaders found for {category}."
    bits = [
        f"{leader.rank}. {leader.player_name} {leader.value}"
        + (f" ({leader.team_name})" if leader.team_name else "")
        for leader in leaders
    ]
    return _truncate(f"{category} leaders: " + "; ".join(bits))


def format_current_pitcher(
    game: GameSummary, requested_abbreviation: str, pitcher: PitcherInfo | None
) -> str:
    if pitcher is None:
        return (
            f"{requested_abbreviation}: current pitcher is not available for "
            f"{game.away.abbreviation} vs {game.home.abbreviation} ({game.detailed_state})."
        )
    return _truncate(
        f"{requested_abbreviation} game pitcher: {pitcher.team.abbreviation} "
        f"{pitcher.full_name} ({game.away.abbreviation} vs {game.home.abbreviation}, "
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
    return [
        _truncate(
            f"Pitchers {group.team.abbreviation}: "
            + ", ".join(pitcher.full_name for pitcher in group.pitchers)
        )
        for group in groups
        if group.pitchers
    ]


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


def _probables(game: GameSummary) -> str:
    if not game.away_probable_pitcher and not game.home_probable_pitcher:
        return ""
    away = game.away_probable_pitcher or "TBD"
    home = game.home_probable_pitcher or "TBD"
    return f" (probables: {away} vs {home})"


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


def _truncate(value: str) -> str:
    if len(value) <= MAX_IRC_LEN:
        return value
    return value[: MAX_IRC_LEN - 1].rstrip() + "..."
