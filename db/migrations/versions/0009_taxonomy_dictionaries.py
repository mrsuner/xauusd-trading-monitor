"""add taxonomy dictionaries

Revision ID: 0009_taxonomy_dictionaries
Revises: 0008_raw_item_taxonomy
Create Date: 2026-06-01 09:20:00.000000
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0009_taxonomy_dictionaries"
down_revision = "0008_raw_item_taxonomy"
branch_labels = None
depends_on = None


CATEGORIES = [
    ("diplomacy", "外交", "Diplomacy", "Negotiations, statements, talks and diplomatic positioning.", 10),
    ("military", "軍事", "Military", "Military action, defense updates, strikes, drones and missiles.", 20),
    ("sanctions", "制裁", "Sanctions", "Sanctions, OFAC, Treasury and financial restrictions.", 30),
    ("fed", "Fed", "Fed", "Federal Reserve policy, speeches, rates and inflation expectations.", 40),
    ("energy", "能源", "Energy", "Oil, gas, Strait of Hormuz and energy supply risk.", 50),
    ("market", "市場", "Market", "Market squawk, macro pricing and asset movement context.", 60),
    ("domestic_politics", "國內政治", "Domestic Politics", "Internal political news and domestic policy context.", 70),
    ("economy", "經濟", "Economy", "Economic data, fiscal policy and macroeconomic background.", 80),
    ("technology", "科技", "Technology", "Technology, cyber and infrastructure items.", 90),
    ("routine", "日常", "Routine", "Routine schedules, ceremonies, interviews and low-policy background items.", 900),
    ("social", "社會", "Social", "Social, cultural, lifestyle or human-interest items.", 910),
    ("other", "其他", "Other", "Fallback category when no controlled category fits.", 999),
]


TAGS = [
    ("iran", "Iran", "topic", ["islamic-republic-of-iran", "tehran"]),
    ("trump", "Trump", "actor", ["donald-trump", "donald-j-trump"]),
    ("united-states", "United States", "actor", ["usa", "us", "u-s", "u-s-a", "america"]),
    ("nuclear", "Nuclear", "topic", ["enrichment", "uranium-enrichment"]),
    ("sanctions", "Sanctions", "topic", ["ofac-sanctions"]),
    ("hormuz", "Strait of Hormuz", "topic", ["strait-of-hormuz"]),
    ("fed", "Federal Reserve", "actor", ["federal-reserve", "fomc"]),
    ("oil", "Oil", "topic", ["crude", "wti", "brent"]),
    ("israel", "Israel", "actor", []),
    ("irgc", "IRGC", "actor", ["islamic-revolutionary-guard-corps", "revolutionary-guards"]),
    ("centcom", "CENTCOM", "actor", ["us-centcom", "u-s-centcom"]),
    ("idf", "IDF", "actor", ["israel-defense-forces"]),
    ("treasury", "U.S. Treasury", "actor", ["us-treasury", "u-s-treasury"]),
    ("ofac", "OFAC", "actor", []),
    ("dxy", "DXY", "topic", ["dollar-index", "us-dollar-index"]),
]


def upgrade() -> None:
    op.execute(
        """
        create table if not exists content_categories (
          id uuid primary key default gen_random_uuid(),
          key text not null unique,
          label_zh text not null,
          label_en text not null,
          description text,
          sort_order integer not null default 1000,
          enabled boolean not null default true,
          is_system boolean not null default false,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          constraint content_categories_key_check check (key ~ '^[a-z0-9][a-z0-9_\\-]*$')
        )
        """
    )
    op.execute(
        """
        create table if not exists tags (
          id uuid primary key default gen_random_uuid(),
          key text not null unique,
          label text not null,
          tag_type text not null default 'topic',
          aliases jsonb not null default '[]'::jsonb,
          usage_count integer not null default 0,
          enabled boolean not null default true,
          is_system boolean not null default false,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          constraint tags_key_check check (key ~ '^[a-z0-9][a-z0-9\\-]*$'),
          constraint tags_aliases_array_check check (jsonb_typeof(aliases) = 'array')
        )
        """
    )
    op.execute(
        """
        create table if not exists raw_item_tags (
          raw_item_id uuid not null references raw_items(id) on delete cascade,
          tag_id uuid not null references tags(id) on delete cascade,
          source text not null default 'ai_layer_1',
          confidence smallint,
          created_at timestamptz not null default now(),
          primary key (raw_item_id, tag_id),
          constraint raw_item_tags_confidence_check check (confidence is null or confidence between 0 and 100)
        )
        """
    )
    op.execute("create index if not exists content_categories_enabled_sort_idx on content_categories (enabled, sort_order, key)")
    op.execute("create index if not exists tags_enabled_type_key_idx on tags (enabled, tag_type, key)")
    op.execute("create index if not exists tags_aliases_gin_idx on tags using gin (aliases)")
    op.execute("create index if not exists raw_item_tags_tag_id_idx on raw_item_tags (tag_id)")

    bind = op.get_bind()
    for key, label_zh, label_en, description, sort_order in CATEGORIES:
        bind.execute(
            sa.text(
                """
            insert into content_categories (key, label_zh, label_en, description, sort_order, enabled, is_system)
            values (:key, :label_zh, :label_en, :description, :sort_order, true, true)
            on conflict (key) do update
            set label_zh = excluded.label_zh,
                label_en = excluded.label_en,
                description = excluded.description,
                sort_order = excluded.sort_order,
                enabled = true,
                is_system = true,
                updated_at = now()
            """
            ),
            {
                "key": key,
                "label_zh": label_zh,
                "label_en": label_en,
                "description": description,
                "sort_order": sort_order,
            },
        )

    for key, label, tag_type, aliases in TAGS:
        bind.execute(
            sa.text(
                """
            insert into tags (key, label, tag_type, aliases, enabled, is_system)
            values (:key, :label, :tag_type, cast(:aliases as jsonb), true, true)
            on conflict (key) do update
            set label = excluded.label,
                tag_type = excluded.tag_type,
                aliases = excluded.aliases,
                enabled = true,
                is_system = true,
                updated_at = now()
            """
            ),
            {"key": key, "label": label, "tag_type": tag_type, "aliases": json.dumps(aliases)},
        )


def downgrade() -> None:
    op.execute("drop index if exists raw_item_tags_tag_id_idx")
    op.execute("drop index if exists tags_aliases_gin_idx")
    op.execute("drop index if exists tags_enabled_type_key_idx")
    op.execute("drop index if exists content_categories_enabled_sort_idx")
    op.execute("drop table if exists raw_item_tags")
    op.execute("drop table if exists tags")
    op.execute("drop table if exists content_categories")
