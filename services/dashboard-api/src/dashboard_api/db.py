from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import psycopg
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row


class Database:
    def __init__(self, database_url: str, *, min_size: int = 1, max_size: int = 10) -> None:
        self._database_url = database_url
        self._pool = AsyncConnectionPool(
            database_url,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )

    async def connect(self) -> None:
        await self._pool.open()

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
