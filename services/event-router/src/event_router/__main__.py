from __future__ import annotations

import argparse
import asyncio

from .db import Database
from .logging import configure_logging
from .settings import Settings
from .worker import EventRouter


def main() -> None:
    parser = argparse.ArgumentParser(prog="event-router")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run", help="Run the event-router worker")
    args = parser.parse_args()

    if args.command != "run":
        parser.print_help()
        raise SystemExit(2)

    settings = Settings()
    configure_logging(settings.log_level)
    db = Database(settings.database_url)
    worker = EventRouter(settings, db)
    asyncio.run(worker.run())


if __name__ == "__main__":
    main()
