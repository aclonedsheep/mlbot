from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

JsonDict = dict[str, Any]


@dataclass(frozen=True)
class TeamInfo:
    id: int | None
    name: str
    abbreviation: str


@dataclass(frozen=True)
class LinescoreSnapshot:
    current_inning: int | None = None
    inning_state: str | None = None
    inning_half: str | None = None
    balls: int | None = None
    strikes: int | None = None
    outs: int | None = None
    runners: tuple[str, ...] = ()


@dataclass(frozen=True)
class GameSummary:
    game_pk: int
    game_date: datetime | None
    official_date: date | None
    status: str
    abstract_state: str
    detailed_state: str
    away: TeamInfo
    home: TeamInfo
    away_score: int | None = None
    home_score: int | None = None
    venue: str | None = None
    away_probable_pitcher: str | None = None
    home_probable_pitcher: str | None = None
    linescore: LinescoreSnapshot | None = None
    series_description: str | None = None
    raw: JsonDict = field(default_factory=dict)

    @property
    def is_live(self) -> bool:
        return self.abstract_state.lower() == "live" or self.status.lower() == "in progress"

    @property
    def is_final(self) -> bool:
        values = {self.abstract_state.lower(), self.status.lower(), self.detailed_state.lower()}
        return bool(values & {"final", "game over", "completed early"})

    @property
    def is_upcoming(self) -> bool:
        return not self.is_live and not self.is_final


@dataclass(frozen=True)
class GameDetail:
    summary: GameSummary
    last_play: str | None = None
    raw: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class PitcherInfo:
    player_id: int | None
    full_name: str
    team: TeamInfo
    game_stats: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class TeamPitchers:
    team: TeamInfo
    pitchers: tuple[PitcherInfo, ...]


@dataclass(frozen=True)
class LineupEntry:
    order: int
    player_id: int | None
    full_name: str
    position: str


@dataclass(frozen=True)
class TeamLineup:
    team: TeamInfo
    entries: tuple[LineupEntry, ...]


@dataclass(frozen=True)
class StandingTeam:
    team_id: int | None
    team_name: str
    abbreviation: str
    league_name: str
    division_name: str
    wins: int
    losses: int
    pct: str
    games_back: str
    wild_card_games_back: str
    division_rank: str
    league_rank: str
    wild_card_rank: str
    streak: str
    last_ten: str


@dataclass(frozen=True)
class PlayerSearchResult:
    person_id: int
    full_name: str
    team_name: str | None = None
    position: str | None = None
    active: bool | None = None


@dataclass(frozen=True)
class PlayerStats:
    player: PlayerSearchResult
    group: str
    season: int
    stats: JsonDict
    advanced_stats: JsonDict = field(default_factory=dict)
    sabermetric_stats: JsonDict = field(default_factory=dict)
    expected_stats: JsonDict = field(default_factory=dict)
    start_date: date | None = None
    end_date: date | None = None


@dataclass(frozen=True)
class Leader:
    rank: str
    value: str
    player_name: str
    team_name: str | None = None
