"""add deterministic domain routing

Revision ID: 0025_domain_routing
Revises: 0024_subscription_taxonomy
Create Date: 2026-09-10 23:00:00.000000
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0025_domain_routing"
down_revision = "0024_subscription_taxonomy"
branch_labels = None
depends_on = None

DOMAINS = [
    ("geopolitics", "Geopolitics", "地緣政治", 30, 10, "Assess conflict, sanctions, diplomacy, escalation and safe-haven relevance."),
    ("monetary", "Monetary Policy", "貨幣政策", 30, 20, "Assess central-bank stance, rates, liquidity, real yields and currency transmission."),
    ("energy", "Energy", "能源", 30, 30, "Assess oil and gas supply, OPEC decisions, transport chokepoints and disruption."),
    ("macro_data", "Macro Data", "總體數據", 30, 40, "Assess inflation, employment and growth data relative to stated expectations."),
]

KEYWORDS = {
    "geopolitics": [
        ("iran", ["iran", "iranian", "tehran", "伊朗", "ایران"], 30, "substring"),
        ("israel", ["israel", "idf", "以色列"], 30, "word"),
        ("military", ["irgc", "centcom", "missile", "drone", "strike", "red sea", "سپاه", "موشک"], 30, "substring"),
        ("sanctions", ["sanction", "ofac", "制裁"], 30, "substring"),
        ("diplomacy", ["diplomacy", "ceasefire", "negotiation", "talks", "外交", "停火"], 10, "substring"),
    ],
    "monetary": [
        ("fed", ["fed", "fomc", "federal reserve", "powell", "聯準會"], 30, "word"),
        ("central_banks", ["ecb", "boj", "boe", "pboc", "central bank", "央行"], 30, "word"),
        ("rates", ["rate cut", "rate hike", "interest rate", "higher for longer", "利率"], 30, "substring"),
        ("inflation", ["inflation", "通膨"], 10, "substring"),
    ],
    "energy": [
        ("oil", ["oil", "crude", "brent", "wti", "石油", "原油"], 30, "word"),
        ("opec", ["opec", "opec+", "石油輸出國"], 30, "word"),
        ("chokepoints", ["strait of hormuz", "hormuz", "荷莫茲"], 30, "substring"),
        ("supply", ["supply disruption", "output cut", "production cut", "供應中斷", "減產"], 10, "substring"),
    ],
    "macro_data": [
        ("inflation_data", ["cpi", "pce", "consumer price index", "消費者物價"], 30, "word"),
        ("employment", ["nonfarm payroll", "payrolls", "unemployment", "jobless claims", "就業", "失業"], 30, "substring"),
        ("growth", ["gdp", "gross domestic product", "國內生產毛額"], 30, "word"),
        ("weak_macro", ["economic data", "macro data", "經濟數據"], 10, "substring"),
    ],
}


def upgrade() -> None:
    op.execute(
        """
        create table domains (
          id uuid primary key default gen_random_uuid(),
          key text not null unique,
          label_en text not null,
          label_zh text not null,
          score_threshold smallint not null default 30,
          enabled boolean not null default true,
          sort_order integer not null default 1000,
          is_system boolean not null default true,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          constraint domains_key_check check (key ~ '^[a-z][a-z0-9_]*$'),
          constraint domains_threshold_check check (score_threshold between 1 and 100)
        )
        """
    )
    op.execute(
        """
        create table domain_keywords (
          id uuid primary key default gen_random_uuid(),
          domain_id uuid not null references domains(id) on delete cascade,
          group_key text not null,
          term text not null,
          weight smallint not null,
          language text,
          match_type text not null default 'substring',
          enabled boolean not null default true,
          created_at timestamptz not null default now(),
          constraint domain_keywords_weight_check check (weight between 1 and 100),
          constraint domain_keywords_match_check check (match_type in ('word', 'substring')),
          unique (domain_id, group_key, term)
        )
        """
    )
    op.execute(
        """
        create table source_domains (
          source_id uuid not null references sources(id) on delete cascade,
          domain_id uuid not null references domains(id) on delete cascade,
          prior_weight smallint not null default 10,
          created_at timestamptz not null default now(),
          primary key (source_id, domain_id),
          constraint source_domains_prior_check check (prior_weight between 0 and 30)
        )
        """
    )
    op.execute(
        """
        create table prompt_modules (
          id uuid primary key default gen_random_uuid(),
          domain_id uuid references domains(id) on delete cascade,
          role text not null,
          version integer not null default 1,
          body text not null,
          is_active boolean not null default true,
          created_at timestamptz not null default now(),
          constraint prompt_modules_role_check check (role in ('domain')),
          unique (domain_id, role, version)
        )
        """
    )
    op.execute(
        """
        create table routing_config_snapshots (
          config_version text primary key,
          snapshot_json jsonb not null,
          created_at timestamptz not null default now()
        )
        """
    )
    for table in ("raw_items", "events"):
        op.execute(f"alter table {table} add column matched_domains text[] not null default '{{}}'::text[]")
        op.execute(f"alter table {table} add column primary_domain text")
        op.execute(f"alter table {table} add column routing_config_version text")

    bind = op.get_bind()
    for key, label_en, label_zh, threshold, sort_order, prompt in DOMAINS:
        bind.execute(
            sa.text(
                """
                insert into domains (key, label_en, label_zh, score_threshold, sort_order, enabled, is_system)
                values (:key, :label_en, :label_zh, :threshold, :sort_order, true, true)
                """
            ),
            {"key": key, "label_en": label_en, "label_zh": label_zh, "threshold": threshold, "sort_order": sort_order},
        )
        bind.execute(
            sa.text(
                """
                insert into prompt_modules (domain_id, role, version, body, is_active)
                select id, 'domain', 1, :body, true from domains where key = :key
                """
            ),
            {"key": key, "body": prompt},
        )
        for group_key, terms, weight, match_type in KEYWORDS[key]:
            for term in terms:
                bind.execute(
                    sa.text(
                        """
                        insert into domain_keywords (domain_id, group_key, term, weight, match_type)
                        select id, :group_key, :term, :weight, :match_type from domains where key = :key
                        """
                    ),
                    {"key": key, "group_key": group_key, "term": term, "weight": weight, "match_type": match_type},
                )

    op.execute("create index domain_keywords_domain_enabled_idx on domain_keywords (domain_id, enabled)")
    op.execute("create index raw_items_matched_domains_gin_idx on raw_items using gin (matched_domains)")
    op.execute("create index events_matched_domains_gin_idx on events using gin (matched_domains)")


def downgrade() -> None:
    op.execute("drop index if exists events_matched_domains_gin_idx")
    op.execute("drop index if exists raw_items_matched_domains_gin_idx")
    for table in ("events", "raw_items"):
        op.execute(f"alter table {table} drop column if exists routing_config_version")
        op.execute(f"alter table {table} drop column if exists primary_domain")
        op.execute(f"alter table {table} drop column if exists matched_domains")
    op.execute("drop table if exists prompt_modules")
    op.execute("drop table if exists routing_config_snapshots")
    op.execute("drop table if exists source_domains")
    op.execute("drop table if exists domain_keywords")
    op.execute("drop table if exists domains")
