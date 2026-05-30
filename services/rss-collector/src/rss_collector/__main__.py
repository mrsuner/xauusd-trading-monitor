from __future__ import annotations

import argparse
import asyncio

from .collector import RssCollector
from .logging import configure_logging
from .settings import Settings


async def async_main() -> None:
    parser = argparse.ArgumentParser(prog="rss-collector")
    parser.add_argument("command", choices=("run",), nargs="?", default="run")
    parser.parse_args()

    settings = Settings()
    configure_logging(settings.log_level)
    collector = RssCollector(settings)
    await collector.run()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
