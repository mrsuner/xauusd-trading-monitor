from __future__ import annotations

import argparse

import uvicorn

from .logging import configure_logging
from .settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="public-api")
    parser.add_argument("command", choices=["run"], nargs="?", default="run")
    args = parser.parse_args()

    settings = Settings()
    configure_logging(settings.log_level)

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
