#!/usr/bin/env python3
"""Backfill and verify private event summary translation rows.

The command never overwrites an existing translation. Conflicts remain visible to
the verifier and must be resolved explicitly before the reader/writer cutover.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

LANGUAGE_COLUMNS = {
    "zh-Hant": "summary_zh",
    "en": "summary_en",
}


@dataclass(frozen=True)
class Coverage:
    source: int
    target: int
    missing: int
    conflicts: int
    empty_source: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("backfill", "verify"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args()


def coverage(conn: psycopg.Connection[dict[str, object]], language: str, column: str) -> Coverage:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            select
              count(*) filter (where e.{column} is not null and btrim(e.{column}) <> '') as source,
              count(et.event_id) as target,
              count(*) filter (
                where e.{column} is not null and btrim(e.{column}) <> '' and et.event_id is null
              ) as missing,
              count(*) filter (
                where e.{column} is not null and btrim(e.{column}) <> ''
                  and et.event_id is not null and et.summary <> e.{column}
              ) as conflicts,
              count(*) filter (where e.{column} is null or btrim(e.{column}) = '') as empty_source
            from events e
            left join event_translations et
              on et.event_id = e.id and et.language = %s
            """,
            (language,),
        )
        row = cur.fetchone()
    assert row is not None
    return Coverage(**{name: int(row[name]) for name in Coverage.__dataclass_fields__})


def backfill_language(
    conn: psycopg.Connection[dict[str, object]],
    language: str,
    column: str,
    batch_size: int,
) -> int:
    copied = 0
    while True:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(
                f"""
                with candidates as (
                  select e.id, e.{column} as summary, e.created_at, e.updated_at
                  from events e
                  left join event_translations et
                    on et.event_id = e.id and et.language = %s
                  where e.{column} is not null
                    and btrim(e.{column}) <> ''
                    and et.event_id is null
                  order by e.id
                  limit %s
                  for update of e skip locked
                )
                insert into event_translations (
                  event_id, language, summary, created_at, updated_at
                )
                select id, %s, summary, created_at, updated_at
                from candidates
                on conflict (event_id, language) do nothing
                returning event_id
                """,
                (language, batch_size, language),
            )
            batch_count = len(cur.fetchall())
        copied += batch_count
        print(f"language={language} copied={copied} last_batch={batch_count}")
        if batch_count < batch_size:
            return copied


def main() -> int:
    args = parse_args()
    if not args.database_url:
        print("DATABASE_URL or --database-url is required", file=sys.stderr)
        return 2
    if args.batch_size < 1:
        print("--batch-size must be greater than zero", file=sys.stderr)
        return 2

    with psycopg.connect(args.database_url, row_factory=dict_row) as conn:
        if args.action == "backfill":
            for language, column in LANGUAGE_COLUMNS.items():
                backfill_language(conn, language, column, args.batch_size)

        failed = False
        for language, column in LANGUAGE_COLUMNS.items():
            result = coverage(conn, language, column)
            print(
                f"language={language} source={result.source} target={result.target} "
                f"missing={result.missing} conflicts={result.conflicts} "
                f"empty_source={result.empty_source}"
            )
            failed = failed or result.missing > 0 or result.conflicts > 0
        return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
