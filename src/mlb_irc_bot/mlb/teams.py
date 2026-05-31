from dataclasses import dataclass


@dataclass(frozen=True)
class TeamRecord:
    team_id: int
    abbreviation: str
    name: str
    aliases: tuple[str, ...] = ()


MLB_TEAMS: tuple[TeamRecord, ...] = (
    TeamRecord(108, "LAA", "Los Angeles Angels", ("ANA", "ANGELS")),
    TeamRecord(109, "ARI", "Arizona Diamondbacks", ("AZ", "DIAMONDBACKS", "DBACKS")),
    TeamRecord(110, "BAL", "Baltimore Orioles", ("ORIOLES",)),
    TeamRecord(111, "BOS", "Boston Red Sox", ("RED SOX", "SOX")),
    TeamRecord(112, "CHC", "Chicago Cubs", ("CUBS",)),
    TeamRecord(113, "CIN", "Cincinnati Reds", ("REDS",)),
    TeamRecord(114, "CLE", "Cleveland Guardians", ("GUARDIANS",)),
    TeamRecord(115, "COL", "Colorado Rockies", ("ROCKIES",)),
    TeamRecord(116, "DET", "Detroit Tigers", ("TIGERS",)),
    TeamRecord(117, "HOU", "Houston Astros", ("ASTROS",)),
    TeamRecord(118, "KC", "Kansas City Royals", ("KCR", "ROYALS")),
    TeamRecord(119, "LAD", "Los Angeles Dodgers", ("LA", "DODGERS")),
    TeamRecord(120, "WSH", "Washington Nationals", ("WSN", "NATS", "NATIONALS")),
    TeamRecord(121, "NYM", "New York Mets", ("METS",)),
    TeamRecord(133, "ATH", "Athletics", ("OAK", "A'S", "AS", "ATHLETICS")),
    TeamRecord(134, "PIT", "Pittsburgh Pirates", ("PIRATES",)),
    TeamRecord(135, "SD", "San Diego Padres", ("SDP", "PADRES")),
    TeamRecord(136, "SEA", "Seattle Mariners", ("MARINERS",)),
    TeamRecord(137, "SF", "San Francisco Giants", ("SFG", "GIANTS")),
    TeamRecord(138, "STL", "St. Louis Cardinals", ("CARDINALS", "CARDS")),
    TeamRecord(139, "TB", "Tampa Bay Rays", ("TBR", "RAYS")),
    TeamRecord(140, "TEX", "Texas Rangers", ("RANGERS",)),
    TeamRecord(141, "TOR", "Toronto Blue Jays", ("BLUE JAYS", "JAYS")),
    TeamRecord(142, "MIN", "Minnesota Twins", ("TWINS",)),
    TeamRecord(143, "PHI", "Philadelphia Phillies", ("PHILLIES",)),
    TeamRecord(144, "ATL", "Atlanta Braves", ("BRAVES",)),
    TeamRecord(145, "CWS", "Chicago White Sox", ("CHW", "WHITE SOX")),
    TeamRecord(146, "MIA", "Miami Marlins", ("FLA", "MARLINS")),
    TeamRecord(147, "NYY", "New York Yankees", ("YANKEES", "YANKS")),
    TeamRecord(158, "MIL", "Milwaukee Brewers", ("BREWERS",)),
)


class TeamDirectory:
    def __init__(self, teams: tuple[TeamRecord, ...] = MLB_TEAMS) -> None:
        self._by_id = {team.team_id: team for team in teams}
        self._by_token: dict[str, TeamRecord] = {}
        for team in teams:
            for token in (team.abbreviation, team.name, *team.aliases):
                self._by_token[self._normalize(token)] = team

    def resolve(self, value: str) -> TeamRecord | None:
        return self._by_token.get(self._normalize(value))

    def abbreviation_for_id(self, team_id: int) -> str:
        team = self._by_id.get(team_id)
        return team.abbreviation if team else str(team_id)

    def name_for_id(self, team_id: int) -> str:
        team = self._by_id.get(team_id)
        return team.name if team else str(team_id)

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.upper().replace(".", "").split())


TEAM_DIRECTORY = TeamDirectory()
