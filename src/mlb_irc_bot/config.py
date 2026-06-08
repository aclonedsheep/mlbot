from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MLB_",
        case_sensitive=False,
        extra="ignore",
    )

    irc_nick: str = "mlbbot"
    irc_server: str = "irc.example.net"
    irc_port: int = 6697
    irc_tls: bool = True
    irc_channel: str = "#mlb"
    irc_realname: str = "MLB IRC Bot"
    irc_password: str | None = None

    command_prefix: str = "@"
    timezone: str = "America/New_York"
    database_path: Path = Path("data/mlb_irc_bot.sqlite3")
    http_timeout_seconds: float = 10.0

    schedule_poll_seconds: int = Field(default=300, ge=30)
    active_game_poll_seconds: int = Field(default=15, ge=5)
    near_start_poll_seconds: int = Field(default=60, ge=15)

    enable_alert_home_runs: bool = True
    enable_alert_scoring: bool = True
    enable_alert_bases_loaded: bool = True
    enable_alert_finals: bool = True
    enable_alert_no_hitter: bool = True
    enable_alert_immaculate: bool = True
    enable_alert_cycle: bool = True
    enable_alert_win_probability: bool = True
    enable_alert_high_leverage: bool = True
    enable_alert_hard_hit: bool = True
    enable_alert_barrel: bool = True
    enable_alert_late_threat: bool = True
    enable_alert_weather: bool = True
    enable_alert_lead_changes: bool = True

    alert_hard_hit_threshold_mph: float = Field(default=110.0, ge=0)
    alert_win_probability_threshold: float = Field(default=15.0, ge=0)
    alert_high_leverage_threshold: float = Field(default=2.5, ge=0)

    def zoneinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)
