from __future__ import annotations

import argparse
import logging

import uvicorn

from .settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="public-api")
    parser.add_argument("command", choices=["run"], nargs="?", default="run")
    args = parser.parse_args()

    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if args.command == "run":
        uvicorn.run(
            "public_api.app:create_app",
            factory=True,
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level.lower(),
        )


if __name__ == "__main__":
    main()
