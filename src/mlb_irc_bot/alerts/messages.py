from dataclasses import dataclass


@dataclass(frozen=True)
class Alert:
    key: str
    alert_type: str
    game_pk: int | None
    message: str
