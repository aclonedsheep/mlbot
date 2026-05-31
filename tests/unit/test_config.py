from pathlib import Path

from mlb_irc_bot.config import Settings


def test_settings_accept_overrides(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        command_prefix="!",
        timezone="America/Chicago",
        database_path=tmp_path / "bot.sqlite3",
    )

    assert settings.command_prefix == "!"
    assert settings.zoneinfo().key == "America/Chicago"
    assert settings.database_path == tmp_path / "bot.sqlite3"
