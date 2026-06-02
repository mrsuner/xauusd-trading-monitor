from __future__ import annotations

import argparse
import asyncio

from .logging import configure_logging
from .settings import Settings
from .worker import PublicSyncer


def main() -> None:
    parser = argparse.ArgumentParser(prog="public-syncer")
    parser.add_argument("command", choices=["run", "once"], nargs="?", default="run")
    args = parser.parse_args()

    settings = Settings()
    configure_logging(settings.log_level)

    syncer = PublicSyncer(settings)
    if args.command == "once":
        asyncio.run(syncer.run_once_with_lifecycle())
        return
    asyncio.run(syncer.run())


if __name__ == "__main__":
    main()
