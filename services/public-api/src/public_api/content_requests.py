"""Preview or apply a content withdrawal against the operator's explicit database.

Use PUBLIC_DATABASE_URL with an operator role that can update public and notify.
No content is deleted; hidden rows remain as tombstones against resynchronization.
"""

from __future__ import annotations

import argparse
import json
import os
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.pq import TransactionStatus


def withdraw(conn: psycopg.Connection, *, raw_item_id: UUID | None = None,
             event_id: UUID | None = None, reason: str, apply: bool = False) -> dict:
    if (raw_item_id is None) == (event_id is None):
        raise ValueError("Choose exactly one public raw item or public event ID.")
    if not reason.strip() or len(reason) > 200:
        raise ValueError("Use a non-sensitive public reason between 1 and 200 characters.")

    standalone = conn.info.transaction_status == TransactionStatus.IDLE
    with conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
        if not apply and standalone:
            cur.execute("SET TRANSACTION READ ONLY")
        if raw_item_id:
            cur.execute("SELECT upstream_raw_item_id, upstream_event_ids FROM public.public_raw_items WHERE id = %s",
                        (raw_item_id,))
            raw = cur.fetchone()
            if raw is None:
                raise ValueError("Public raw item not found.")
            if apply:
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("raw:" + str(raw["upstream_raw_item_id"]),))
                cur.execute("SELECT upstream_event_ids FROM public.public_raw_items WHERE id = %s", (raw_item_id,))
                raw = cur.fetchone()
            upstream_ids = raw["upstream_event_ids"]
        else:
            cur.execute("SELECT upstream_event_id FROM public.public_events WHERE id = %s", (event_id,))
            event = cur.fetchone()
            if event is None:
                raise ValueError("Public event not found.")
            upstream_ids = [event["upstream_event_id"]]

        # Same lock as ingestion: another payload version cannot resurrect this event.
        if apply:
            for upstream_id in sorted(upstream_ids):
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(upstream_id),))
        cur.execute("SELECT id FROM public.public_events WHERE upstream_event_id = ANY(%s::uuid[]) ORDER BY id",
                    (upstream_ids,))
        event_ids = [row["id"] for row in cur.fetchall()]
        cur.execute("SELECT DISTINCT edition_id FROM notify.digest_edition_events WHERE public_event_id = ANY(%s::uuid[])",
                    (event_ids,))
        edition_ids = [row["edition_id"] for row in cur.fetchall()]
        cur.execute("SELECT count(*) AS count FROM notify.deliveries WHERE public_event_id = ANY(%s::uuid[]) AND status IN ('pending', 'retry')",
                    (event_ids,))
        pending = cur.fetchone()["count"]
        result = {"applied": apply, "raw_item_id": str(raw_item_id) if raw_item_id else None,
                  "event_ids": [str(id) for id in event_ids],
                  "digest_ids": [str(id) for id in edition_ids], "pending_notifications": pending}
        if not apply:
            return result

        if raw_item_id:
            cur.execute("""UPDATE public.public_raw_items SET is_visible = false, updated_at = now(),
                           scrub_metadata = scrub_metadata || jsonb_build_object('withdrawal',
                               jsonb_build_object('reason', %s::text, 'at', now()))
                           WHERE id = %s""", (reason, raw_item_id))
        cur.execute("""UPDATE public.public_events
                       SET is_visible = false, invalidated_at = coalesce(invalidated_at, now()),
                           invalidation_kind = coalesce(invalidation_kind, 'withdrawal'),
                           invalidation_reason = coalesce(invalidation_reason, %s), updated_at = now()
                       WHERE id = ANY(%s::uuid[])""", (reason, event_ids))
        cur.execute("""UPDATE notify.deliveries SET status = 'canceled', error_code = 'event_unavailable', updated_at = now()
                       WHERE public_event_id = ANY(%s::uuid[]) AND status IN ('pending', 'retry')""", (event_ids,))
        cur.execute("""UPDATE notify.digest_editions
                       SET status = 'invalidated', invalidated_at = coalesce(invalidated_at, now()),
                           invalidation_kind = coalesce(invalidation_kind, 'withdrawal'),
                           invalidation_reason = coalesce(invalidation_reason, %s), updated_at = now()
                       WHERE id = ANY(%s::uuid[])""", (reason, edition_ids))
        # Cancel pending batches rather than delivering an already frozen withdrawn summary.
        cur.execute("""UPDATE notify.digest_batches SET status = 'canceled', error_code = 'edition_invalidated', updated_at = now()
                       WHERE status IN ('pending', 'retry') AND id IN (
                           SELECT batch_id FROM notify.digest_batch_editions WHERE edition_id = ANY(%s::uuid[])
                       )""", (edition_ids,))
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--raw-item-id", type=UUID, help="Public raw item ID, not upstream ID")
    target.add_argument("--event-id", type=UUID, help="Public event ID, not upstream ID")
    parser.add_argument("--reason", default="Content withdrawn following a content request.")
    parser.add_argument("--apply", action="store_true", help="Apply withdrawal; omitted means read-only preview")
    args = parser.parse_args()
    url = os.getenv("PUBLIC_DATABASE_URL")
    if not url:
        parser.error("PUBLIC_DATABASE_URL must explicitly identify the target database.")
    try:
        with psycopg.connect(url, autocommit=True) as conn:
            result = withdraw(conn, raw_item_id=args.raw_item_id, event_id=args.event_id,
                              reason=args.reason, apply=args.apply)
    except (ValueError, psycopg.Error):
        # Do not print connection strings, credentials or raw complaint material.
        print("Withdrawal failed. Verify target ID, schema and operator permissions; transaction was rolled back.")
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
