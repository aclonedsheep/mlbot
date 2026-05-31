import argparse
import asyncio
import logging

from mlb_irc_bot.config import Settings
from mlb_irc_bot.irc_bot import MLBIRCService
from mlb_irc_bot.storage import AlertStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MLB IRC bot.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load config and initialize storage, then exit.",
    )
    parser.add_argument("--log-level", default="INFO", help="Python logging level.")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    asyncio.run(_amain(args.dry_run))


async def _amain(dry_run: bool) -> None:
    settings = Settings()
    if dry_run:
        await AlertStore(settings.database_path).init()
        print(
            f"Dry run OK: nick={settings.irc_nick}, server={settings.irc_server}, "
            f"channel={settings.irc_channel}, db={settings.database_path}"
        )
        return
    await MLBIRCService(settings).run()


if __name__ == "__main__":
    main()
