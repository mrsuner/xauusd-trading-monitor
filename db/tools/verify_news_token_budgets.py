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
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import psycopg
import httpx

ROOT = Path(__file__).resolve().parents[2]
for service in ("normalizer-classifier", "public-syncer", "public-api"):
    sys.path.insert(0, str(ROOT / "services" / service / "src"))
from normalizer_classifier.db import Database
from normalizer_classifier.models import AIModelCallUsage, AuxiliaryModelResponse, AuxiliaryTextResult, RawItem, SourceMetadata, NormalizedItem
from normalizer_classifier.settings import Settings
from normalizer_classifier.model_client import build_model_client, build_translation_model_clients
from normalizer_classifier.worker import NormalizerClassifierWorker
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
        peer = Database(url, min_size=1, max_size=6)
        await peer.connect()
        try:
            outcomes = await asyncio.gather(*((db if index % 2 else peer).reserve_ai_tokens(raw_item_id=item, tokens=10,
                item_limit=100, daily_limit=30) for index, item in enumerate(ids)))
        finally:
            await peer.close()
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
        # Budget deferrals happen before HTTP and must not consume model retries.
        with psycopg.connect(url) as conn:
            processing_id = conn.execute("select id from raw_item_processing where raw_item_id=%s", (ids[0],)).fetchone()[0]
            conn.execute("update raw_item_processing set status='running', attempt_count=1 where id=%s", (processing_id,))
        for _ in range(3):
            await db.defer_for_model_budget(processing_id=processing_id, reason="daily_token_budget_reached")
            with psycopg.connect(url) as conn:
                row = conn.execute("select status,attempt_count from raw_item_processing where id=%s", (processing_id,)).fetchone()
                assert row == ("retry", 0), row
                conn.execute("update raw_item_processing set status='running',attempt_count=attempt_count+1 where id=%s", (processing_id,))
        await db.mark_failed(processing_id=processing_id, attempt_count=1, max_attempts=3, error_message="first actual model failure")
        with psycopg.connect(url) as conn:
            assert conn.execute("select status from raw_item_processing where id=%s", (processing_id,)).fetchone()[0] == "retry"
            conn.execute("update raw_item_processing set status='running',attempt_count=3 where id=%s", (processing_id,))
        await db.defer_for_model_budget(processing_id=processing_id)
        await db.defer_for_model_budget(processing_id=processing_id)
        with psycopg.connect(url) as conn:
            assert conn.execute("select attempt_count from raw_item_processing where id=%s", (processing_id,)).fetchone()[0] == 2
        return dict(daily_race_allowed=3, item_race_allowed=2, item_budget_survives_new_client_and_daily_reset=True,
                    denied_reservation_does_not_debit=True, request_count_budget_preserved=True,
                    budget_deferrals_do_not_consume_classification_retries=True,
                    repeated_deferral_is_idempotent=True, independent_worker_pools_share_daily_cap=True)
    finally:
        await db.close()


def reject_full_text(conn, table: str) -> None:
    try:
        with conn.transaction():
            conn.execute(f"update {table} set full_translation='invalid full text' where status='summary_only'")
    except psycopg.errors.CheckViolation:
        return
    raise AssertionError("summary_only incorrectly accepted full text")


async def verify_worker_repair_budget(url: str) -> dict:
    config = Settings(DATABASE_URL=url, CLOUD_MODEL_API_KEY="fixture", OLLAMA_API_KEY="fixture",
        TRANSLATION_MODEL_PROVIDER="ollama_cloud", OLLAMA_CLOUD_TRANSLATION_MODEL="fixture",
        TRANSLATION_PAID_FALLBACK_ENABLED=True, TRANSLATION_FALLBACK_PROVIDER="openrouter",
        TRANSLATION_FALLBACK_MODEL_NAME="fixture-fallback", TRANSLATION_MODEL_API_KEY="fixture",
        TRANSLATION_OUTPUT_LANGUAGES="zh-Hant,en,th,ja", AI_ITEM_TOKEN_LIMIT=29000)
    db = Database(url, min_size=1, max_size=2, translation_output_languages=config.translation_output_languages)
    await db.connect()
    try:
        item = uuid4()
        with psycopg.connect(url) as conn:
            source_id = conn.execute("select id from sources limit 1").fetchone()[0]
            conn.execute("insert into raw_items (id,source_id,dedupe_key) values (%s,%s,%s)",
                         (item, source_id, f"repair-budget:{item}"))
        raw = RawItem(id=item, source_id=source_id, ingested_at=datetime.now(timezone.utc),
            text_raw="A reported policy review.", dedupe_key=f"repair-budget:{item}", raw_json={}, media_type="none")
        source = SourceMetadata(id=source_id, name="Fixture", handle_or_url="https://example.test",
            source_type="rss", source_group="fixture", official_level="official", priority="P1",
            reliability_score=80, latency_score=80, requires_confirmation=True)
        normalized = NormalizedItem(text_clean=raw.text_raw, language="en", keyword_score=70, prefilter_passed=True)
        worker = NormalizerClassifierWorker(config, db, build_model_client(config), build_translation_model_clients(config))
        calls = []

        async def post(http, endpoint, **kwargs):
            calls.append(endpoint)
            value = {"translations": [dict(language=lang, summary=summary, full_translation=raw.text_raw)
                for lang, summary in zip(config.translation_output_languages,
                    ("新聞摘要", "News summary", "สรุปข่าว", "ニュース要約"))]}
            body = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(value)}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}}
            return httpx.Response(200, json=body, request=httpx.Request("POST", endpoint))

        with patch.object(httpx.AsyncClient, "post", post):
            await worker._run_translation_summary(SimpleNamespace(raw_item=raw, source=source), normalized)
        assert len(calls) == 2 and all("ollama.com" in call for call in calls), calls
        with psycopg.connect(url) as conn:
            reserved = conn.execute("select tokens_reserved from ai_item_token_budgets where raw_item_id=%s", (item,)).fetchone()[0]
            assert 20000 < reserved <= 29000, reserved
            assert conn.execute("select count(*) from ai_model_calls where raw_item_id=%s", (item,)).fetchone()[0] == 2
            assert "item_token_budget_reached" in conn.execute("select translation_error from raw_items where id=%s", (item,)).fetchone()[0]
            assert conn.execute("select translation_model_provider,translation_model from raw_items where id=%s", (item,)).fetchone() == ("translation_primary", "fixture")
        return dict(script_attempts=2, fallback_http_calls=0, actual_shared_reservations=reserved,
                    item_limit=29000, failed_attempt_usage_rows=2)
    finally:
        await db.close()


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
        # Replacing existing full translations must actively clear their full text.
        full_response = response.model_copy(deep=True)
        for translation in full_response.result.translations:
            translation.full_translation = translation.summary
        await db.update_translation_result(raw_item_id=item, response=full_response, status="completed", input_chars=22)
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
        full_payload = json.loads(json.dumps(payload))
        for translation in full_payload["translations"]:
            translation["status"] = "completed"
            translation["full_translation"] = translation["summary"]
        first = await repo.ingest_raw_item(PublicRawItemIngestRequest.model_validate(full_payload),
            raw_body=json.dumps(full_payload).encode(), key_id=None, nonce=None)
        assert first["status"] == "accepted"
        accepted = await repo.ingest_raw_item(PublicRawItemIngestRequest.model_validate(payload),
            raw_body=json.dumps(payload).encode(), key_id=None, nonce=None)
        assert accepted["status"] == "duplicate"
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
        report["worker_repair_and_fallback_budget"] = asyncio.run(verify_worker_repair_budget(url))
        payload = asyncio.run(summary_payload(url))
        migrate("db/alembic.ini", "downgrade", "0026_ai_daily_budgets")
        with psycopg.connect(url) as conn:
            rows = conn.execute("select status,summary,full_translation from raw_item_translations where summary is not null").fetchall()
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
        report["full_to_summary_only_update_clears_full_text_in_both_databases"] = True
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
