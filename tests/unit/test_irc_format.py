from mlb_irc_bot import irc_format as fmt


def test_style_helpers_emit_standard_irc_codes() -> None:
    assert fmt.bold("MLB").startswith(fmt.BOLD)
    assert fmt.italic("MLB").startswith(fmt.ITALIC)
    assert fmt.color("MLB", fmt.IRCColor.LIGHT_BLUE) == "\x0312MLB\x0f"


def test_strip_irc_formatting_restores_plaintext() -> None:
    styled = (
        f"{fmt.title('MLB')} {fmt.team('TOR')} "
        f"{fmt.section('Win')}: {fmt.value('99%')}"
    )

    assert fmt.strip_irc_formatting(styled) == "MLB TOR Win: 99%"


def test_truncate_irc_keeps_control_codes_intact() -> None:
    styled = f"prefix {fmt.color('abcdef', fmt.IRCColor.LIGHT_BLUE)} suffix"
    truncated = fmt.truncate_irc(styled, 13)

    assert len(fmt.strip_irc_formatting(truncated)) <= 13
    assert truncated.endswith(f"{fmt.RESET}...")
    assert "\x0312" in truncated
    assert fmt.strip_irc_formatting(truncated) == "prefix abc..."
