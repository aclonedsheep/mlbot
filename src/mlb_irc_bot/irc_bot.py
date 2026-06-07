import asyncio
import contextlib
import logging

from ircrobots import Bot as BaseBot
from ircrobots import ConnectionParams
from ircrobots import Server as BaseServer
from irctokens import Line

from mlb_irc_bot.commands import CommandRouter
from mlb_irc_bot.config import Settings
from mlb_irc_bot.mlb.client import MLBStatsClient
from mlb_irc_bot.scheduler import LiveScheduler
from mlb_irc_bot.storage import AlertStore

LOGGER = logging.getLogger(__name__)


class MLBIRCService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = MLBStatsClient(timeout=settings.http_timeout_seconds)
        self.store = AlertStore(settings.database_path)
        self.router = CommandRouter(client=self.client, settings=settings)
        self.scheduler_task: asyncio.Task[None] | None = None
        self.server: MLBServer | None = None

    async def run(self) -> None:
        await self.store.init()
        bot = MLBBot(self)
        if self.settings.irc_tls:
            params = ConnectionParams(
                self.settings.irc_nick,
                self.settings.irc_server,
                self.settings.irc_port,
                realname=self.settings.irc_realname,
                password=self.settings.irc_password,
                autojoin=[self.settings.irc_channel],
            )
        else:
            params = ConnectionParams(
                self.settings.irc_nick,
                self.settings.irc_server,
                self.settings.irc_port,
                tls=None,
                realname=self.settings.irc_realname,
                password=self.settings.irc_password,
                autojoin=[self.settings.irc_channel],
            )
        await bot.add_server("primary", params)
        try:
            await bot.run()
        finally:
            if self.scheduler_task:
                self.scheduler_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.scheduler_task
            await self.client.close()

    def start_scheduler(self, server: "MLBServer") -> None:
        if self.scheduler_task is not None:
            return
        self.server = server
        scheduler = LiveScheduler(
            client=self.client,
            store=self.store,
            settings=self.settings,
            send_alert=lambda message: server.send_channel_message(message),
        )
        self.scheduler_task = asyncio.create_task(scheduler.run_forever())


class MLBBot(BaseBot):
    def __init__(self, service: MLBIRCService) -> None:
        super().__init__()
        self.service = service

    def create_server(self, name: str) -> "MLBServer":
        return MLBServer(self, name, self.service)


class MLBServer(BaseServer):
    def __init__(self, bot: MLBBot, name: str, service: MLBIRCService) -> None:
        super().__init__(bot, name)
        self.service = service

    async def line_read(self, line: Line) -> None:
        if line.command == "JOIN" and self._is_own_channel_join(line):
            self.service.start_scheduler(self)
            return
        if line.command != "PRIVMSG" or len(line.params) < 2:
            return
        target, message = line.params[0], line.params[1]
        if _is_own_message(
            line.hostmask.nickname,
            current_nick=self.nickname,
            configured_nick=self.service.settings.irc_nick,
        ):
            return
        if target != self.service.settings.irc_channel and target != self.nickname:
            return
        replies = await self.service.router.handle_message(message)
        if not replies:
            return
        response_target = (
            self.service.settings.irc_channel
            if target.startswith("#")
            else line.hostmask.nickname
        )
        for reply in replies:
            await self.send_message(response_target, reply)

    async def line_send(self, line: Line) -> None:
        LOGGER.debug("> %s", line.format())

    async def send_channel_message(self, message: str) -> None:
        await self.send_message(self.service.settings.irc_channel, message)

    def _is_own_channel_join(self, line: Line) -> bool:
        if not line.params:
            return False
        if not _is_own_message(
            line.hostmask.nickname,
            current_nick=self.nickname,
            configured_nick=self.service.settings.irc_nick,
        ):
            return False
        return self.casefold_equals(line.params[0], self.service.settings.irc_channel)


def _is_own_message(
    sender: str | None, *, current_nick: str | None, configured_nick: str
) -> bool:
    if not sender:
        return False
    normalized = sender.casefold()
    return normalized in {
        nick.casefold()
        for nick in (current_nick, configured_nick)
        if nick
    }
