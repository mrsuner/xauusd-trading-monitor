"""tickbase anomaly ingest table + feed source seed

Revision ID: 0016_tickbase_anomaly_ingest
Revises: 0015_partial_translation_status
Create Date: 2026-06-08 15:40:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0016_tickbase_anomaly_ingest"
down_revision = "0015_partial_translation_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Mirror / idempotency / cursor table for the tickbase anomaly feed.
    # `tickbase_id` is the upstream monotonic event id and doubles as the
    # idempotency key; the cursor is derived as max(tickbase_id), so no
    # separate cursor table is needed.
    op.execute(
        """
        create table tickbase_anomaly_ingest (
          tickbase_id bigint primary key,
          event_id uuid not null references events(id),
          rule_id text not null,
          asset_class text not null,
          base text not null,
          quote text not null,
          direction text not null,
          metric text not null,
          triggered_at timestamptz not null,
          raw jsonb not null default '{}'::jsonb,
          ingested_at timestamptz not null default now()
        )
        """
    )
    op.execute(
        "create index tickbase_anomaly_ingest_triggered_idx "
        "on tickbase_anomaly_ingest (triggered_at desc)"
    )

    # Seed a source row representing the tickbase anomaly feed so that
    # events.source_id points at a real source (dashboard-api / public-syncer
    # inner-join events -> sources). source_group MUST avoid AGGREGATOR_GROUPS
    # ({osint_aggregator, market_squawk}) used by event-router penalties.
    op.get_bind().exec_driver_sql(
        """
        insert into sources (
          name, handle_or_url, source_type, source_group, official_level,
          stance, language, priority, reliability_score, latency_score,
          requires_confirmation, translation_policy, enabled, source_config
        ) values (
          'TickBase Anomaly Feed',
          'https://api.thetickbase.com/v1/anomaly-events',
          'api', 'market_anomaly', 'official',
          'Rule-based market anomaly detector operated by tickbase.', 'en',
          'P1', 90, 90,
          false, 'disabled', true,
          '{"upstream":"tickbase","kind":"anomaly_feed"}'::jsonb
        )
        on conflict (source_type, lower(handle_or_url)) do update
        set name = excluded.name,
            source_group = excluded.source_group,
            official_level = excluded.official_level,
            priority = excluded.priority,
            requires_confirmation = excluded.requires_confirmation,
            translation_policy = excluded.translation_policy,
            enabled = excluded.enabled,
            source_config = excluded.source_config,
            updated_at = now()
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists tickbase_anomaly_ingest")
    op.execute(
        "delete from sources "
        "where source_type = 'api' "
        "and lower(handle_or_url) = lower('https://api.thetickbase.com/v1/anomaly-events')"
    )
