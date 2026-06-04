"""add raw item taxonomy fields

Revision ID: 0008_raw_item_taxonomy
Revises: 0007_source_archive
Create Date: 2026-06-01 00:20:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0008_raw_item_taxonomy"
down_revision = "0007_source_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table raw_items add column if not exists content_category text")
    op.execute("alter table raw_items add column if not exists topic_tags jsonb not null default '[]'::jsonb")
    op.execute("alter table raw_items add column if not exists mentioned_actors jsonb not null default '[]'::jsonb")
    op.execute("create index if not exists raw_items_content_category_idx on raw_items (content_category)")
    op.execute("create index if not exists raw_items_topic_tags_gin_idx on raw_items using gin (topic_tags)")
    op.execute("create index if not exists raw_items_mentioned_actors_gin_idx on raw_items using gin (mentioned_actors)")
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint where conname = 'raw_items_topic_tags_array_check'
          ) then
            alter table raw_items add constraint raw_items_topic_tags_array_check
            check (jsonb_typeof(topic_tags) = 'array');
          end if;

          if not exists (
            select 1 from pg_constraint where conname = 'raw_items_mentioned_actors_array_check'
          ) then
            alter table raw_items add constraint raw_items_mentioned_actors_array_check
            check (jsonb_typeof(mentioned_actors) = 'array');
          end if;
        end $$;
        """
    )


def downgrade() -> None:
    op.execute("alter table raw_items drop constraint if exists raw_items_mentioned_actors_array_check")
    op.execute("alter table raw_items drop constraint if exists raw_items_topic_tags_array_check")
    op.execute("drop index if exists raw_items_mentioned_actors_gin_idx")
    op.execute("drop index if exists raw_items_topic_tags_gin_idx")
    op.execute("drop index if exists raw_items_content_category_idx")
    op.execute("alter table raw_items drop column if exists mentioned_actors")
    op.execute("alter table raw_items drop column if exists topic_tags")
    op.execute("alter table raw_items drop column if exists content_category")
