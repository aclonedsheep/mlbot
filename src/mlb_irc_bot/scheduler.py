import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from time import monotonic

from mlb_irc_bot.alerts.detectors import collect_alerts, final_alert_from_summary
from mlb_irc_bot.alerts.messages import Alert
from mlb_irc_bot.config import Settings
from mlb_irc_bot.mlb.client import MLBAPIError, MLBStatsClient
from mlb_irc_bot.mlb.models import GameSummary
from mlb_irc_bot.storage import AlertStore

SendAlert = Callable[[str], Awaitable[None]]


class LiveScheduler:
    def __init__(
        self,
        *,
        client: MLBStatsClient,
        store: AlertStore,
        settings: Settings,
        send_alert: SendAlert,
    ) -> None:
        self.client = client
        self.store = store
        self.settings = settings
        self.send_alert = send_alert
        self._cached_games: list[GameSummary] = []
        self._last_schedule_refresh = 0.0

    async def run_forever(self) -> None:
        while True:
            await self.poll_once()
            await asyncio.sleep(self.settings.active_game_poll_seconds)

    async def poll_once(self) -> None:
        now = datetime.now(self.settings.zoneinfo())
        if monotonic() - self._last_schedule_refresh >= self.settings.schedule_poll_seconds:
            self._cached_games = await self.client.get_schedule(now.date())
            self._last_schedule_refresh = monotonic()
        elif not self._cached_games:
            self._cached_games = await self.client.get_schedule(now.date())

        for game in self._cached_games:
            if not (game.is_live or game.is_final):
                continue
            alerts: list[Alert] = []
            try:
                detail = await self.client.get_game_detail(game.game_pk)
                await self.client.enrich_home_run_data(detail.raw)
                alerts.extend(collect_alerts(detail.raw))
            except MLBAPIError:
                pass
            final_alert = final_alert_from_summary(game)
            if final_alert is not None:
                alerts.append(final_alert)
            for alert in alerts:
                await self._send_once(alert)

    async def _send_once(self, alert: Alert) -> None:
        if not self._enabled(alert.alert_type):
            return
        if await self.store.seen(alert.key):
            return
        await self.send_alert(alert.message)
        await self.store.mark_sent(
            alert_key=alert.key,
            alert_type=alert.alert_type,
            game_pk=alert.game_pk,
            message=alert.message,
        )

    def _enabled(self, alert_type: str) -> bool:
        return {
            "home_run": self.settings.enable_alert_home_runs,
            "scoring": self.settings.enable_alert_scoring,
            "bases_loaded": self.settings.enable_alert_bases_loaded,
            "final": self.settings.enable_alert_finals,
            "no_hitter": self.settings.enable_alert_no_hitter,
            "immaculate": self.settings.enable_alert_immaculate,
            "cycle_watch": self.settings.enable_alert_cycle,
            "cycle": self.settings.enable_alert_cycle,
        }.get(alert_type, True)
