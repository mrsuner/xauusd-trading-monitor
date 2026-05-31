from __future__ import annotations

import argparse
import asyncio

from .logging import configure_logging
from .settings import Settings
from .worker import AlertDispatcher


async def async_main() -> None:
    parser = argparse.ArgumentParser(prog="alert-dispatcher")
    parser.add_argument("command", choices=("run", "once"), nargs="?", default="run")
    args = parser.parse_args()

    settings = Settings()
    configure_logging(settings.log_level)
    dispatcher = AlertDispatcher(settings)
    if args.command == "once":
        await dispatcher.db.connect()
        try:
            await dispatcher.run_once()
        finally:
            await dispatcher.db.close()
        return
    await dispatcher.run()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
