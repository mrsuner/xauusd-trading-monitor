from __future__ import annotations

import argparse
import asyncio

from .db import Database
from .logging import configure_logging
from .model_client import build_auxiliary_model_client, build_model_client
from .settings import Settings
from .worker import NormalizerClassifierWorker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize and classify raw news items")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Run the normalizer-classifier worker")
    return parser.parse_args()


async def run_worker() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    db = Database(settings.database_url)
    model_client = build_model_client(settings)
    auxiliary_model_client = build_auxiliary_model_client(settings)
    worker = NormalizerClassifierWorker(settings, db, model_client, auxiliary_model_client)
    await worker.run()


def main() -> None:
    args = parse_args()
    if args.command == "run":
        asyncio.run(run_worker())


if __name__ == "__main__":
    main()
