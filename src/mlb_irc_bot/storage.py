from datetime import UTC, datetime
from pathlib import Path

import aiosqlite


class AlertStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS sent_alerts (
                    alert_key TEXT PRIMARY KEY,
                    alert_type TEXT NOT NULL,
                    game_pk INTEGER,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.commit()

    async def seen(self, alert_key: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT 1 FROM sent_alerts WHERE alert_key = ?", (alert_key,))
            row = await cursor.fetchone()
            return row is not None

    async def message_for(self, alert_key: str) -> str | None:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT message FROM sent_alerts WHERE alert_key = ?",
                (alert_key,),
            )
            row = await cursor.fetchone()
            return None if row is None else str(row[0])

    async def mark_sent(
        self,
        *,
        alert_key: str,
        alert_type: str,
        game_pk: int | None,
        message: str,
    ) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO sent_alerts
                (alert_key, alert_type, game_pk, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (alert_key, alert_type, game_pk, message, datetime.now(UTC).isoformat()),
            )
            await db.commit()
