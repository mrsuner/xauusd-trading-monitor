"""Verify migrations and concurrent budgets in a disposable, localhost-only PostgreSQL.

Run with services/normalizer-classifier/.venv/bin/python. Migrations use the
repository .venv. Never accepts a production database URL.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import psycopg

ROOT = Path(__file__).resolve().parents[2]
for service in ("normalizer-classifier", "public-syncer", "public-api"):
    sys.path.insert(0, str(ROOT / "services" / service / "src"))
from normalizer_classifier.db import Database
from normalizer_classifier.models import AIModelCallUsage, AuxiliaryModelResponse, AuxiliaryTextResult
from public_syncer.db import raw_item_translations_select_sql
from public_syncer.models import PublicRawItem
from public_syncer.payload import build_raw_item_payload
from public_api.models import PublicRawItemIngestRequest
from public_api.db import Database as PublicDatabase, PublicRepository


def docker(*args: str) -> str:
    return subprocess.check_output(["docker", *args], text=True).strip()


async def verify(url: str) -> dict:
    db = Database(url, min_size=1, max_size=12)
    await db.connect()
    try:
        with psycopg.connect(url) as conn:
            source_id = conn.execute("select id from sources limit 1").fetchone()[0]
            ids = [uuid4() for _ in range(10)]
            for item in ids:
                conn.execute("insert into raw_items (id,source_id,dedupe_key) values (%s,%s,%s)",
                             (item, source_id, f"budget-fixture:{item}"))
        outcomes = await asyncio.gather(*(db.reserve_ai_tokens(raw_item_id=item, tokens=10,
            item_limit=100, daily_limit=30) for item in ids))
        assert outcomes.count(None) == 3, outcomes
        with psycopg.connect(url) as conn:
            assert conn.execute("select sum(tokens_reserved) from ai_daily_budgets").fetchone()[0] == 30
            assert conn.execute("select sum(tokens_reserved) from ai_item_token_budgets").fetchone()[0] == 30
            conn.execute("update ai_daily_budgets set tokens_reserved=0")
            conn.execute("delete from ai_item_token_budgets")
        outcomes = await asyncio.gather(*(db.reserve_ai_tokens(raw_item_id=ids[0], tokens=10,
            item_limit=25, daily_limit=1000) for _ in range(10)))
        assert outcomes.count(None) == 2, outcomes
        with psycopg.connect(url) as conn:
            assert conn.execute("select sum(tokens_reserved) from ai_daily_budgets").fetchone()[0] == 20
            assert conn.execute("select tokens_reserved from ai_item_token_budgets where raw_item_id=%s", (ids[0],)).fetchone()[0] == 20
            # A new daily window cannot reset lifetime per-item reservations.
            conn.execute("update ai_daily_budgets set tokens_reserved=0")
        other = Database(url, min_size=1, max_size=2)
        await other.connect()
        try:
            assert await other.reserve_ai_tokens(raw_item_id=ids[0], tokens=10,
                item_limit=25, daily_limit=1000) == "item_token_budget_reached"
        finally:
            await other.close()
        with psycopg.connect(url) as conn:
            assert conn.execute("select sum(tokens_reserved) from ai_daily_budgets").fetchone()[0] == 0
        assert await db.reserve_ai_request(kind="classification", total_limit=1, kind_limit=1)
        assert not await db.reserve_ai_request(kind="classification", total_limit=1, kind_limit=1)
        return dict(daily_race_allowed=3, item_race_allowed=2, item_budget_survives_new_client_and_daily_reset=True,
                    denied_reservation_does_not_debit=True, request_count_budget_preserved=True)
    finally:
        await db.close()


def reject_full_text(conn, table: str) -> None:
    try:
        with conn.transaction():
            conn.execute(f"update {table} set full_translation='invalid full text' where status='summary_only'")
    except psycopg.errors.CheckViolation:
        return
    raise AssertionError("summary_only incorrectly accepted full text")


async def summary_payload(url: str) -> dict:
    languages = ("zh-Hant", "en", "th", "ja")
    db = Database(url, min_size=1, max_size=2, translation_output_languages=languages)
    await db.connect()
    try:
        with psycopg.connect(url) as conn:
            item = conn.execute("select id from raw_items limit 1").fetchone()[0]
            conn.execute("update raw_items set title='Budget fixture',text_clean='Original fixture text.' where id=%s", (item,))
        response = AuxiliaryModelResponse(provider="translation_primary", api_provider="ollama_cloud", model="fixture",
            raw_output={}, usage=AIModelCallUsage(ai_layer="translation_summary", route_name="translation_primary",
                provider="ollama_cloud", model_name="fixture", request_kind="translate_summary", success=True),
            result=AuxiliaryTextResult(translations=[dict(language=lang, summary=text, full_translation=None)
                for lang, text in zip(languages, ("新聞摘要", "News summary", "สรุปข่าว", "ニュース要約"))]))
        await db.update_translation_result(raw_item_id=item, response=response, status="summary_only", input_chars=22)
        with psycopg.connect(url, row_factory=psycopg.rows.dict_row) as conn:
            row = conn.execute(f"select r.*, {raw_item_translations_select_sql()} as translations from raw_items r where id=%s", (item,)).fetchone()
            assert row["translation_status"] == "summary_only"
            assert row["text_clean"] == "Original fixture text."
            assert len(row["translations"]) == 4
            reject_full_text(conn, "raw_item_translations")
        item = PublicRawItem(**row, source_updated_at=row["updated_at"])
        payload = build_raw_item_payload(item, max_original_chars=4000, max_translation_chars=8000,
                                        sync_languages=languages)
        validated = PublicRawItemIngestRequest.model_validate(payload)
        assert len(validated.translations) == 4
        assert all(t.status == "summary_only" and t.full_translation is None for t in validated.translations)
        return payload
    finally:
        await db.close()


async def public_ingest(url: str, payload: dict) -> None:
    db = PublicDatabase(url)
    await db.connect()
    try:
        repo = PublicRepository(db, max_page_size=50)
        accepted = await repo.ingest_raw_item(PublicRawItemIngestRequest.model_validate(payload),
            raw_body=json.dumps(payload).encode(), key_id=None, nonce=None)
        assert accepted["status"] == "accepted"
    finally:
        await db.close()
    with psycopg.connect(url) as conn:
        rows = conn.execute("select status,summary,full_translation from public_raw_item_translations").fetchall()
        assert len(rows) == 4 and all(status == "summary_only" and summary and full is None for status, summary, full in rows)
        reject_full_text(conn, "public_raw_item_translations")


def main() -> None:
    name = f"tickbase-budget-test-{uuid4().hex[:10]}"
    created = False
    report = {}
    try:
        docker("run", "--detach", "--rm", "--name", name,
               "--tmpfs", "/var/lib/postgresql/data:rw,noexec,nosuid",
               "--publish", "127.0.0.1::5432", "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:16.14-alpine")
        created = True
        port = docker("port", name, "5432/tcp").split(":")[-1]
        url = f"postgresql://postgres@127.0.0.1:{port}/postgres"
        for _ in range(60):
            try:
                with psycopg.connect(url, connect_timeout=1) as conn:
                    conn.execute("select 1")
                # Initdb starts a temporary server before the final process.
                if docker("exec", name, "sh", "-c", "cat /proc/1/comm") == "postgres":
                    break
            except psycopg.Error:
                pass
            time.sleep(.2)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")
        env = dict(os.environ, DATABASE_URL=url, PUBLIC_DATABASE_URL=url)
        def migrate(config: str, *args: str) -> None:
            subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "alembic", "-c", str(ROOT / config), *args],
                           cwd=(ROOT / config).parent, env=env, check=True, capture_output=True, text=True)
        migrate("db/alembic.ini", "upgrade", "head")
        report["concurrency"] = asyncio.run(verify(url))
        payload = asyncio.run(summary_payload(url))
        migrate("db/alembic.ini", "downgrade", "0026_ai_daily_budgets")
        with psycopg.connect(url) as conn:
            rows = conn.execute("select status,summary,full_translation from raw_item_translations").fetchall()
            assert rows and all(status == "skipped" and summary and full is None for status, summary, full in rows)
        migrate("db/alembic.ini", "upgrade", "head")
        report["private_upgrade_downgrade_upgrade"] = True
        # Use a separate database to avoid sharing alembic_version with private.
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute("create database public_budget_test")
        env["DATABASE_URL"] = env["PUBLIC_DATABASE_URL"] = url.rsplit("/", 1)[0] + "/public_budget_test"
        migrate("services/public-api/alembic.ini", "upgrade", "head")
        report["public_fresh_upgrade"] = True
        asyncio.run(public_ingest(env["PUBLIC_DATABASE_URL"], payload))
        report["summary_only_private_storage_sync_payload_api_ingest_public_storage"] = True
        report["summary_only_full_text_rejected_by_both_databases"] = True
        migrate("services/public-api/alembic.ini", "downgrade", "0009_digest_content_lifecycle")
        migrate("services/public-api/alembic.ini", "upgrade", "head")
        with psycopg.connect(env["PUBLIC_DATABASE_URL"]) as conn:
            rows = conn.execute("select status,summary,full_translation from public_raw_item_translations").fetchall()
            assert rows and all(status == "skipped" and summary and full is None for status, summary, full in rows)
        report["public_upgrade_downgrade_upgrade_preserves_summaries_without_full_completion"] = True
    except subprocess.CalledProcessError as exc:
        raise RuntimeError((exc.stderr or exc.output or "disposable verifier command failed")[-5000:]) from exc
    finally:
        if created:
            docker("rm", "--force", name)
            report["disposable_postgres_removed"] = True
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
