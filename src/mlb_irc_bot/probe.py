import argparse
import asyncio
from datetime import date, datetime

from mlb_irc_bot.config import Settings
from mlb_irc_bot.mlb.client import MLBStatsClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe live MLB API hydrate behavior.")
    parser.add_argument("--date", help="Date to probe in YYYY-MM-DD format. Defaults to today.")
    args = parser.parse_args()
    asyncio.run(_amain(args.date))


async def _amain(date_value: str | None) -> None:
    settings = Settings()
    target_date = (
        date.fromisoformat(date_value)
        if date_value
        else datetime.now(settings.zoneinfo()).date()
    )
    async with MLBStatsClient(timeout=settings.http_timeout_seconds) as client:
        hydrations = await client.available_schedule_hydrations(target_date)
        games = await client.get_schedule(target_date)

    first = games[0] if games else None
    print(f"Date: {target_date.isoformat()}")
    print(f"Hydrations advertised: {', '.join(hydrations[:20])}")
    print(f"Games: {len(games)}")
    if first is not None:
        print(f"First game: {first.game_pk} {first.away.abbreviation} @ {first.home.abbreviation}")
        print(f"First game has linescore: {first.linescore is not None}")


if __name__ == "__main__":
    main()
