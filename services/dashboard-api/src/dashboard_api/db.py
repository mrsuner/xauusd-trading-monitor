from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping
from contextlib import suppress
from typing import Any

import psycopg
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("invalid integer environment value", extra={"env_name": name, "env_value": raw})
        return default
    return max(value, 1)


def _positive_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("invalid float environment value", extra={"env_name": name, "env_value": raw})
        return default
    return max(value, 0.1)


class Database:
    def __init__(self, database_url: str, *, min_size: int = 1, max_size: int = 10) -> None:
        self._database_url = database_url
        self._min_size = min_size
        self._max_size = max_size
        self._pool = self._create_pool()

    def _create_pool(self) -> AsyncConnectionPool:
        return AsyncConnectionPool(
            self._database_url,
            min_size=self._min_size,
            max_size=self._max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )

    async def connect(self) -> None:
        max_attempts = _positive_int_env("DB_CONNECT_MAX_ATTEMPTS", 10)
        delay_seconds = _positive_float_env("DB_CONNECT_INITIAL_BACKOFF_SECONDS", 1.0)
        max_delay_seconds = _positive_float_env("DB_CONNECT_MAX_BACKOFF_SECONDS", 30.0)

        for attempt in range(1, max_attempts + 1):
            try:
                await self._pool.open(wait=True)
                return
            except Exception:
                with suppress(Exception):
                    await self._pool.close()
                if attempt >= max_attempts:
                    logger.exception(
                        "database pool connection failed after retries",
                        extra={"attempt": attempt, "max_attempts": max_attempts},
                    )
                    raise
                logger.warning(
                    "database pool connection failed; retrying",
                    extra={
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "retry_in_seconds": delay_seconds,
                    },
                    exc_info=True,
                )
                await asyncio.sleep(delay_seconds)
                delay_seconds = min(delay_seconds * 2, max_delay_seconds)
                self._pool = self._create_pool()

    async def close(self) -> None:
        await self._pool.close()

    async def ping(self) -> bool:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("select 1")
                row = await cur.fetchone()
        return bool(row)

    async def fetch_one(self, sql: str, params: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, dict(params or {}))
                return await cur.fetchone()

    async def fetch_all(self, sql: str, params: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, dict(params or {}))
                rows = await cur.fetchall()
        return list(rows)

    async def execute(self, sql: str, params: Mapping[str, Any] | None = None) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, dict(params or {}))
