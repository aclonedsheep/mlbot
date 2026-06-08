import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from time import monotonic

from mlb_irc_bot.alerts.detectors import collect_alerts, final_alert_from_summary
from mlb_irc_bot.alerts.messages import Alert
from mlb_irc_bot.config import Settings
from mlb_irc_bot.mlb.client import MLBAPIError, MLBStatsClient
from mlb_irc_bot.mlb.models import GameSummary
from mlb_irc_bot.storage import AlertStore

SendAlert = Callable[[str], Awaitable[None]]
NEAR_START_LOOKAHEAD = timedelta(hours=2)
NEAR_START_GRACE = timedelta(hours=3)
LOGGER = logging.getLogger(__name__)


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
        self._last_near_start_poll: dict[int, float] = {}
        self._observed_game_pks: set[int] = set()
        self._suppressed_alert_keys: set[str] = set()

    async def run_forever(self) -> None:
        while True:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Live scheduler poll failed")
            await asyncio.sleep(self.settings.active_game_poll_seconds)

    async def poll_once(self) -> None:
        now = datetime.now(self.settings.zoneinfo())
        now_monotonic = monotonic()
        if now_monotonic - self._last_schedule_refresh >= self.settings.schedule_poll_seconds:
            self._cached_games = await self.client.get_schedule(now.date())
            self._last_schedule_refresh = monotonic()
        elif not self._cached_games:
            self._cached_games = await self.client.get_schedule(now.date())

        for game in self._cached_games:
            if not self._should_poll_game(game, now=now, now_monotonic=now_monotonic):
                continue
            alerts: list[Alert] = []
            try:
                detail = await self.client.get_game_detail(game.game_pk)
                await self.client.enrich_home_run_data(detail.raw)
                try:
                    detail.raw["winProbabilityPlays"] = await self.client.get_win_probability_plays(
                        game.game_pk
                    )
                except MLBAPIError:
                    detail.raw["winProbabilityPlays"] = []
                alerts.extend(
                    collect_alerts(
                        detail.raw,
                        hard_hit_threshold_mph=self.settings.alert_hard_hit_threshold_mph,
                        win_probability_threshold=self.settings.alert_win_probability_threshold,
                        high_leverage_threshold=self.settings.alert_high_leverage_threshold,
                    )
                )
            except MLBAPIError:
                pass
            except Exception:
                LOGGER.exception(
                    "Live scheduler failed to collect alerts for game %s",
                    game.game_pk,
                )
                continue
            final_alert = final_alert_from_summary(game)
            if final_alert is not None:
                alerts.append(final_alert)
            if self._should_suppress_existing_alerts(game):
                suppressed_keys = {alert.key for alert in alerts}
                self._suppressed_alert_keys.update(suppressed_keys)
                if suppressed_keys:
                    LOGGER.info(
                        "Live scheduler suppressed %s existing alerts for game %s on first poll",
                        len(suppressed_keys),
                        game.game_pk,
                    )
                continue
            for alert in alerts:
                if alert.key in self._suppressed_alert_keys:
                    continue
                try:
                    await self._send_once(alert)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    LOGGER.exception(
                        "Live scheduler failed to send alert key=%s type=%s game_pk=%s",
                        alert.key,
                        alert.alert_type,
                        alert.game_pk,
                    )

    def _should_poll_game(
        self,
        game: GameSummary,
        *,
        now: datetime,
        now_monotonic: float,
    ) -> bool:
        if game.is_live or game.is_final:
            return True
        if not _is_near_start_game(game, now):
            return False
        last_polled = self._last_near_start_poll.get(game.game_pk, 0.0)
        if now_monotonic - last_polled < self.settings.near_start_poll_seconds:
            return False
        self._last_near_start_poll[game.game_pk] = now_monotonic
        return True

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
            "win_probability": self.settings.enable_alert_win_probability,
            "high_leverage": self.settings.enable_alert_high_leverage,
            "hard_hit": self.settings.enable_alert_hard_hit,
            "barrel": self.settings.enable_alert_barrel,
            "late_threat": self.settings.enable_alert_late_threat,
            "weather": self.settings.enable_alert_weather,
        }.get(alert_type, True)

    def _should_suppress_existing_alerts(self, game: GameSummary) -> bool:
        if game.game_pk in self._observed_game_pks:
            return False
        self._observed_game_pks.add(game.game_pk)
        return game.is_live or game.is_final


def _is_near_start_game(game: GameSummary, now: datetime) -> bool:
    if not game.is_upcoming or game.game_date is None:
        return False
    game_time = game.game_date
    if game_time.tzinfo is None:
        game_time = game_time.replace(tzinfo=now.tzinfo)
    else:
        game_time = game_time.astimezone(now.tzinfo)
    until_start = game_time - now
    return -NEAR_START_GRACE <= until_start <= NEAR_START_LOOKAHEAD
