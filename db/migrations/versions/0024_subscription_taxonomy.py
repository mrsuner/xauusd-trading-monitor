"""add subscription taxonomy catalog

Revision ID: 0024_subscription_taxonomy
Revises: 0023_relax_event_summary_legacy
Create Date: 2026-09-10 22:00:00.000000
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0024_subscription_taxonomy"
down_revision = "0023_relax_event_summary_legacy"
branch_labels = None
depends_on = None

NEW_TAGS = [
    ("ecb", "European Central Bank", "歐洲央行", "actor", ["european-central-bank"]),
    ("boj", "Bank of Japan", "日本銀行", "actor", ["bank-of-japan"]),
    ("boe", "Bank of England", "英格蘭銀行", "actor", ["bank-of-england"]),
    ("pboc", "People's Bank of China", "中國人民銀行", "actor", ["peoples-bank-of-china"]),
    ("opec", "OPEC", "石油輸出國組織", "actor", ["organization-of-the-petroleum-exporting-countries"]),
    ("inflation", "Inflation", "通膨", "topic", []),
    ("cpi", "CPI", "消費者物價指數", "topic", ["consumer-price-index"]),
    ("pce", "PCE", "個人消費支出物價", "topic", ["personal-consumption-expenditures"]),
    ("employment", "Employment", "就業", "topic", ["jobs", "labor-market"]),
    ("gdp", "GDP", "國內生產毛額", "topic", ["gross-domestic-product"]),
    ("interest-rates", "Interest Rates", "利率", "topic", ["policy-rates"]),
    ("treasury-yields", "Treasury Yields", "美債殖利率", "topic", ["government-bond-yields"]),
]

EXISTING_TAG_ZH = {
    "iran": "伊朗",
    "trump": "川普",
    "united-states": "美國",
    "nuclear": "核議題",
    "sanctions": "制裁",
    "hormuz": "荷莫茲海峽",
    "fed": "聯準會",
    "oil": "石油",
    "israel": "以色列",
    "irgc": "伊朗革命衛隊",
    "centcom": "美國中央司令部",
    "idf": "以色列國防軍",
    "treasury": "美國財政部",
    "ofac": "美國海外資產控制辦公室",
    "dxy": "美元指數",
}


def upgrade() -> None:
    op.execute("alter table content_categories add column if not exists subscribable boolean not null default false")
    op.execute("alter table tags add column if not exists subscribable boolean not null default false")
    op.execute("alter table tags add column if not exists label_en text")
    op.execute("alter table tags add column if not exists label_zh text")
    op.execute("update tags set label_en = coalesce(label_en, label) where label_en is null")

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            insert into content_categories (
              key, label_zh, label_en, description, sort_order, enabled, is_system, subscribable
            ) values (
              'central_bank', '其他央行政策', 'Other Central Banks',
              'ECB, BOJ, BOE, PBOC and other non-Fed central-bank policy.',
              45, true, true, true
            )
            on conflict (key) do update set
              label_zh = excluded.label_zh,
              label_en = excluded.label_en,
              description = excluded.description,
              sort_order = excluded.sort_order,
              enabled = true,
              is_system = true,
              subscribable = true,
              updated_at = now()
            """
        )
    )
    bind.execute(
        sa.text(
            """
            update content_categories
            set subscribable = key in (
              'fed', 'central_bank', 'economy', 'energy',
              'diplomacy', 'military', 'sanctions', 'market'
            ), updated_at = now()
            where is_system = true
            """
        )
    )
    bind.execute(
        sa.text("update tags set subscribable = true, label_en = coalesce(label_en, label) where is_system = true")
    )
    for key, label_zh in EXISTING_TAG_ZH.items():
        bind.execute(
            sa.text("update tags set label_zh = :label_zh, updated_at = now() where key = :key and is_system = true"),
            {"key": key, "label_zh": label_zh},
        )

    for key, label_en, label_zh, tag_type, aliases in NEW_TAGS:
        bind.execute(
            sa.text(
                """
                insert into tags (
                  key, label, label_en, label_zh, tag_type, aliases,
                  enabled, is_system, subscribable
                ) values (
                  :key, :label_en, :label_en, :label_zh, :tag_type,
                  cast(:aliases as jsonb), true, true, true
                )
                on conflict (key) do update set
                  label = excluded.label,
                  label_en = excluded.label_en,
                  label_zh = excluded.label_zh,
                  tag_type = excluded.tag_type,
                  aliases = excluded.aliases,
                  enabled = true,
                  is_system = true,
                  subscribable = true,
                  updated_at = now()
                """
            ),
            {
                "key": key,
                "label_en": label_en,
                "label_zh": label_zh,
                "tag_type": tag_type,
                "aliases": json.dumps(aliases),
            },
        )

    op.execute(
        "create index if not exists content_categories_subscription_idx "
        "on content_categories (subscribable, enabled, sort_order, key)"
    )
    op.execute(
        "create index if not exists tags_subscription_idx "
        "on tags (subscribable, enabled, tag_type, key)"
    )


def downgrade() -> None:
    op.execute("drop index if exists tags_subscription_idx")
    op.execute("drop index if exists content_categories_subscription_idx")
    op.execute("delete from tags where key = any(array['ecb','boj','boe','pboc','opec','inflation','cpi','pce','employment','gdp','interest-rates','treasury-yields']) and usage_count = 0")
    op.execute("delete from content_categories where key = 'central_bank'")
    op.execute("alter table tags drop column if exists label_zh")
    op.execute("alter table tags drop column if exists label_en")
    op.execute("alter table tags drop column if exists subscribable")
    op.execute("alter table content_categories drop column if exists subscribable")
