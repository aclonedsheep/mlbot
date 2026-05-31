from datetime import UTC, date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from mlb_irc_bot.commands import CommandRouter
from mlb_irc_bot.mlb.models import (
    GameDetail,
    GameSummary,
    Leader,
    PlayerSearchResult,
    PlayerStats,
    StandingTeam,
    TeamInfo,
    TeamStats,
    Transaction,
    WinProbability,
)


class FakeClient:
    def __init__(self, games: list[GameSummary] | None = None) -> None:
        self.schedule_calls = []
        self.standings_calls = []
        self.leader_calls = []
        self.stats_calls = []
        self.team_stats_calls = []
        self.transaction_calls = []
        self.games = games

    async def get_schedule(
        self, target_date: date, team_id: int | None = None
    ) -> list[GameSummary]:
        self.schedule_calls.append((target_date, team_id))
        if self.games is not None:
            return [
                game
                for game in self.games
                if team_id is None or team_id in {game.away.id, game.home.id}
            ]
        return [
            GameSummary(
                game_pk=123,
                game_date=datetime(2026, 6, 1, 23, 5, tzinfo=UTC),
                official_date=target_date,
                status="Preview",
                abstract_state="Preview",
                detailed_state="Scheduled",
                away=TeamInfo(id=119, name="Los Angeles Dodgers", abbreviation="LAD"),
                home=TeamInfo(id=147, name="New York Yankees", abbreviation="NYY"),
                venue="Yankee Stadium",
                away_probable_pitcher="Dodger Arm",
                home_probable_pitcher="Yankee Arm",
            )
        ]

    async def get_game_detail(self, game_pk: int) -> GameDetail:
        return _live_detail()

    async def get_win_probability(self, game_pk: int) -> WinProbability:
        return WinProbability(
            away=TeamInfo(id=141, name="Toronto Blue Jays", abbreviation="TOR"),
            home=TeamInfo(id=110, name="Baltimore Orioles", abbreviation="BAL"),
            away_probability=0.9,
            home_probability=99.1,
        )

    async def get_standings(self, *, season: int, standings_type: str, league: str | None):
        self.standings_calls.append((season, standings_type, league))
        records = [
            StandingTeam(
                team_id=147,
                team_name="New York Yankees",
                abbreviation="NYY",
                league_name="American League",
                division_name="AL East",
                wins=34,
                losses=20,
                pct=".630",
                games_back="-",
                wild_card_games_back="+2.0",
                division_rank="1",
                league_rank="1",
                wild_card_rank="1",
                streak="W2",
                last_ten="7-3",
            )
        ]
        if league is None:
            records.append(
                StandingTeam(
                    team_id=119,
                    team_name="Los Angeles Dodgers",
                    abbreviation="LAD",
                    league_name="National League",
                    division_name="NL West",
                    wins=33,
                    losses=21,
                    pct=".611",
                    games_back="-",
                    wild_card_games_back="+1.0",
                    division_rank="1",
                    league_rank="1",
                    wild_card_rank="1",
                    streak="W1",
                    last_ten="6-4",
                )
            )
        return records

    async def search_people(self, name: str):
        if name.lower() == "shohei ohtani":
            return [PlayerSearchResult(660271, "Shohei Ohtani", "Los Angeles Dodgers", "DH", True)]
        if name.lower() == "tarik skubal":
            return [PlayerSearchResult(669373, "Tarik Skubal", "Detroit Tigers", "Pitcher", True)]
        return [
            PlayerSearchResult(1, "John Smith", "A Team", "P", True),
            PlayerSearchResult(2, "John Smith Jr.", "B Team", "CF", True),
        ]

    async def get_player_stats(
        self,
        player: PlayerSearchResult,
        *,
        group: str,
        season: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ):
        self.stats_calls.append((player.full_name, group, season, start_date, end_date))
        if start_date and end_date:
            return PlayerStats(
                player,
                group,
                season,
                {"avg": ".286", "obp": ".400", "slg": ".619", "ops": "1.019", "homeRuns": 2},
                advanced_stats={"iso": ".333", "strikeoutsPerPlateAppearance": ".200"},
                start_date=start_date,
                end_date=end_date,
            )
        if group == "pitching":
            return PlayerStats(
                player,
                group,
                season,
                {
                    "era": "2.70",
                    "whip": "0.95",
                    "wins": 3,
                    "losses": 2,
                    "inningsPitched": "43.1",
                    "strikeOuts": 45,
                },
                advanced_stats={"strikeoutsPer9": "9.35", "baseOnBallsPer9": "1.25"},
                sabermetric_stats={"war": 1.5, "fip": 2.07},
                expected_stats={"avg": ".262", "woba": ".284"},
            )
        return PlayerStats(
            player,
            group,
            season,
            {
                "avg": ".300",
                "obp": ".390",
                "slg": ".600",
                "ops": ".990",
                "homeRuns": 12,
                "rbi": 40,
            },
            advanced_stats={"babip": ".330", "iso": ".300"},
            sabermetric_stats={"wRcPlus": 165, "war": 2.4},
            expected_stats={"avg": ".310", "slg": ".640", "woba": ".420"},
        )

    async def get_leaders(self, category: str, *, season: int, limit: int):
        self.leader_calls.append((category, season, limit))
        return [Leader(rank="1", value="20", player_name="Slugger", team_name="Club")]

    async def get_team_stats(
        self,
        team: TeamInfo,
        *,
        group: str,
        season: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ):
        self.team_stats_calls.append((team.abbreviation, group, season, start_date, end_date))
        if group == "pitching":
            return TeamStats(
                team,
                group,
                season,
                {
                    "era": "3.50",
                    "whip": "1.20",
                    "inningsPitched": "60.0",
                    "strikeOuts": 70,
                    "baseOnBalls": 20,
                    "homeRuns": 8,
                    "strikeoutWalkRatio": "3.50",
                },
                start_date=start_date,
                end_date=end_date,
            )
        return TeamStats(
            team,
            group,
            season,
            {
                "avg": ".250",
                "obp": ".320",
                "slg": ".410",
                "ops": ".730",
                "runs": 42,
                "homeRuns": 11,
                "hits": 80,
                "stolenBases": 6,
            },
            start_date=start_date,
            end_date=end_date,
        )

    async def get_transactions(
        self,
        *,
        start_date: date,
        end_date: date,
        team_id: int | None = None,
    ):
        self.transaction_calls.append((start_date, end_date, team_id))
        return [
            Transaction(
                transaction_id=1,
                date=end_date,
                player_name="Player One",
                type_description="Status Change",
                description="Toronto Blue Jays activated RHP Player One from the injured list.",
                to_team=TeamInfo(id=141, name="Toronto Blue Jays", abbreviation="TOR"),
            ),
            Transaction(
                transaction_id=2,
                date=end_date,
                player_name="Player Two",
                type_description="Assigned",
                description="Toronto Blue Jays optioned RHP Player Two to Buffalo Bisons.",
                from_team=TeamInfo(id=141, name="Toronto Blue Jays", abbreviation="TOR"),
            ),
        ]


def settings() -> SimpleNamespace:
    return SimpleNamespace(command_prefix="@", zoneinfo=lambda: ZoneInfo("America/New_York"))


def fixed_now() -> datetime:
    return datetime(2026, 5, 31, 10, 0, tzinfo=ZoneInfo("America/New_York"))


@pytest.mark.asyncio
async def test_mlb_tomorrow_uses_next_day_schedule() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlb tomorrow")

    assert client.schedule_calls == [(date(2026, 6, 1), None)]
    assert replies == ["MLB 2026-06-01: LAD vs NYY 7:05pm"]


@pytest.mark.asyncio
async def test_mlb_team_tomorrow_uses_team_id() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlb NYY tomorrow")

    assert client.schedule_calls == [(date(2026, 6, 1), 147)]
    assert replies == [
        "LAD @ NYY: 7:05 PM EDT at Yankee Stadium (probables: Dodger Arm vs Yankee Arm)"
    ]


@pytest.mark.asyncio
async def test_mlb_star_returns_only_live_games() -> None:
    client = FakeClient(games=[_live_game(), _final_game(), _upcoming_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlb *")

    assert replies == ["MLB live: TOR 1-2 BAL Top 3, 1 out"]


@pytest.mark.asyncio
async def test_mlb_star_reports_no_live_games() -> None:
    client = FakeClient(games=[_final_game(), _upcoming_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlb *")

    assert replies == ["MLB live: no games live."]


@pytest.mark.asyncio
async def test_mlb_live_team_includes_win_probability_and_active_pitchers() -> None:
    client = FakeClient(games=[_live_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlb TOR")

    assert replies == [
        "TOR @ BAL: TOR 1, BAL 2 Top 3, 1 out | Win: BAL 99%, TOR 0.9% | "
        "P: TOR Spencer Miles 2.1 IP 3 H 1 R 1 ER 1 BB 4 K 46 pit; "
        "BAL Kyle Bradish 3.0 IP 2 H 1 R 1 ER 2 BB 5 K 58 pit"
    ]


@pytest.mark.asyncio
async def test_box_returns_compact_boxscore() -> None:
    client = FakeClient(games=[_live_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@box TOR")

    assert replies == [
        "Box TOR 1-4-0, BAL 2-5-1 Top 3, 1 out | LOB TOR 3, BAL 4 | "
        "Pitching: TOR Reliever One 0.2 IP 0 H 0 R 0 ER 0 BB 1 K 12 pit; "
        "BAL Kyle Bradish 3.0 IP 2 H 1 R 1 ER 2 BB 5 K 58 pit"
    ]


@pytest.mark.asyncio
async def test_mlb_pitcher_shows_current_team_pitcher() -> None:
    client = FakeClient(games=[_live_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlbpitcher TOR")

    assert replies == [
        "TOR game pitcher: TOR Spencer Miles - 2.1 IP, 3 H, 1 R, 1 ER, "
        "1 BB, 4 K, 46 pit (TOR vs BAL, In Progress)"
    ]


@pytest.mark.asyncio
async def test_mlb_pitchers_shows_all_game_pitchers() -> None:
    client = FakeClient(games=[_live_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlbpitchers TOR")

    assert replies == [
        "Pitchers: TOR: Spencer Miles 2.1 IP 3 H 1 R 1 ER 1 BB 4 K 46 pit; "
        "Reliever One 0.2 IP 0 H 0 R 0 ER 0 BB 1 K 12 pit | "
        "BAL: Kyle Bradish 3.0 IP 2 H 1 R 1 ER 2 BB 5 K 58 pit",
    ]


@pytest.mark.asyncio
async def test_mlb_lineup_shows_requested_team_lineup() -> None:
    client = FakeClient(games=[_live_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlblineup TOR")

    assert replies == [
        "TOR lineup: 1. Nathan Lukes LF; 2. Vladimir Guerrero Jr. DH"
    ]


@pytest.mark.asyncio
async def test_wildcard_command_requests_wildcard_standings() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@wildcard AL")

    assert client.standings_calls == [(2026, "wildCard", "AL")]
    assert replies == ["AL wildcard standings: 1. NYY 34-20 +2.0 GB"]


@pytest.mark.asyncio
async def test_wildcard_default_returns_both_leagues() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@wildcard")

    assert client.standings_calls == [(2026, "wildCard", None)]
    assert replies == [
        "Wildcard standings: AL: 1. NYY 34-20 +2.0 GB | "
        "NL: 1. LAD 33-21 +1.0 GB"
    ]


@pytest.mark.asyncio
async def test_sstats_returns_candidates_for_ambiguous_player() -> None:
    router = CommandRouter(client=FakeClient(), settings=settings(), now=fixed_now)

    replies = await router.handle_message("@sstats John")

    assert replies == [
        "Multiple players matched: John Smith (A Team, P); John Smith Jr. (B Team, CF)"
    ]


@pytest.mark.asyncio
async def test_sstats_formats_advanced_season_stats() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@sstats Shohei Ohtani")

    assert client.stats_calls == [("Shohei Ohtani", "hitting", 2026, None, None)]
    assert replies == [
        "Shohei Ohtani 2026 hitting: .300/.390/.600 OPS .990, 12 HR, 40 RBI | "
        "adv: BABIP .330, ISO .300 | sabr: wRC+ 165, WAR 2.4 | "
        "exp: xAVG .310, xSLG .640, xwOBA .420"
    ]


@pytest.mark.asyncio
async def test_sstats_accepts_day_window() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@sstats Shohei Ohtani hitting 7 days")

    assert client.stats_calls == [
        ("Shohei Ohtani", "hitting", 2026, date(2026, 5, 25), date(2026, 5, 31))
    ]
    assert replies == [
        "Shohei Ohtani last 7 days hitting: .286/.400/.619 OPS 1.019, 2 HR | "
        "adv: ISO .333, K/PA .200"
    ]


@pytest.mark.asyncio
async def test_sstats_defaults_pitchers_to_pitching_stats() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@sstats Tarik Skubal")

    assert client.stats_calls == [("Tarik Skubal", "pitching", 2026, None, None)]
    assert replies == [
        "Tarik Skubal 2026 pitching: 3-2, ERA 2.70, WHIP 0.95, IP 43.1, "
        "K 45 | adv: K/9 9.35, BB/9 1.25 | sabr: FIP 2.07, WAR 1.5 | "
        "exp: xAVG .262, xwOBA .284"
    ]


@pytest.mark.asyncio
async def test_sstats_respects_explicit_group_for_pitcher() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    await router.handle_message("@sstats Tarik Skubal hitting")

    assert client.stats_calls == [("Tarik Skubal", "hitting", 2026, None, None)]


@pytest.mark.asyncio
async def test_leaders_normalizes_category_alias() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@leaders hr 3")

    assert client.leader_calls == [("homeRuns", 2026, 3)]
    assert replies == ["homeRuns leaders: 1. Slugger 20 (Club)"]


@pytest.mark.asyncio
async def test_teamstats_defaults_to_hitting_and_pitching() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@teamstats TOR")

    assert client.team_stats_calls == [
        ("TOR", "hitting", 2026, None, None),
        ("TOR", "pitching", 2026, None, None),
    ]
    assert replies == [
        "TOR teamstats 2026: hit: .250/.320/.410 OPS .730, 42 R, 11 HR, "
        "80 H, 6 SB | pitch: ERA 3.50, WHIP 1.20, IP 60.0, K 70, "
        "BB 20, HR 8, K/BB 3.50"
    ]


@pytest.mark.asyncio
async def test_teamstats_accepts_group_and_day_window() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@teamstats TOR hitting 7 days")

    assert client.team_stats_calls == [
        ("TOR", "hitting", 2026, date(2026, 5, 25), date(2026, 5, 31))
    ]
    assert replies == [
        "TOR teamstats last 7 days: hit: .250/.320/.410 OPS .730, 42 R, "
        "11 HR, 80 H, 6 SB"
    ]


@pytest.mark.asyncio
async def test_transactions_defaults_to_today() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@transactions")

    assert client.transaction_calls == [(date(2026, 5, 31), date(2026, 5, 31), None)]
    assert replies == [
        "MLB transactions 2026-05-31: "
        "Toronto Blue Jays activated RHP Player One from the injured list.; "
        "Toronto Blue Jays optioned RHP Player Two to Buffalo Bisons."
    ]


@pytest.mark.asyncio
async def test_transactions_accepts_team_and_day_window() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@transactions TOR 7 days")

    assert client.transaction_calls == [(date(2026, 5, 25), date(2026, 5, 31), 141)]
    assert replies[0].startswith("TOR transactions 2026-05-25..2026-05-31:")


def _live_game() -> GameSummary:
    return GameSummary(
        game_pk=824832,
        game_date=datetime(2026, 5, 31, 17, 35, tzinfo=UTC),
        official_date=date(2026, 5, 31),
        status="Live",
        abstract_state="Live",
        detailed_state="In Progress",
        away=TeamInfo(id=141, name="Toronto Blue Jays", abbreviation="TOR"),
        home=TeamInfo(id=110, name="Baltimore Orioles", abbreviation="BAL"),
        away_score=1,
        home_score=2,
        linescore=SimpleNamespace(
            current_inning=3,
            inning_half="Top",
            balls=None,
            strikes=None,
            outs=1,
            runners=(),
        ),
    )


def _final_game() -> GameSummary:
    return GameSummary(
        game_pk=1,
        game_date=datetime(2026, 5, 31, 16, 0, tzinfo=UTC),
        official_date=date(2026, 5, 31),
        status="Final",
        abstract_state="Final",
        detailed_state="Final",
        away=TeamInfo(id=119, name="Los Angeles Dodgers", abbreviation="LAD"),
        home=TeamInfo(id=147, name="New York Yankees", abbreviation="NYY"),
        away_score=5,
        home_score=4,
    )


def _upcoming_game() -> GameSummary:
    return GameSummary(
        game_pk=2,
        game_date=datetime(2026, 5, 31, 23, 5, tzinfo=UTC),
        official_date=date(2026, 5, 31),
        status="Preview",
        abstract_state="Preview",
        detailed_state="Scheduled",
        away=TeamInfo(id=136, name="Seattle Mariners", abbreviation="SEA"),
        home=TeamInfo(id=135, name="San Diego Padres", abbreviation="SD"),
    )


def _live_detail() -> GameDetail:
    return GameDetail(
        summary=_live_game(),
        raw={
            "gameData": {
                "teams": {
                    "away": {"id": 141, "name": "Toronto Blue Jays", "abbreviation": "TOR"},
                    "home": {"id": 110, "name": "Baltimore Orioles", "abbreviation": "BAL"},
                }
            },
            "liveData": {
                "linescore": {
                    "teams": {
                        "away": {"runs": 1, "hits": 4, "errors": 0, "leftOnBase": 3},
                        "home": {"runs": 2, "hits": 5, "errors": 1, "leftOnBase": 4},
                    },
                    "offense": {
                        "team": {"id": 141, "name": "Toronto Blue Jays"},
                        "pitcher": {"id": 693686, "fullName": "Spencer Miles"},
                    },
                    "defense": {
                        "team": {"id": 110, "name": "Baltimore Orioles"},
                        "pitcher": {"id": 680694, "fullName": "Kyle Bradish"},
                    },
                },
                "boxscore": {
                    "teams": {
                        "away": {
                            "team": {"id": 141, "name": "Toronto Blue Jays"},
                            "battingOrder": [664770, 665489],
                            "pitchers": [693686, 123456],
                            "players": {
                                "ID664770": {
                                    "person": {"id": 664770, "fullName": "Nathan Lukes"},
                                    "position": {"abbreviation": "LF"},
                                },
                                "ID665489": {
                                    "person": {
                                        "id": 665489,
                                        "fullName": "Vladimir Guerrero Jr.",
                                    },
                                    "position": {"abbreviation": "DH"},
                                },
                                "ID693686": {
                                    "person": {"id": 693686, "fullName": "Spencer Miles"},
                                    "stats": {
                                        "pitching": {
                                            "inningsPitched": "2.1",
                                            "hits": 3,
                                            "runs": 1,
                                            "earnedRuns": 1,
                                            "baseOnBalls": 1,
                                            "strikeOuts": 4,
                                            "pitchesThrown": 46,
                                        }
                                    },
                                },
                                "ID123456": {
                                    "person": {"id": 123456, "fullName": "Reliever One"},
                                    "stats": {
                                        "pitching": {
                                            "inningsPitched": "0.2",
                                            "hits": 0,
                                            "runs": 0,
                                            "earnedRuns": 0,
                                            "baseOnBalls": 0,
                                            "strikeOuts": 1,
                                            "pitchesThrown": 12,
                                        }
                                    },
                                },
                            },
                        },
                        "home": {
                            "team": {"id": 110, "name": "Baltimore Orioles"},
                            "battingOrder": [],
                            "pitchers": [680694],
                            "players": {
                                "ID680694": {
                                    "person": {"id": 680694, "fullName": "Kyle Bradish"},
                                    "stats": {
                                        "pitching": {
                                            "inningsPitched": "3.0",
                                            "hits": 2,
                                            "runs": 1,
                                            "earnedRuns": 1,
                                            "baseOnBalls": 2,
                                            "strikeOuts": 5,
                                            "pitchesThrown": 58,
                                        }
                                    },
                                }
                            },
                        },
                    }
                },
            },
        },
    )
