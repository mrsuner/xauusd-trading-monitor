from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from psycopg import Connection

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def database_url() -> str:
    url = os.environ.get("PUBLIC_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("PUBLIC_DATABASE_URL or DATABASE_URL is required")
    return url


def run_migrations_online() -> None:
    with Connection.connect(database_url()) as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
