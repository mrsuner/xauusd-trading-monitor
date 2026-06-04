"""create public website event tables

Revision ID: 0001_public_events
Revises:
Create Date: 2026-06-01 00:00:00
"""
from __future__ import annotations

from alembic import op

revision = "0001_public_events"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create extension if not exists pgcrypto")
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
    op.execute(
        """
        create table public_events (
          id uuid primary key default gen_random_uuid(),
          upstream_event_id uuid not null,
          idempotency_key text not null,
          schema_version text not null,
          event_time timestamptz,
          generated_at timestamptz,
          received_at timestamptz not null default now(),
          severity text not null,
          relevance_score smallint,
          confirmation_state text,
          public_title_zh text,
          public_summary_zh text,
          public_title_en text,
          public_summary_en text,
          public_source_links jsonb not null default '[]'::jsonb,
          topic_tags text[] not null default '{}'::text[],
          content_category text,
          mentioned_actors text[] not null default '{}'::text[],
          route_metadata jsonb not null default '{}'::jsonb,
          is_visible boolean not null default true,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          constraint public_events_schema_version_check check (schema_version in ('public_event.v1')),
          constraint public_events_severity_check check (severity in ('S', 'A', 'B', 'C')),
          constraint public_events_relevance_score_check check (
            relevance_score is null or (relevance_score >= 0 and relevance_score <= 100)
          ),
          constraint public_events_confirmation_state_check check (
            confirmation_state is null
            or confirmation_state in ('unconfirmed', 'partially_confirmed', 'confirmed', 'contradicted')
          ),
          constraint public_events_source_links_array_check check (jsonb_typeof(public_source_links) = 'array'),
          constraint public_events_route_metadata_object_check check (jsonb_typeof(route_metadata) = 'object')
        )
        """
    )
    op.execute("create unique index public_events_idempotency_key_uidx on public_events (idempotency_key)")
    op.execute("create index public_events_upstream_event_id_idx on public_events (upstream_event_id)")
    op.execute("create index public_events_event_time_idx on public_events (event_time desc)")
    op.execute("create index public_events_generated_idx on public_events (generated_at desc)")
    op.execute("create index public_events_severity_idx on public_events (severity)")
    op.execute("create index public_events_confirmation_state_idx on public_events (confirmation_state)")
    op.execute("create index public_events_content_category_idx on public_events (content_category)")
    op.execute("create index public_events_topic_tags_gin_idx on public_events using gin (topic_tags)")
    op.execute("create index public_events_mentioned_actors_gin_idx on public_events using gin (mentioned_actors)")
    op.execute(
        """
        create trigger trg_public_events_updated_at
        before update on public_events
        for each row execute function set_updated_at()
        """
    )

    op.execute(
        """
        create table public_ingest_requests (
          id uuid primary key default gen_random_uuid(),
          idempotency_key text,
          upstream_event_id uuid,
          public_event_id uuid references public_events(id) on delete set null,
          request_hash text,
          key_id text,
          nonce text,
          status text not null,
          error_message text,
          received_at timestamptz not null default now(),
          constraint public_ingest_requests_status_check check (
            status in ('accepted', 'duplicate', 'rejected', 'error')
          )
        )
        """
    )
    op.execute("create index public_ingest_requests_received_idx on public_ingest_requests (received_at desc)")
    op.execute("create index public_ingest_requests_idempotency_idx on public_ingest_requests (idempotency_key)")
    op.execute("create unique index public_ingest_requests_nonce_uidx on public_ingest_requests (key_id, nonce) where nonce is not null")


def downgrade() -> None:
    op.execute("drop index if exists public_ingest_requests_nonce_uidx")
    op.execute("drop index if exists public_ingest_requests_idempotency_idx")
    op.execute("drop index if exists public_ingest_requests_received_idx")
    op.execute("drop table if exists public_ingest_requests")
    op.execute("drop trigger if exists trg_public_events_updated_at on public_events")
    op.execute("drop index if exists public_events_mentioned_actors_gin_idx")
    op.execute("drop index if exists public_events_topic_tags_gin_idx")
    op.execute("drop index if exists public_events_content_category_idx")
    op.execute("drop index if exists public_events_confirmation_state_idx")
    op.execute("drop index if exists public_events_severity_idx")
    op.execute("drop index if exists public_events_generated_idx")
    op.execute("drop index if exists public_events_event_time_idx")
    op.execute("drop index if exists public_events_upstream_event_id_idx")
    op.execute("drop index if exists public_events_idempotency_key_uidx")
    op.execute("drop table if exists public_events")
    op.execute("drop function if exists set_updated_at()")
