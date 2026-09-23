"""add public subscription catalog

Revision ID: 0008_subscription_catalog
Revises: 0007_public_event_event_type
Create Date: 2026-09-11 01:15:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0008_subscription_catalog"
down_revision = "0007_public_event_event_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table public_subscription_catalog_revisions (
          revision text primary key,
          schema_version text not null,
          payload_hash text not null,
          generated_at timestamptz not null,
          received_at timestamptz not null default now(),
          category_count integer not null,
          tag_count integer not null,
          constraint public_subscription_catalog_schema_check
            check (schema_version = 'subscription_catalog.v1'),
          constraint public_subscription_catalog_counts_check
            check (category_count > 0 and tag_count > 0)
        )
        """
    )
    op.execute(
        """
        create table public_subscription_categories (
          key text primary key,
          label_en text not null,
          label_zh text not null,
          description text,
          sort_order integer not null,
          revision text not null references public_subscription_catalog_revisions(revision),
          updated_at timestamptz not null default now()
        )
        """
    )
    op.execute(
        """
        create table public_subscription_tags (
          key text primary key,
          label_en text not null,
          label_zh text not null,
          tag_type text not null,
          aliases jsonb not null default '[]'::jsonb,
          revision text not null references public_subscription_catalog_revisions(revision),
          updated_at timestamptz not null default now(),
          constraint public_subscription_tags_aliases_check check (jsonb_typeof(aliases) = 'array')
        )
        """
    )
    op.execute("create index public_subscription_categories_order_idx on public_subscription_categories (sort_order, key)")
    op.execute("create index public_subscription_tags_type_idx on public_subscription_tags (tag_type, key)")
    op.execute("alter table public_ingest_requests drop constraint if exists public_ingest_requests_ingest_kind_check")
    op.execute(
        """
        alter table public_ingest_requests
        add constraint public_ingest_requests_ingest_kind_check
        check (ingest_kind in ('event', 'raw_item', 'subscription_catalog'))
        """
    )


def downgrade() -> None:
    op.execute("alter table public_ingest_requests drop constraint if exists public_ingest_requests_ingest_kind_check")
    op.execute(
        """
        alter table public_ingest_requests
        add constraint public_ingest_requests_ingest_kind_check
        check (ingest_kind in ('event', 'raw_item'))
        """
    )
    op.execute("drop index if exists public_subscription_tags_type_idx")
    op.execute("drop index if exists public_subscription_categories_order_idx")
    op.execute("drop table if exists public_subscription_tags")
    op.execute("drop table if exists public_subscription_categories")
    op.execute("drop table if exists public_subscription_catalog_revisions")
