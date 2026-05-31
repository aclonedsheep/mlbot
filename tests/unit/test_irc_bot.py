from mlb_irc_bot.irc_bot import _is_own_message


def test_is_own_message_matches_current_or_configured_nick_case_insensitively() -> None:
    assert _is_own_message("MLBotSlop", current_nick="mlbotslop", configured_nick="mlbbot")
    assert _is_own_message("MLBBOT", current_nick="mlbotslop", configured_nick="mlbbot")
    assert not _is_own_message("codexfull1234", current_nick="mlbotslop", configured_nick="mlbbot")
    assert not _is_own_message(None, current_nick="mlbotslop", configured_nick="mlbbot")
