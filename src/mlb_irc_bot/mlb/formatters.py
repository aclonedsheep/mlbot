from collections import defaultdict
from datetime import date
from zoneinfo import ZoneInfo

from mlb_irc_bot.mlb.models import GameDetail, GameSummary, Leader, PlayerStats, StandingTeam

MAX_IRC_LEN = 390


def format_schedule(games: list[GameSummary], target_date: date, tz: ZoneInfo) -> list[str]:
    if not games:
        return [f"MLB {target_date.isoformat()}: no games scheduled."]
    lines = [f"MLB {target_date.isoformat()}: {len(games)} game(s)"]
    lines.extend(_truncate(format_game_summary(game, tz)) for game in games)
    return lines


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


def _probables(game: GameSummary) -> str:
    if not game.away_probable_pitcher and not game.home_probable_pitcher:
        return ""
    away = game.away_probable_pitcher or "TBD"
    home = game.home_probable_pitcher or "TBD"
    return f" (probables: {away} vs {home})"


def _rank_key(value: str) -> tuple[int, str]:
    try:
        return (int(value), value)
    except ValueError:
        return (999, value)


def _truncate(value: str) -> str:
    if len(value) <= MAX_IRC_LEN:
        return value
    return value[: MAX_IRC_LEN - 1].rstrip() + "..."
