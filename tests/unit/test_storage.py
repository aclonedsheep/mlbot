import pytest

from mlb_irc_bot.storage import AlertStore


@pytest.mark.asyncio
async def test_alert_store_marks_seen(tmp_path) -> None:
    store = AlertStore(tmp_path / "alerts.sqlite3")
    await store.init()

    assert not await store.seen("game:alert")

    await store.mark_sent(
        alert_key="game:alert",
        alert_type="home_run",
        game_pk=1,
        message="HR",
    )

    assert await store.seen("game:alert")
    assert await store.message_for("game:alert") == "HR"
    assert await store.message_for("game:missing") is None
