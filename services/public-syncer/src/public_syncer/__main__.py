from __future__ import annotations

import argparse
import asyncio
import logging

from .settings import Settings
from .worker import PublicSyncer


def main() -> None:
    parser = argparse.ArgumentParser(prog="public-syncer")
    parser.add_argument("command", choices=["run", "once"], nargs="?", default="run")
    args = parser.parse_args()

    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    syncer = PublicSyncer(settings)
    if args.command == "once":
        asyncio.run(syncer.run_once_with_lifecycle())
        return
    asyncio.run(syncer.run())


if __name__ == "__main__":
    main()
