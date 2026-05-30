"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-30 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create extension if not exists pgcrypto")
    op.execute("create extension if not exists pg_trgm")

    op.execute(
        """
        create table sources (
          id uuid primary key default gen_random_uuid(),
          name text not null,
          handle_or_url text not null,
          source_type text not null,
          source_group text not null,
          official_level text not null,
          stance text,
          language text,
          priority text not null,
          reliability_score smallint not null default 50,
          latency_score smallint not null default 50,
          requires_confirmation boolean not null default true,
          enabled boolean not null default true,
          source_config jsonb not null default '{}'::jsonb,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint sources_source_type_check check (
            source_type in ('telegram', 'rss', 'atom', 'html_polling', 'api')
          ),
          constraint sources_official_level_check check (
            official_level in (
              'official',
              'semi_official',
              'unofficial',
              'unofficial_mirror',
              'aggregator'
            )
          ),
          constraint sources_priority_check check (
            priority in ('P0', 'P1', 'P2', 'P3')
          ),
          constraint sources_reliability_score_check check (
            reliability_score >= 0 and reliability_score <= 100
          ),
          constraint sources_latency_score_check check (
            latency_score >= 0 and latency_score <= 100
          )
        )
        """
    )

    op.execute(
        """
        create table raw_items (
          id uuid primary key default gen_random_uuid(),
          source_id uuid not null references sources(id),
          external_id text,
          published_at timestamptz,
          ingested_at timestamptz not null default now(),
          edited_at timestamptz,
          title text,
          text_raw text,
          text_clean text,
          language text,
          url text,
          media_type text not null default 'none',
          raw_json jsonb not null default '{}'::jsonb,
          content_hash text,
          dedupe_key text not null,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint raw_items_media_type_check check (
            media_type in (
              'none',
              'photo',
              'video',
              'document',
              'webpage',
              'mixed',
              'unknown'
            )
          )
        )
        """
    )

    op.execute(
        """
        create table raw_item_processing (
          id uuid primary key default gen_random_uuid(),
          raw_item_id uuid not null references raw_items(id) on delete cascade,
          stage text not null default 'normalize',
          status text not null default 'pending',
          is_relevant boolean,
          relevance_score smallint,
          filter_reason text,
          model_provider text,
          model_name text,
          model_output_json jsonb,
          normalized_json jsonb not null default '{}'::jsonb,
          event_id uuid,
          attempt_count integer not null default 0,
          next_retry_at timestamptz,
          locked_by text,
          locked_at timestamptz,
          error_message text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint raw_item_processing_stage_check check (
            stage in ('normalize', 'prefilter', 'classify', 'event_create', 'completed')
          ),
          constraint raw_item_processing_status_check check (
            status in ('pending', 'running', 'completed', 'skipped', 'failed', 'retry')
          ),
          constraint raw_item_processing_relevance_score_check check (
            relevance_score is null or (relevance_score >= 0 and relevance_score <= 100)
          )
        )
        """
    )

    op.execute(
        """
        create table events (
          id uuid primary key default gen_random_uuid(),
          event_time timestamptz,
          detected_at timestamptz not null default now(),
          event_type text not null,
          region text,
          primary_actor text,
          secondary_actor text,
          source_id uuid references sources(id),
          source_group text,
          severity text not null default 'C',
          relevance_score smallint not null default 0,
          confidence smallint,
          confirmation_state text not null default 'unconfirmed',
          title text,
          summary_zh text not null,
          summary_en text,
          market_relevance text,
          xauusd_impact_channel text[] not null default '{}'::text[],
          requires_confirmation boolean not null default true,
          raw_item_ids uuid[] not null default '{}'::uuid[],
          processing_id uuid references raw_item_processing(id),
          model_provider text,
          model_name text,
          model_output_json jsonb,
          dedupe_key text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint events_severity_check check (
            severity in ('S', 'A', 'B', 'C')
          ),
          constraint events_relevance_score_check check (
            relevance_score >= 0 and relevance_score <= 100
          ),
          constraint events_confidence_check check (
            confidence is null or (confidence >= 0 and confidence <= 100)
          ),
          constraint events_confirmation_state_check check (
            confirmation_state in (
              'unconfirmed',
              'partially_confirmed',
              'confirmed',
              'contradicted'
            )
          )
        )
        """
    )

    op.execute(
        """
        alter table raw_item_processing
          add constraint raw_item_processing_event_fk
          foreign key (event_id) references events(id)
        """
    )

    op.execute(
        """
        create table event_claims (
          id uuid primary key default gen_random_uuid(),
          event_id uuid not null references events(id) on delete cascade,
          source_id uuid references sources(id),
          raw_item_id uuid references raw_items(id),
          claim_group_id text,
          claim_text text not null,
          claim_direction text not null,
          stance text,
          confidence smallint,
          model_provider text,
          model_name text,
          model_output_json jsonb,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint event_claims_direction_check check (
            claim_direction in (
              'confirm',
              'deny',
              'warn',
              'escalate',
              'deescalate',
              'neutral',
              'unknown'
            )
          ),
          constraint event_claims_confidence_check check (
            confidence is null or (confidence >= 0 and confidence <= 100)
          )
        )
        """
    )

    op.execute(
        """
        create table alerts (
          id uuid primary key default gen_random_uuid(),
          event_id uuid not null references events(id) on delete cascade,
          channel text not null,
          priority text not null default 'normal',
          dedupe_key text not null,
          message text not null,
          sent_at timestamptz,
          delivery_status text not null default 'pending',
          attempt_count integer not null default 0,
          next_retry_at timestamptz,
          locked_by text,
          locked_at timestamptz,
          provider_response_json jsonb,
          error_message text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint alerts_channel_check check (
            channel in ('telegram', 'pushover')
          ),
          constraint alerts_priority_check check (
            priority in ('normal', 'high', 'emergency')
          ),
          constraint alerts_delivery_status_check check (
            delivery_status in ('pending', 'sent', 'failed', 'skipped', 'retry')
          )
        )
        """
    )

    op.execute(
        """
        create table source_health (
          id uuid primary key default gen_random_uuid(),
          source_id uuid not null references sources(id) on delete cascade,
          service_name text not null,
          status text not null default 'unknown',
          last_seen_at timestamptz,
          last_polled_at timestamptz,
          last_message_at timestamptz,
          last_success_at timestamptz,
          last_error_at timestamptz,
          last_error_message text,
          messages_ingested_1h integer not null default 0,
          messages_ingested_24h integer not null default 0,
          backfill_status text,
          backfill_started_at timestamptz,
          backfill_completed_at timestamptz,
          metadata jsonb not null default '{}'::jsonb,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint source_health_status_check check (
            status in ('unknown', 'healthy', 'degraded', 'failed', 'disabled')
          ),
          constraint source_health_backfill_status_check check (
            backfill_status is null or backfill_status in (
              'pending',
              'running',
              'completed',
              'failed'
            )
          )
        )
        """
    )

    op.execute("create unique index sources_type_handle_uidx on sources (source_type, lower(handle_or_url))")
    op.execute("create index sources_enabled_type_idx on sources (enabled, source_type)")
    op.execute("create index sources_group_priority_idx on sources (source_group, priority)")

    op.execute("create unique index raw_items_dedupe_key_uidx on raw_items (dedupe_key)")
    op.execute(
        """
        create unique index raw_items_source_external_uidx
          on raw_items (source_id, external_id)
          where external_id is not null
        """
    )
    op.execute("create index raw_items_source_published_idx on raw_items (source_id, published_at desc)")
    op.execute("create index raw_items_ingested_idx on raw_items (ingested_at desc)")
    op.execute("create index raw_items_content_hash_idx on raw_items (content_hash) where content_hash is not null")
    op.execute("create index raw_items_title_trgm_idx on raw_items using gin (title gin_trgm_ops) where title is not null")
    op.execute("create index raw_items_text_clean_trgm_idx on raw_items using gin (text_clean gin_trgm_ops) where text_clean is not null")

    op.execute("create unique index raw_item_processing_raw_item_uidx on raw_item_processing (raw_item_id)")
    op.execute("create index raw_item_processing_claim_idx on raw_item_processing (status, next_retry_at, created_at)")
    op.execute("create index raw_item_processing_locked_idx on raw_item_processing (locked_at) where status = 'running'")
    op.execute("create index raw_item_processing_relevance_idx on raw_item_processing (is_relevant, relevance_score desc)")

    op.execute("create unique index events_dedupe_key_uidx on events (dedupe_key) where dedupe_key is not null")
    op.execute("create index events_detected_idx on events (detected_at desc)")
    op.execute("create index events_severity_detected_idx on events (severity, detected_at desc)")
    op.execute("create index events_type_detected_idx on events (event_type, detected_at desc)")
    op.execute("create index events_source_group_idx on events (source_group, detected_at desc)")
    op.execute("create index events_relevance_idx on events (relevance_score desc, detected_at desc)")

    op.execute("create index event_claims_event_idx on event_claims (event_id)")
    op.execute("create index event_claims_group_idx on event_claims (claim_group_id) where claim_group_id is not null")
    op.execute("create index event_claims_source_idx on event_claims (source_id, created_at desc)")

    op.execute("create unique index alerts_dedupe_key_uidx on alerts (dedupe_key)")
    op.execute("create index alerts_delivery_claim_idx on alerts (delivery_status, next_retry_at, created_at)")
    op.execute("create index alerts_event_idx on alerts (event_id)")
    op.execute("create index alerts_channel_created_idx on alerts (channel, created_at desc)")

    op.execute("create unique index source_health_source_service_uidx on source_health (source_id, service_name)")
    op.execute("create index source_health_status_idx on source_health (status, updated_at desc)")
    op.execute("create index source_health_service_idx on source_health (service_name, updated_at desc)")

    op.execute(
        """
        create or replace function set_updated_at()
        returns trigger as $$
        begin
          new.updated_at = now();
          return new;
        end;
        $$ language plpgsql
        """
    )

    for table_name in (
        "sources",
        "raw_items",
        "raw_item_processing",
        "events",
        "event_claims",
        "alerts",
        "source_health",
    ):
        op.execute(
            f"""
            create trigger trg_{table_name}_updated_at
            before update on {table_name}
            for each row execute function set_updated_at()
            """
        )

    op.execute(
        """
        create or replace function enqueue_raw_item_processing()
        returns trigger as $$
        begin
          insert into raw_item_processing (raw_item_id)
          values (new.id)
          on conflict (raw_item_id) do nothing;

          perform pg_notify('raw_item_created', new.id::text);
          return new;
        end;
        $$ language plpgsql
        """
    )

    op.execute(
        """
        create trigger trg_raw_items_enqueue_processing
        after insert on raw_items
        for each row execute function enqueue_raw_item_processing()
        """
    )

    op.execute(
        """
        create or replace function notify_event_created()
        returns trigger as $$
        begin
          perform pg_notify('event_created', new.id::text);
          return new;
        end;
        $$ language plpgsql
        """
    )

    op.execute(
        """
        create trigger trg_events_notify_created
        after insert on events
        for each row execute function notify_event_created()
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_events_notify_created on events")
    op.execute("drop function if exists notify_event_created()")
    op.execute("drop trigger if exists trg_raw_items_enqueue_processing on raw_items")
    op.execute("drop function if exists enqueue_raw_item_processing()")

    for table_name in (
        "source_health",
        "alerts",
        "event_claims",
        "events",
        "raw_item_processing",
        "raw_items",
        "sources",
    ):
        op.execute(f"drop trigger if exists trg_{table_name}_updated_at on {table_name}")

    op.execute("drop function if exists set_updated_at()")
    op.execute("drop table if exists source_health")
    op.execute("drop table if exists alerts")
    op.execute("drop table if exists event_claims")
    op.execute("alter table if exists raw_item_processing drop constraint if exists raw_item_processing_event_fk")
    op.execute("drop table if exists events")
    op.execute("drop table if exists raw_item_processing")
    op.execute("drop table if exists raw_items")
    op.execute("drop table if exists sources")
