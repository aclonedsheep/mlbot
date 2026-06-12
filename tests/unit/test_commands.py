from datetime import UTC, date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from mlb_irc_bot.commands import CommandRouter
from mlb_irc_bot.irc_format import BOLD, COLOR, ITALIC, strip_irc_formatting
from mlb_irc_bot.mlb.formatters import MAX_IRC_LEN, format_leaders
from mlb_irc_bot.mlb.models import (
    GameDetail,
    GameHighlight,
    GameLogEntry,
    GameSummary,
    Leader,
    PitchArsenalEntry,
    PlayerSearchResult,
    PlayerStats,
    SavantLeaderboardRow,
    StandingTeam,
    TeamInfo,
    TeamLeaderGroup,
    TeamRanking,
    TeamStats,
    Transaction,
    WinProbability,
    WinProbabilitySummary,
    WinProbabilitySwing,
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

    async def get_win_probability_summary(
        self, game_pk: int, game: GameSummary
    ) -> WinProbabilitySummary:
        return WinProbabilitySummary(
            current=WinProbability(
                away=game.away,
                home=game.home,
                away_probability=35.0,
                home_probability=65.0,
            ),
            biggest_swing=WinProbabilitySwing(
                team=game.home,
                probability_added=18.4,
                description="Clutch hit scores two.",
                inning=8,
                half_inning="bottom",
            ),
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
        if standings_type == "regularSeason" and league is None:
            records.extend(
                [
                    StandingTeam(
                        team_id=141,
                        team_name="Toronto Blue Jays",
                        abbreviation="TOR",
                        league_name="American League",
                        division_name="AL East",
                        wins=31,
                        losses=26,
                        pct=".544",
                        games_back="4.5",
                        wild_card_games_back="1.0",
                        division_rank="3",
                        league_rank="6",
                        wild_card_rank="3",
                        streak="W1",
                        last_ten="6-4",
                    ),
                    StandingTeam(
                        team_id=110,
                        team_name="Baltimore Orioles",
                        abbreviation="BAL",
                        league_name="American League",
                        division_name="AL East",
                        wins=28,
                        losses=30,
                        pct=".483",
                        games_back="8.0",
                        wild_card_games_back="4.5",
                        division_rank="4",
                        league_rank="9",
                        wild_card_rank="7",
                        streak="L2",
                        last_ten="4-6",
                    ),
                ]
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
        games_limit: int | None = None,
    ):
        self.stats_calls.append((player.full_name, group, season, start_date, end_date))
        if games_limit is not None:
            return PlayerStats(
                player,
                group,
                season,
                {
                    "avg": ".400",
                    "obp": ".455",
                    "slg": ".800",
                    "ops": "1.255",
                    "homeRuns": 3,
                },
                games_limit=games_limit,
            )
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

    async def get_player_split_stats(
        self,
        player: PlayerSearchResult,
        *,
        group: str,
        season: int,
        situation_code: str,
        situation_label: str,
    ):
        return PlayerStats(
            player,
            group,
            season,
            {"avg": ".333", "obp": ".444", "slg": ".667", "ops": "1.111", "rbi": 12},
            split_label=situation_label,
        )

    async def get_player_game_log(
        self,
        player: PlayerSearchResult,
        *,
        group: str,
        season: int,
        limit: int,
    ):
        return [
            GameLogEntry(
                date=date(2026, 5, 31),
                opponent=TeamInfo(id=110, name="Baltimore Orioles", abbreviation="BAL"),
                is_home=False,
                stats={"summary": "2-4 | HR, 3 RBI"},
            ),
            GameLogEntry(
                date=date(2026, 5, 30),
                opponent=TeamInfo(id=110, name="Baltimore Orioles", abbreviation="BAL"),
                is_home=True,
                stats={"summary": "1-3 | BB"},
            ),
        ][:limit]

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
        situation_code: str | None = None,
        situation_label: str | None = None,
    ):
        self.team_stats_calls.append((team.abbreviation, group, season, start_date, end_date))
        if situation_code:
            return TeamStats(
                team,
                group,
                season,
                {
                    "avg": ".300",
                    "obp": ".380",
                    "slg": ".500",
                    "ops": ".880",
                    "runs": 22,
                    "homeRuns": 5,
                },
                split_label=situation_label,
            )
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

    async def get_team_rankings(
        self,
        category: str,
        *,
        season: int,
        group: str | None = None,
        limit: int,
    ):
        return [
            TeamRanking(
                rank="1",
                team=TeamInfo(id=141, name="Toronto Blue Jays", abbreviation="TOR"),
                value=".800",
            ),
            TeamRanking(
                rank="2",
                team=TeamInfo(id=110, name="Baltimore Orioles", abbreviation="BAL"),
                value=".760",
            ),
        ][:limit]

    async def get_team_leaders(
        self,
        team: TeamInfo,
        *,
        categories: list[str],
        season: int,
        limit: int,
    ):
        return [
            TeamLeaderGroup(
                category=categories[0],
                leaders=(Leader("1", "12", "Team Slugger", team.abbreviation),),
            )
        ]

    async def get_player_defense(self, player: PlayerSearchResult, *, season: int):
        return PlayerStats(
            player,
            "fielding",
            season,
            {
                "totalOutsAboveAverage": 5,
                "fieldingRunsPrevented": 4,
                "attempts": 80,
            },
        )

    async def get_pitch_arsenal(self, player: PlayerSearchResult, *, season: int):
        return [
            PitchArsenalEntry("Four-Seam Fastball", count=120, percentage=55.5, average_speed=96.4),
            PitchArsenalEntry("Slider", count=70, percentage=32.1, average_speed=86.2),
        ]

    async def get_savant_percentiles(self, player: PlayerSearchResult, *, season: int):
        return SavantLeaderboardRow(
            player,
            season,
            "percentiles",
            {
                "percent_rank_xwoba": 98,
                "percent_rank_xslg": 96,
                "percent_rank_exit_velocity_avg": 96,
                "percent_rank_hard_hit_percent": 95,
                "percent_rank_barrel": 95,
                "percent_rank_bb_percent": 94,
                "percent_rank_k_percent": 61,
                "percent_rank_sprint_speed": 56,
                "percent_rank_swing_speed": 79,
            },
        )

    async def get_savant_expected_stats(self, player: PlayerSearchResult, *, season: int):
        return SavantLeaderboardRow(
            player,
            season,
            "expected stats",
            {
                "est_ba": ".310",
                "est_slg": ".640",
                "est_woba": ".420",
                "exit_velocity_avg": 94.2,
                "exit_velocity_max": 119.1,
                "hard_hit_percent": 57.4,
                "barrels_per_bip": 22.8,
                "barrels_per_pa": 13.1,
                "sweet_spot_percent": 38.6,
            },
        )

    async def get_savant_sprint_speed(self, player: PlayerSearchResult, *, season: int):
        return SavantLeaderboardRow(
            player,
            season,
            "sprint speed",
            {
                "r_sprint_speed_top50percent_pretty": "28.7",
                "n_bolts": 9,
                "hp_to_1b": 4.19,
                "speed_order": 72,
            },
        )

    async def get_savant_bat_tracking(self, player: PlayerSearchResult, *, season: int):
        return SavantLeaderboardRow(
            player,
            season,
            "bat tracking",
            {
                "avg_sweetspot_speed_mph": 75.8,
                "attack_angle": 13.4,
                "swing_length": 7.9,
                "squared_up_per_bat_contact": 0.348,
                "rate_ideal_attack_angle": 0.584,
                "delta_run_exp": 9.6,
                "count": 284,
            },
        )

    async def get_savant_run_value(self, player: PlayerSearchResult, *, season: int):
        return SavantLeaderboardRow(
            player,
            season,
            "batting run value",
            {
                "runs_all": 16.8,
                "runs_heart": 6.2,
                "runs_shadow": -3.0,
                "runs_chase": 8.0,
                "runs_waste": 5.5,
                "pa": 297,
                "pitches": 1283,
            },
        )

    async def get_savant_fielding_run_value(self, player: PlayerSearchResult, *, season: int):
        return SavantLeaderboardRow(
            player,
            season,
            "fielding run value",
            {
                "total_runs": 13.1,
                "range_runs": 10.4,
                "arm_runs": 2.7,
                "dp_runs": 0.0,
                "outs_total": 1777,
            },
        )

    async def get_savant_baserunning_run_value(
        self, player: PlayerSearchResult, *, season: int
    ):
        return SavantLeaderboardRow(
            player,
            season,
            "baserunning run value",
            {
                "runner_runs_tot": 4.0,
                "runner_runs_SBX": 3.4,
                "runner_runs_XB": 0.7,
                "N_runner_moved": 88,
                "N_runner_moved_XB": 42,
            },
        )

    async def get_savant_arm_strength(self, player: PlayerSearchResult, *, season: int):
        return SavantLeaderboardRow(
            player,
            season,
            "arm strength",
            {
                "arm_overall": 87.3,
                "max_arm_strength": 94.1,
                "total_throws": 157,
                "primary_pos_name_short": "OF",
            },
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

    async def get_game_highlights(self, game_pk: int, *, limit: int | None, tag: str | None = None):
        highlights = [
            GameHighlight(
                title="Condensed Game: TOR@BAL",
                url="https://clips.example/condensed.mp4",
                duration="00:08:42",
                page_url="https://www.mlb.com/video/condensed-game-tor-bal",
                tags=("condensed",),
            ),
            GameHighlight(
                title="Vladimir Guerrero Jr.'s go-ahead homer",
                url="https://clips.example/vlad-go-ahead-homer.mp4",
                duration="00:00:42",
                page_url="https://www.mlb.com/video/vlad-go-ahead-homer",
                tags=("scoring", "homers"),
            ),
            GameHighlight(
                title="Blue Jays turn two",
                url="https://clips.example/jays-turn-two.mp4",
                duration="00:00:28",
                page_url="https://www.mlb.com/video/jays-turn-two",
                tags=("defense",),
            ),
            GameHighlight(
                title="Andres Gimenez's RBI double",
                url="https://clips.example/gimenez-rbi-double.mp4",
                duration="00:00:20",
                page_url="https://www.mlb.com/video/gimenez-rbi-double",
                tags=("scoring",),
            ),
            GameHighlight(
                title="Manager talks after the win",
                url="https://clips.example/manager-talks.mp4",
                duration="00:01:45",
                page_url="https://www.mlb.com/video/manager-talks",
                tags=("interviews",),
            ),
        ]
        if tag:
            highlights = [highlight for highlight in highlights if tag in highlight.tags]
        return highlights if limit is None else highlights[:limit]


def settings() -> SimpleNamespace:
    return SimpleNamespace(command_prefix="@", zoneinfo=lambda: ZoneInfo("America/New_York"))


def fixed_now() -> datetime:
    return datetime(2026, 5, 31, 10, 0, tzinfo=ZoneInfo("America/New_York"))


def _plain(replies: list[str] | None) -> list[str] | None:
    if replies is None:
        return None
    return [strip_irc_formatting(reply) for reply in replies]


@pytest.mark.asyncio
async def test_mlb_tomorrow_uses_next_day_schedule() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlb tomorrow")

    assert client.schedule_calls == [(date(2026, 6, 1), None)]
    assert _plain(replies) == ["MLB 2026-06-01: LAD vs NYY 7:05pm"]
    assert BOLD in replies[0]
    assert COLOR in replies[0]


@pytest.mark.asyncio
async def test_help_and_error_replies_use_irc_formatting() -> None:
    router = CommandRouter(client=FakeClient(), settings=settings(), now=fixed_now)

    help_replies = await router.handle_message("@help")
    error_replies = await router.handle_message("@bogus")

    assert _plain(help_replies) == [
        "Commands: games: @mlb, @mlb *, @mlb TEAM, @preview/@matchup, @box, @wp, @stars, "
        "@weather, @highlights, @replay, @mlbpitcher, @mlbpitchers, @mlblineup | "
        "standings: @standings, @wildcard | stats: @sstats, @gamelog, "
        "@splits, @teamstats, @teamrank, @teamleaders, @leaders, @defense, "
        "@arsenal, @savant, @xstats, @speed, @bat, @runvalue, @fieldrv, "
        "@baserun, @arm | other: @transactions, @more, @help <command>"
    ]
    assert _plain(error_replies) == ["Unknown command: @bogus. Try @help."]
    assert BOLD in help_replies[0]
    assert COLOR in help_replies[0]
    assert BOLD in error_replies[0]
    assert COLOR in error_replies[0]


@pytest.mark.asyncio
async def test_help_topics_cover_all_commands_and_aliases() -> None:
    router = CommandRouter(client=FakeClient(), settings=settings(), now=fixed_now)
    topics = [
        "mlb",
        "preview",
        "matchup",
        "box",
        "wp",
        "stars",
        "weather",
        "replay",
        "mlbpitcher",
        "mlbpitchers",
        "mlblineup",
        "standings",
        "wildcard",
        "sstats",
        "gamelog",
        "splits",
        "leaders",
        "teamstats",
        "teamrank",
        "teamleaders",
        "defense",
        "arsenal",
        "savant",
        "percentiles",
        "xstats",
        "speed",
        "sprint",
        "bat",
        "battrack",
        "runvalue",
        "rv",
        "fieldrv",
        "fieldingrv",
        "frv",
        "baserun",
        "baserunning",
        "brv",
        "arm",
        "armstrength",
        "transactions",
        "highlights",
        "more",
        "help",
    ]

    for topic in topics:
        replies = await router.handle_message(f"@help {topic}")
        plain = _plain(replies)
        assert plain is not None
        assert not plain[0].startswith("Commands:"), topic


@pytest.mark.asyncio
async def test_mlb_team_tomorrow_uses_team_id() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlb NYY tomorrow")

    assert client.schedule_calls == [(date(2026, 6, 1), 147)]
    assert _plain(replies) == [
        "LAD @ NYY: 7:05 PM EDT at Yankee Stadium (probables: Dodger Arm vs Yankee Arm)"
    ]


@pytest.mark.asyncio
async def test_mlb_star_returns_only_live_games() -> None:
    client = FakeClient(games=[_live_game(), _final_game(), _upcoming_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlb *")

    assert _plain(replies) == ["MLB live: TOR 1-2 BAL Top 3, 1 out"]
    assert COLOR in replies[0]


@pytest.mark.asyncio
async def test_mlb_star_reports_no_live_games() -> None:
    client = FakeClient(games=[_final_game(), _upcoming_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlb *")

    assert _plain(replies) == ["MLB live: no games live."]


@pytest.mark.asyncio
async def test_mlb_live_team_includes_win_probability_and_active_pitchers() -> None:
    client = FakeClient(games=[_live_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlb TOR")

    assert _plain(replies) == [
        "TOR @ BAL | Top 3, 1 out | Score: TOR 1, BAL 2 | "
        "WP: BAL 99%, TOR 0.9% | Pitching: TOR Spencer Miles "
        "(2.1 IP 3 H 1 R 1 ER 1 BB 4 K 46 pit); BAL Kyle Bradish "
        "(3.0 IP 2 H 1 R 1 ER 2 BB 5 K 58 pit)"
    ]
    assert ITALIC in replies[0]


@pytest.mark.asyncio
async def test_preview_alias_returns_game_context() -> None:
    client = FakeClient(games=[_live_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@matchup TOR")

    assert _plain(replies) == [
        "Preview TOR @ BAL | State: Top 3, 1 out | Score: TOR 1, BAL 2 | "
        "Weather: Sunny, 82F, wind 3 mph, L To R | "
        "Lineups: TOR posted, BAL pending | "
        "Form: TOR 31-26 L10 6-4 W1; BAL 28-30 L10 4-6 L2"
    ]


@pytest.mark.asyncio
async def test_highlights_accepts_game_id() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@highlights game 824832")

    assert _plain(replies) == [
        "Highlights TOR @ BAL 1/5: Condensed Game: TOR@BAL 00:08:42 "
        "https://clips.example/condensed.mp4",
        "Highlights TOR @ BAL 2/5: Vladimir Guerrero Jr.'s go-ahead homer 00:00:42 "
        "https://clips.example/vlad-go-ahead-homer.mp4",
        "Highlights TOR @ BAL 3/5: Blue Jays turn two 00:00:28 "
        "https://clips.example/jays-turn-two.mp4",
        "2 more highlights. Use @more."
    ]


@pytest.mark.asyncio
async def test_more_returns_next_highlight_page() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    await router.handle_message("@highlights game 824832")
    replies = await router.handle_message("@more")
    exhausted = await router.handle_message("@more")

    assert _plain(replies) == [
        "Highlights TOR @ BAL 4/5: Andres Gimenez's RBI double 00:00:20 "
        "https://clips.example/gimenez-rbi-double.mp4",
        "Highlights TOR @ BAL 5/5: Manager talks after the win 00:01:45 "
        "https://clips.example/manager-talks.mp4",
    ]
    assert _plain(exhausted) == ["Nothing more to show. Run @highlights first."]


@pytest.mark.asyncio
async def test_highlights_filters_before_or_after_game_id() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    homers = await router.handle_message("@highlights homers game 824832")
    scoring = await router.handle_message("@highlights game 824832 scoring")

    assert _plain(homers) == [
        "Highlights homers TOR @ BAL 1/1: Vladimir Guerrero Jr.'s go-ahead homer 00:00:42 "
        "https://clips.example/vlad-go-ahead-homer.mp4"
    ]
    assert _plain(scoring) == [
        "Highlights scoring plays TOR @ BAL 1/2: "
        "Vladimir Guerrero Jr.'s go-ahead homer 00:00:42 "
        "https://clips.example/vlad-go-ahead-homer.mp4",
        "Highlights scoring plays TOR @ BAL 2/2: Andres Gimenez's RBI double 00:00:20 "
        "https://clips.example/gimenez-rbi-double.mp4",
    ]


@pytest.mark.asyncio
async def test_highlights_lists_filters() -> None:
    router = CommandRouter(client=FakeClient(), settings=settings(), now=fixed_now)

    replies = await router.handle_message("@highlights filters")

    assert _plain(replies) == [
        "Highlight filters: all, condensed games, scoring plays, homers, defense, "
        "pitching, recaps, interviews, data clips. Example: @highlights scoring game 822807"
    ]


@pytest.mark.asyncio
async def test_box_returns_compact_boxscore() -> None:
    client = FakeClient(games=[_live_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@box TOR")

    assert _plain(replies) == [
        "Box TOR @ BAL | Top 3, 1 out | R-H-E: TOR 1-4-0, BAL 2-5-1 | "
        "LOB: TOR 3, BAL 4 | Pitching: TOR Reliever One "
        "(0.2 IP 0 H 0 R 0 ER 0 BB 1 K 12 pit); BAL Kyle Bradish "
        "(3.0 IP 2 H 1 R 1 ER 2 BB 5 K 58 pit) | "
        "Stars: TOR Vladimir Guerrero Jr. GS 78 - 2-4, HR, 3 RBI | "
        "Swing: BAL +18.4% Bottom 8 - Clutch hit scores two."
    ]


@pytest.mark.asyncio
async def test_wp_stars_weather_and_replay_commands() -> None:
    client = FakeClient(games=[_live_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    wp = await router.handle_message("@wp TOR")
    stars = await router.handle_message("@stars TOR")
    weather = await router.handle_message("@weather TOR")
    replay = await router.handle_message("@replay TOR")

    assert _plain(wp) == [
        "WP TOR @ BAL: Now: BAL 65%, TOR 35% | "
        "Swing: BAL +18.4% Bottom 8 - Clutch hit scores two."
    ]
    assert _plain(stars) == [
        "Stars TOR @ BAL: TOR Vladimir Guerrero Jr. GS 78 - 2-4, HR, 3 RBI"
    ]
    assert _plain(weather) == ["Weather TOR @ BAL: Sunny, 82F, wind 3 mph, L To R"]
    assert _plain(replay) == ["Replay TOR @ BAL: TOR 1 left, 1 used; BAL 1 left, 0 used"]


@pytest.mark.asyncio
async def test_mlb_pitcher_shows_current_team_pitcher() -> None:
    client = FakeClient(games=[_live_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlbpitcher TOR")

    assert _plain(replies) == [
        "TOR game pitcher: TOR Spencer Miles - 2.1 IP, 3 H, 1 R, 1 ER, "
        "1 BB, 4 K, 46 pit (TOR vs BAL, In Progress)"
    ]


@pytest.mark.asyncio
async def test_mlb_pitchers_shows_all_game_pitchers() -> None:
    client = FakeClient(games=[_live_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlbpitchers TOR")

    assert _plain(replies) == [
        "Pitchers: TOR: Spencer Miles 2.1 IP 3 H 1 R 1 ER 1 BB 4 K 46 pit; "
        "Reliever One 0.2 IP 0 H 0 R 0 ER 0 BB 1 K 12 pit | "
        "BAL: Kyle Bradish 3.0 IP 2 H 1 R 1 ER 2 BB 5 K 58 pit",
    ]


@pytest.mark.asyncio
async def test_mlb_lineup_shows_requested_team_lineup() -> None:
    client = FakeClient(games=[_live_game()])
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@mlblineup TOR")

    assert _plain(replies) == [
        "TOR lineup: 1. Nathan Lukes LF; 2. Vladimir Guerrero Jr. DH"
    ]


@pytest.mark.asyncio
async def test_wildcard_command_requests_wildcard_standings() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@wildcard AL")

    assert client.standings_calls == [(2026, "wildCard", "AL")]
    assert _plain(replies) == ["AL wildcard standings: 1. NYY 34-20 +2.0 GB"]


@pytest.mark.asyncio
async def test_wildcard_default_returns_both_leagues() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@wildcard")

    assert client.standings_calls == [(2026, "wildCard", None)]
    assert _plain(replies) == [
        "Wildcard standings: AL: 1. NYY 34-20 +2.0 GB | "
        "NL: 1. LAD 33-21 +1.0 GB"
    ]


@pytest.mark.asyncio
async def test_sstats_returns_candidates_for_ambiguous_player() -> None:
    router = CommandRouter(client=FakeClient(), settings=settings(), now=fixed_now)

    replies = await router.handle_message("@sstats John")

    assert _plain(replies) == [
        "Multiple players matched: John Smith (A Team, P); John Smith Jr. (B Team, CF)"
    ]


@pytest.mark.asyncio
async def test_sstats_formats_advanced_season_stats() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@sstats Shohei Ohtani")

    assert client.stats_calls == [("Shohei Ohtani", "hitting", 2026, None, None)]
    assert _plain(replies) == [
        "Shohei Ohtani 2026 hitting: .300/.390/.600 OPS .990, 12 HR, 40 RBI | "
        "adv: BABIP .330, ISO .300 | sabr: wRC+ 165, WAR 2.4 | "
        "exp: xAVG .310, xSLG .640, xwOBA .420"
    ]
    assert ITALIC in replies[0]


@pytest.mark.asyncio
async def test_sstats_accepts_day_window() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@sstats Shohei Ohtani hitting 7 days")

    assert client.stats_calls == [
        ("Shohei Ohtani", "hitting", 2026, date(2026, 5, 25), date(2026, 5, 31))
    ]
    assert _plain(replies) == [
        "Shohei Ohtani last 7 days hitting: .286/.400/.619 OPS 1.019, 2 HR | "
        "adv: ISO .333, K/PA .200"
    ]


@pytest.mark.asyncio
async def test_sstats_accepts_last_games_window() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@sstats Shohei Ohtani hitting last 3 games")

    assert _plain(replies) == [
        "Shohei Ohtani last 3 games hitting: .400/.455/.800 OPS 1.255, 3 HR"
    ]


@pytest.mark.asyncio
async def test_gamelog_and_splits_commands() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    gamelog = await router.handle_message("@gamelog Shohei Ohtani 2")
    splits = await router.handle_message("@splits Shohei Ohtani risp")
    night_split = await router.handle_message("@splits Shohei Ohtani night")

    assert _plain(gamelog) == [
        "Shohei Ohtani last 2 games hitting: "
        "05-31 @ BAL: 2-4, HR, 3 RBI; 05-30 vs BAL: 1-3, BB"
    ]
    assert _plain(splits) == [
        "Shohei Ohtani 2026 Scoring Position hitting: "
        ".333/.444/.667 OPS 1.111, 12 RBI"
    ]
    assert _plain(night_split) == [
        "Shohei Ohtani 2026 Night Games hitting: "
        ".333/.444/.667 OPS 1.111, 12 RBI"
    ]


@pytest.mark.asyncio
async def test_sstats_defaults_pitchers_to_pitching_stats() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@sstats Tarik Skubal")

    assert client.stats_calls == [("Tarik Skubal", "pitching", 2026, None, None)]
    assert _plain(replies) == [
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
    assert _plain(replies) == ["homeRuns leaders: 1. Slugger 20 (Club)"]


@pytest.mark.asyncio
async def test_leaders_clamps_large_requested_limit() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    await router.handle_message("@leaders HR 300")

    assert client.leader_calls == [("homeRuns", 2026, 10)]


def test_format_leaders_omits_whole_entries_when_output_is_long() -> None:
    leaders = [
        Leader(
            rank=str(index),
            value=str(40 - index),
            player_name=f"Very Long Slugger Name Number {index}",
            team_name="Extremely Long Baseball Club",
        )
        for index in range(1, 11)
    ]

    reply = format_leaders("homeRuns", leaders)
    plain = strip_irc_formatting(reply)

    assert len(plain) <= MAX_IRC_LEN
    assert "+5 more" in plain
    assert "Very Long Slugger Name Number 5" in plain
    assert "Very Long Slugger Name Number 6" not in plain
    assert not plain.endswith("...")


@pytest.mark.asyncio
async def test_teamstats_defaults_to_hitting_and_pitching() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@teamstats TOR")

    assert client.team_stats_calls == [
        ("TOR", "hitting", 2026, None, None),
        ("TOR", "pitching", 2026, None, None),
    ]
    assert _plain(replies) == [
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
    assert _plain(replies) == [
        "TOR teamstats last 7 days: hit: .250/.320/.410 OPS .730, 42 R, "
        "11 HR, 80 H, 6 SB"
    ]


@pytest.mark.asyncio
async def test_team_split_rank_leaders_defense_and_arsenal_commands() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    team_split = await router.handle_message("@teamstats TOR hitting risp")
    team_rank = await router.handle_message("@teamrank ops 2")
    team_leaders = await router.handle_message("@teamleaders TOR hr")
    defense = await router.handle_message("@defense Shohei Ohtani")
    arsenal = await router.handle_message("@arsenal Tarik Skubal")

    assert _plain(team_split) == [
        "TOR teamstats 2026 Scoring Position: hit: .300/.380/.500 OPS .880, "
        "22 R, 5 HR"
    ]
    assert _plain(team_rank) == ["ops team rankings: 1. TOR .800; 2. BAL .760"]
    assert _plain(team_leaders) == ["TOR leaders: homeRuns: Team Slugger 12"]
    assert _plain(defense) == [
        "Shohei Ohtani 2026 defense: OAA 5, Runs Prevented 4, Att 80"
    ]
    assert _plain(arsenal) == [
        "Tarik Skubal arsenal: Four-Seam Fastball 55.5%, 96.4 mph, 120 pit; "
        "Slider 32.1%, 86.2 mph, 70 pit"
    ]


@pytest.mark.asyncio
async def test_savant_leaderboard_commands() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    savant = await router.handle_message("@savant Shohei Ohtani")
    xstats = await router.handle_message("@xstats Shohei Ohtani")
    speed = await router.handle_message("@speed Shohei Ohtani")
    bat = await router.handle_message("@bat Shohei Ohtani")
    runvalue = await router.handle_message("@runvalue Shohei Ohtani")
    fieldrv = await router.handle_message("@fieldrv Shohei Ohtani")
    baserun = await router.handle_message("@baserun Shohei Ohtani")
    arm = await router.handle_message("@arm Shohei Ohtani")

    assert _plain(savant) == [
        "Shohei Ohtani 2026 Savant: xwOBA 98th, xSLG 96th, EV 96th, "
        "HardHit 95th, Barrel 95th, BB 94th, K 61st, Sprint 56th, BatSpd 79th"
    ]
    assert _plain(xstats) == [
        "Shohei Ohtani 2026 xStats: xBA .310, xSLG .640, xwOBA .420, "
        "EV 94.2 mph, MaxEV 119.1 mph, HH 57.4%, Brl/BIP 22.8%, "
        "Brl/PA 13.1%, SweetSpot 38.6%"
    ]
    assert _plain(speed) == [
        "Shohei Ohtani 2026 Speed: Sprint 28.7 ft/s, bolts 9, HP-1B 4.19, rank 72"
    ]
    assert _plain(bat) == [
        "Shohei Ohtani 2026 Bat: BatSpd 75.8 mph, Attack 13.4 deg, "
        "Length 7.9 ft, Squared 34.8%, Ideal 58.4%, RV +9.6, swings 284"
    ]
    assert _plain(runvalue) == [
        "Shohei Ohtani 2026 RunValue: RV +16.8, heart +6.2, shadow -3.0, "
        "chase +8.0, waste +5.5, PA 297, pitches 1283"
    ]
    assert _plain(fieldrv) == [
        "Shohei Ohtani 2026 FieldRV: RV +13.1, range +10.4, arm +2.7, "
        "DP 0.0, outs 1777"
    ]
    assert _plain(baserun) == [
        "Shohei Ohtani 2026 BaseRun: RV +4.0, steal +3.4, extra +0.7, "
        "moved 88, extra att 42"
    ]
    assert _plain(arm) == [
        "Shohei Ohtani 2026 Arm: Arm 87.3 mph, Max 94.1 mph, throws 157, pos OF"
    ]


@pytest.mark.asyncio
async def test_transactions_defaults_to_today() -> None:
    client = FakeClient()
    router = CommandRouter(client=client, settings=settings(), now=fixed_now)

    replies = await router.handle_message("@transactions")

    assert client.transaction_calls == [(date(2026, 5, 31), date(2026, 5, 31), None)]
    assert _plain(replies) == [
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
    assert _plain(replies)[0].startswith("TOR transactions 2026-05-25..2026-05-31:")


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
                "weather": {"condition": "Sunny", "temp": "82", "wind": "3 mph, L To R"},
                "review": {
                    "away": {"used": 1, "remaining": 1},
                    "home": {"used": 0, "remaining": 1},
                },
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
                    "topPerformers": [
                        {
                            "type": "hitter",
                            "gameScore": 78,
                            "player": {
                                "person": {"id": 665489, "fullName": "Vladimir Guerrero Jr."},
                                "stats": {
                                    "batting": {"summary": "2-4 | HR, 3 RBI"},
                                    "pitching": {},
                                },
                            },
                        }
                    ],
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
