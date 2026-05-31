from mlb_irc_bot.mlb.teams import TEAM_DIRECTORY


def test_team_aliases_resolve_common_abbreviations() -> None:
    assert TEAM_DIRECTORY.resolve("NYY").team_id == 147
    assert TEAM_DIRECTORY.resolve("yanks").abbreviation == "NYY"
    assert TEAM_DIRECTORY.resolve("WSN").abbreviation == "WSH"
    assert TEAM_DIRECTORY.resolve("CHW").abbreviation == "CWS"
    assert TEAM_DIRECTORY.resolve("A's").abbreviation == "ATH"
