"""add public raw items feed tables

Revision ID: 0003_public_raw_items
Revises: 0002_public_event_translations
Create Date: 2026-06-13 13:35:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0003_public_raw_items"
down_revision = "0002_public_event_translations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create extension if not exists pg_trgm")
    op.execute(
        """
        create table public_raw_items (
          id uuid primary key default gen_random_uuid(),
          upstream_raw_item_id uuid not null,
          idempotency_key text not null,
          schema_version text not null,
          source_name text,
          source_type text,
          source_group text,
          official_level text,
          priority text,
          source_url text,
          published_at timestamptz,
          ingested_at timestamptz,
          edited_at timestamptz,
          received_at timestamptz not null default now(),
          title text,
          original_content text,
          language text,
          media_type text,
          summary_zh text,
          summary_en text,
          full_translation_zh text,
          full_translation_en text,
          content_category text,
          topic_tags text[] not null default '{}'::text[],
          mentioned_actors text[] not null default '{}'::text[],
          upstream_event_ids uuid[] not null default '{}'::uuid[],
          is_relevant boolean,
          relevance_score smallint,
          filter_reason text,
          classification_stage text,
          classification_status text,
          is_visible boolean not null default true,
          is_truncated boolean not null default false,
          source_text_chars integer,
          translation_chars integer,
          scrub_metadata jsonb not null default '{}'::jsonb,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint public_raw_items_schema_version_check check (schema_version in ('public_raw_item.v1')),
          constraint public_raw_items_relevance_score_check check (
            relevance_score is null or (relevance_score >= 0 and relevance_score <= 100)
          ),
          constraint public_raw_items_source_url_check check (
            source_url is null or source_url ~* '^https?://'
          ),
          constraint public_raw_items_source_text_chars_check check (
            source_text_chars is null or source_text_chars >= 0
          ),
          constraint public_raw_items_translation_chars_check check (
            translation_chars is null or translation_chars >= 0
          ),
          constraint public_raw_items_scrub_metadata_object_check check (jsonb_typeof(scrub_metadata) = 'object')
        )
        """
    )
    op.execute("create unique index public_raw_items_idempotency_key_uidx on public_raw_items (idempotency_key)")
    op.execute("create unique index public_raw_items_upstream_raw_item_uidx on public_raw_items (upstream_raw_item_id)")
    op.execute(
        """
        create index public_raw_items_published_idx
          on public_raw_items (coalesce(published_at, ingested_at, received_at) desc)
        """
    )
    op.execute("create index public_raw_items_source_type_idx on public_raw_items (source_type)")
    op.execute("create index public_raw_items_source_group_idx on public_raw_items (source_group)")
    op.execute("create index public_raw_items_content_category_idx on public_raw_items (content_category)")
    op.execute("create index public_raw_items_relevance_idx on public_raw_items (is_relevant, relevance_score desc)")
    op.execute("create index public_raw_items_topic_tags_gin_idx on public_raw_items using gin (topic_tags)")
    op.execute("create index public_raw_items_mentioned_actors_gin_idx on public_raw_items using gin (mentioned_actors)")
    op.execute("create index public_raw_items_upstream_event_ids_gin_idx on public_raw_items using gin (upstream_event_ids)")
    op.execute("create index public_raw_items_title_trgm_idx on public_raw_items using gin (title gin_trgm_ops)")
    op.execute("create index public_raw_items_original_content_trgm_idx on public_raw_items using gin (original_content gin_trgm_ops)")
    op.execute(
        """
        create trigger trg_public_raw_items_updated_at
        before update on public_raw_items
        for each row execute function set_updated_at()
        """
    )

    op.execute(
        """
        create table public_raw_item_translations (
          id uuid primary key default gen_random_uuid(),
          public_raw_item_id uuid not null references public_raw_items(id) on delete cascade,
          language text not null,
          summary text,
          full_translation text,
          status text,
          is_truncated boolean not null default false,
          source_chars integer,
          translation_chars integer,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),

          constraint public_raw_item_translations_language_check check (btrim(language) <> ''),
          constraint public_raw_item_translations_content_check check (
            summary is not null or full_translation is not null
          ),
          constraint public_raw_item_translations_status_check check (
            status is null or status in ('pending', 'completed', 'completed_truncated', 'skipped', 'failed')
          ),
          constraint public_raw_item_translations_source_chars_check check (
            source_chars is null or source_chars >= 0
          ),
          constraint public_raw_item_translations_translation_chars_check check (
            translation_chars is null or translation_chars >= 0
          ),
          constraint public_raw_item_translations_item_language_key unique (public_raw_item_id, language)
        )
        """
    )
    op.execute("create index public_raw_item_translations_language_idx on public_raw_item_translations (language)")
    op.execute("create index public_raw_item_translations_updated_at_idx on public_raw_item_translations (updated_at desc)")
    op.execute(
        """
        create index public_raw_item_translations_summary_trgm_idx
          on public_raw_item_translations using gin (summary gin_trgm_ops)
        """
    )
    op.execute(
        """
        create index public_raw_item_translations_full_translation_trgm_idx
          on public_raw_item_translations using gin (full_translation gin_trgm_ops)
        """
    )
    op.execute(
        """
        create trigger trg_public_raw_item_translations_updated_at
        before update on public_raw_item_translations
        for each row execute function set_updated_at()
        """
    )

    op.execute("alter table public_ingest_requests add column if not exists ingest_kind text not null default 'event'")
    op.execute("alter table public_ingest_requests add column if not exists public_raw_item_id uuid references public_raw_items(id) on delete set null")
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint where conname = 'public_ingest_requests_ingest_kind_check'
          ) then
            alter table public_ingest_requests add constraint public_ingest_requests_ingest_kind_check
            check (ingest_kind in ('event', 'raw_item'));
          end if;
        end $$;
        """
    )
    op.execute("create index if not exists public_ingest_requests_ingest_kind_idx on public_ingest_requests (ingest_kind)")
    op.execute("create index if not exists public_ingest_requests_public_raw_item_idx on public_ingest_requests (public_raw_item_id)")


def downgrade() -> None:
    op.execute("drop index if exists public_ingest_requests_public_raw_item_idx")
    op.execute("drop index if exists public_ingest_requests_ingest_kind_idx")
    op.execute("alter table public_ingest_requests drop constraint if exists public_ingest_requests_ingest_kind_check")
    op.execute("alter table public_ingest_requests drop column if exists public_raw_item_id")
    op.execute("alter table public_ingest_requests drop column if exists ingest_kind")
    op.execute("drop trigger if exists trg_public_raw_item_translations_updated_at on public_raw_item_translations")
    op.execute("drop index if exists public_raw_item_translations_full_translation_trgm_idx")
    op.execute("drop index if exists public_raw_item_translations_summary_trgm_idx")
    op.execute("drop index if exists public_raw_item_translations_updated_at_idx")
    op.execute("drop index if exists public_raw_item_translations_language_idx")
    op.execute("drop table if exists public_raw_item_translations")
    op.execute("drop trigger if exists trg_public_raw_items_updated_at on public_raw_items")
    op.execute("drop index if exists public_raw_items_original_content_trgm_idx")
    op.execute("drop index if exists public_raw_items_title_trgm_idx")
    op.execute("drop index if exists public_raw_items_upstream_event_ids_gin_idx")
    op.execute("drop index if exists public_raw_items_mentioned_actors_gin_idx")
    op.execute("drop index if exists public_raw_items_topic_tags_gin_idx")
    op.execute("drop index if exists public_raw_items_relevance_idx")
    op.execute("drop index if exists public_raw_items_content_category_idx")
    op.execute("drop index if exists public_raw_items_source_group_idx")
    op.execute("drop index if exists public_raw_items_source_type_idx")
    op.execute("drop index if exists public_raw_items_published_idx")
    op.execute("drop index if exists public_raw_items_upstream_raw_item_uidx")
    op.execute("drop index if exists public_raw_items_idempotency_key_uidx")
    op.execute("drop table if exists public_raw_items")
