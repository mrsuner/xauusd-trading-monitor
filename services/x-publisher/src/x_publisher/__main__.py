from __future__ import annotations

import argparse
import asyncio

from .logging import configure_logging
from .settings import Settings
from .worker import XPublisher


async def async_main() -> None:
    parser = argparse.ArgumentParser(prog="x-publisher")
    parser.add_argument("command", choices=("run", "once"), nargs="?", default="run")
    args = parser.parse_args()

    settings = Settings()
    configure_logging(settings.log_level)
    publisher = XPublisher(settings)
    if args.command == "once":
        await publisher.db.connect()
        try:
            await publisher.run_once()
        finally:
            await publisher.db.close()
        return
    await publisher.run()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
