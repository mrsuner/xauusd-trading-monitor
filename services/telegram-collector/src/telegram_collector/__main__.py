from __future__ import annotations

import argparse
import asyncio

from .collector import TelegramCollector
from .logging import configure_logging
from .settings import Settings


async def async_main() -> None:
    parser = argparse.ArgumentParser(prog="telegram-collector")
    parser.add_argument("command", choices=("run", "login"), nargs="?", default="run")
    args = parser.parse_args()

    settings = Settings()
    configure_logging(settings.log_level)
    collector = TelegramCollector(settings)

    if args.command == "login":
        await collector.login()
        return

    await collector.run()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
