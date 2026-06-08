from __future__ import annotations

import argparse
import asyncio

import httpx

from .logging import configure_logging
from .settings import Settings
from .worker import AnomalyConsumer


async def async_main() -> None:
    parser = argparse.ArgumentParser(prog="tickbase-anomaly-consumer")
    parser.add_argument("command", choices=("run", "once"), nargs="?", default="run")
    args = parser.parse_args()

    settings = Settings()
    configure_logging(settings.log_level)
    consumer = AnomalyConsumer(settings)

    if args.command == "once":
        await consumer.db.connect()
        try:
            timeout = httpx.Timeout(settings.request_timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                await consumer.run_once(client)
        finally:
            await consumer.db.close()
        return

    await consumer.run()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
