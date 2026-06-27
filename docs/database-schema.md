# Database Schema 設計

## 1. 文件目的

本文定義 XAUUSD Event Radar V1 的 PostgreSQL schema。V1 只實作新聞消息層，重點是：

- source registry
- 原始消息入庫
- processing queue / processing state
- normalizer-classifier 結果回寫
- 事件建立
- 簡化 claim 保存
- alert delivery tracking
- source health

V1 不實作 `mt5-collector`、`market_snapshots`、行情異動反查與 market move review。相關 schema 只列在後續版本規劃中，不進入 V1 migration。

## 2. 設計原則

### 2.1 PostgreSQL 是 source of truth

V1 可以使用 `LISTEN/NOTIFY` 或 Redis 作為即時喚醒訊號，但可靠狀態必須保存於 PostgreSQL。

建議：

```text
raw_items insert
  ↓
create raw_item_processing row
  ↓
optional NOTIFY raw_item_created
```

`NOTIFY` 只傳 ID，不傳完整 payload。

### 2.2 Collector 不做判斷

`telegram-collector` 與 `rss-collector` 只寫入：

- `raw_items`
- `source_health`
- 必要時建立 `raw_item_processing` pending row

事件分類、相關度、摘要、claim direction 都由 `normalizer-classifier` 回寫。

### 2.3 V1 以簡單 enum + check constraint 為主

V1 不必過度正規化。來源群組、事件類型、severity 等可以先用 `text` + check constraint，避免早期遷移成本太高。

### 2.4 JSONB 只保存不穩定結構

固定查詢欄位應使用 typed columns。來源原始 payload、模型原始輸出、provider response 等不穩定資料使用 `jsonb`。

### 2.5 所有 worker table 必須可恢復

`raw_item_processing` 與 `alerts` 必須有：

- `status`
- `attempt_count`
- `next_retry_at`
- `locked_by`
- `locked_at`
- `error_message`

這樣服務重啟後可以掃描 pending / retry / stale running rows 恢復。

## 3. Extension

V1 建議啟用：

```sql
create extension if not exists pgcrypto;
create extension if not exists pg_trgm;
```

用途：

- `pgcrypto`：使用 `gen_random_uuid()`。
- `pg_trgm`：支援文字近似搜尋與後續 near-duplicate detection。

## 4. 命名與型別慣例

### 4.1 Primary Key

V1 建議使用 UUID：

```sql
id uuid primary key default gen_random_uuid()
```

原因：

- 多服務寫入時不依賴 sequence 語意。
- 後續若拆服務或同步資料較容易。

### 4.2 時間欄位

所有時間欄位使用：

```sql
timestamptz
```

所有表至少包含：

```text
created_at
updated_at
```

### 4.3 Score 欄位

所有 score 使用 `smallint`，並加 check：

```sql
check (score >= 0 and score <= 100)
```

### 4.4 狀態欄位

狀態欄位使用 `text` + check constraint。V1 不使用 PostgreSQL enum，避免修改 enum 值需要額外 migration。

## 5. V1 Tables

V1 必要資料表：

| Table | 用途 |
| --- | --- |
| `sources` | 資料源註冊與來源立場矩陣 |
| `raw_items` | Telegram / RSS / HTML polling 原始消息 |
| `raw_item_processing` | reliable processing queue 與模型輸出 |
| `events` | 已判定有價值的標準事件 |
| `event_claims` | V1 簡化 claim 保存 |
| `alerts` | Telegram / Pushover delivery tracking |
| `ai_model_calls` | AI API call、token usage、model route 與成本估算 |
| `source_health` | source 與 collector health |
| `schema_migrations` | migration 版本紀錄，若不用 Alembic 可保留 |

## 6. sources

### 6.1 用途

`sources` 是所有 collector 的 source registry，也是事件權重與來源立場判斷的基礎。

Collector 不應寫死資料源清單，必須從 `sources` 讀取 enabled source。

### 6.2 欄位

```sql
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
  translation_policy text not null default 'full',
  translation_priority text not null default 'normal',
  translation_max_chars integer,
  always_full_translate boolean not null default false,
  telegram_alert_enabled boolean not null default true,
  pushover_alert_enabled boolean not null default false,
  telegram_min_severity text not null default 'B',
  pushover_min_severity text not null default 'S',
  alert_weight smallint not null default 50,
  alert_rate_limit_per_hour integer,
  alert_cooldown_minutes integer,
  enabled boolean not null default true,
  source_config jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint sources_source_type_check check (
    source_type in ('telegram', 'rss', 'atom', 'html_polling', 'api')
  ),
  constraint sources_official_level_check check (
    official_level in ('official', 'semi_official', 'unofficial', 'unofficial_mirror', 'aggregator')
  ),
  constraint sources_priority_check check (
    priority in ('P0', 'P1', 'P2', 'P3')
  ),
  constraint sources_reliability_score_check check (
    reliability_score >= 0 and reliability_score <= 100
  ),
  constraint sources_latency_score_check check (
    latency_score >= 0 and latency_score <= 100
  ),
  constraint sources_translation_policy_check check (
    translation_policy in ('disabled', 'summary_only', 'full')
  ),
  constraint sources_translation_priority_check check (
    translation_priority in ('normal', 'high')
  ),
  constraint sources_translation_max_chars_check check (
    translation_max_chars is null or translation_max_chars >= 0
  ),
  constraint sources_telegram_min_severity_check check (
    telegram_min_severity in ('S', 'A', 'B', 'C')
  ),
  constraint sources_pushover_min_severity_check check (
    pushover_min_severity in ('S', 'A', 'B', 'C')
  ),
  constraint sources_alert_weight_check check (
    alert_weight >= 0 and alert_weight <= 100
  ),
  constraint sources_alert_rate_limit_per_hour_check check (
    alert_rate_limit_per_hour is null or alert_rate_limit_per_hour >= 0
  ),
  constraint sources_alert_cooldown_minutes_check check (
    alert_cooldown_minutes is null or alert_cooldown_minutes >= 0
  )
);
```

Translation policy 用於 deterministic translation scope，不由低成本模型判斷重要性：

| 欄位 | 說明 |
| --- | --- |
| `translation_policy` | `disabled` / `summary_only` / `full`，V1 預設 `full` |
| `translation_priority` | `normal` / `high`，高優先來源可使用較大的文字長度限制 |
| `translation_max_chars` | source-level override；P0/P1 seed 預設可設為 `100000` |
| `always_full_translate` | 指定來源永遠使用 full translation policy |

Alert policy 用於 `alert-dispatcher` 的 deterministic 通知降噪：

| 欄位 | 說明 |
| --- | --- |
| `telegram_alert_enabled` | 此 source 是否允許 Telegram 通知 |
| `pushover_alert_enabled` | 此 source 是否允許 Pushover 通知；V1 預設 false，靠 allowlist 開啟 |
| `telegram_min_severity` | Telegram 最低通知等級 |
| `pushover_min_severity` | Pushover 最低通知等級 |
| `alert_weight` | source-level 通知權重，參與 `alert_score` |
| `alert_rate_limit_per_hour` | 單一 source 每小時最多建立 pending/sent/retry alert 的數量 |
| `alert_cooldown_minutes` | 同一 source 兩次通知的最小間隔 |

### 6.3 source_group V1 建議值

```text
us_trump
us_fed
us_military
us_diplomacy
us_sanctions
iran_government
iran_external_media
iran_irgc_adjacent
iran_irgc_official
iran_supreme_leader
iran_conservative
israel_military
israel_diplomacy
israel_media
market_squawk
osint_aggregator
international_media
```

V1 不建議對 `source_group` 加 check constraint，因為來源群組會頻繁調整。

### 6.4 source_config

Telegram source 示例：

```json
{
  "telegram_username": "Irna_en",
  "backfill_hours": 6
}
```

RSS source 示例：

```json
{
  "poll_interval_seconds": 120,
  "request_timeout_seconds": 15,
  "etag": "...",
  "last_modified": "...",
  "timezone_hint": "UTC"
}
```

HTML polling source 示例：

```json
{
  "poll_interval_seconds": 300,
  "list_selector": ".views-row",
  "title_selector": "a",
  "url_selector": "a",
  "published_selector": "time"
}
```

### 6.5 Indexes

```sql
create unique index sources_type_handle_uidx
  on sources (source_type, lower(handle_or_url));

create index sources_enabled_type_idx
  on sources (enabled, source_type);

create index sources_group_priority_idx
  on sources (source_group, priority);
```

## 7. raw_items

### 7.1 用途

`raw_items` 保存所有 collector 寫入的原始消息。它是後續處理的原始依據。

### 7.2 欄位

```sql
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
  content_category text,
  topic_tags jsonb not null default '[]'::jsonb,
  mentioned_actors jsonb not null default '[]'::jsonb,
  translation_status text not null default 'pending',
  translation_model_provider text,
  translation_model text,
  translation_error text,
  translation_input_chars integer,
  translation_updated_at timestamptz,
  language text,
  url text,
  media_type text not null default 'none',
  raw_json jsonb not null default '{}'::jsonb,
  content_hash text,
  dedupe_key text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint raw_items_media_type_check check (
    media_type in ('none', 'photo', 'video', 'document', 'webpage', 'mixed', 'unknown')
  ),
  constraint raw_items_translation_status_check check (
    translation_status in ('pending', 'completed', 'completed_truncated', 'skipped', 'failed')
  ),
  constraint raw_items_translation_input_chars_check check (
    translation_input_chars is null or translation_input_chars >= 0
  ),
  constraint raw_items_topic_tags_array_check check (
    jsonb_typeof(topic_tags) = 'array'
  ),
  constraint raw_items_mentioned_actors_array_check check (
    jsonb_typeof(mentioned_actors) = 'array'
  )
);
```

Raw item 摘要與全文翻譯保存在 `raw_item_translations`，以 `(raw_item_id, language)` 表示多語輸出。`raw_items` 不再保存固定語言欄位。Layer 2 classification-reasoning 不讀 raw item translation rows，避免低成本翻譯模型影響事件判斷。

`content_category`、`topic_tags` 與 `mentioned_actors` 由 Layer 1 在翻譯摘要時同步回寫，只用於 Timeline taxonomy、filter 與搜尋。這些欄位不代表交易相關性、通知等級或事件嚴重度。

`content_category` 是 controlled category key，應來自 `content_categories.key`；若模型輸出不在啟用字典內，normalizer 會回寫為 `other`。`topic_tags` 是 semi-controlled normalized tag keys，normalizer 會做 lowercase、slug normalization、alias mapping，並 upsert 到 `tags` 與 `raw_item_tags`。

`translation_status`：

| 狀態 | 說明 |
| --- | --- |
| `pending` | 尚未處理 |
| `completed` | 已完成，未截斷 |
| `completed_truncated` | 已完成，但只翻譯 policy 允許的截斷輸入 |
| `skipped` | deterministic prefilter 或 source policy 跳過 |
| `failed` | free 與 fallback route 都失敗，或 budget 用盡 |

### 7.3 Dedupe Key

Telegram：

```text
telegram:{channel_id}:{message_id}
```

RSS：

```text
rss:{feed_url_hash}:{guid_or_url_hash}
```

HTML polling：

```text
html:{source_id}:{url_hash_or_title_time_hash}
```

### 7.4 Constraints / Indexes

```sql
create unique index raw_items_dedupe_key_uidx
  on raw_items (dedupe_key);

create unique index raw_items_source_external_uidx
  on raw_items (source_id, external_id)
  where external_id is not null;

create index raw_items_source_published_idx
  on raw_items (source_id, published_at desc);

create index raw_items_ingested_idx
  on raw_items (ingested_at desc);

create index raw_items_content_hash_idx
  on raw_items (content_hash)
  where content_hash is not null;

create index raw_items_title_trgm_idx
  on raw_items using gin (title gin_trgm_ops)
  where title is not null;

create index raw_items_text_clean_trgm_idx
  on raw_items using gin (text_clean gin_trgm_ops)
  where text_clean is not null;

create index raw_items_content_category_idx
  on raw_items (content_category);

create index raw_items_topic_tags_gin_idx
  on raw_items using gin (topic_tags);

create index raw_items_mentioned_actors_gin_idx
  on raw_items using gin (mentioned_actors);
```

V1 先使用兩個簡單 trigram index 與 taxonomy GIN index。若後續需要更好的全文搜尋，可新增 `search_text` generated column 或 `tsvector` 欄位。

### 7.5 Upsert 行為

新 item：

- insert row。
- 建立 `raw_item_processing` pending row。
- 可選 `NOTIFY raw_item_created`。

重複 item：

- 若內容未變，不更新。
- 若 `edited_at` 或 `content_hash` 變更，更新 `title`、`text_raw`、`text_clean`、`edited_at`、`raw_json`、`content_hash`。
- V1 不建立 `raw_item_versions`，後續版本再做。

## 8. Taxonomy Dictionaries

### 8.1 content_categories

`content_categories` 是 controlled category dictionary。Layer 1 必須優先從啟用的 category keys 中選擇；若都不適合，使用 `other`。

```sql
create table content_categories (
  id uuid primary key default gen_random_uuid(),
  key text not null unique,
  label_zh text not null,
  label_en text not null,
  description text,
  sort_order integer not null default 1000,
  enabled boolean not null default true,
  is_system boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

V1 system categories：

```text
diplomacy
military
sanctions
fed
energy
market
domestic_politics
economy
technology
routine
social
other
```

### 8.2 tags

`tags` 是 semi-controlled tag dictionary。Layer 1 可以輸出新 tags，但 normalizer 會先做 normalization 與 alias mapping，然後自動 upsert。

```sql
create table tags (
  id uuid primary key default gen_random_uuid(),
  key text not null unique,
  label text not null,
  tag_type text not null default 'topic',
  aliases jsonb not null default '[]'::jsonb,
  usage_count integer not null default 0,
  enabled boolean not null default true,
  is_system boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

Normalization 規則：

- lowercase。
- trim。
- spaces、underscores、slash 轉為 `-`。
- 移除多餘 punctuation。
- alias mapping，例如 `usa` / `u.s.` / `america` -> `united-states`。
- 限制每筆 raw item 最多 12 個 tags。

### 8.3 raw_item_tags

`raw_item_tags` 保存 raw item 與 tag dictionary 的正規關聯。`raw_items.topic_tags` 仍保留為 Timeline 查詢快取。

```sql
create table raw_item_tags (
  raw_item_id uuid not null references raw_items(id) on delete cascade,
  tag_id uuid not null references tags(id) on delete cascade,
  source text not null default 'ai_layer_1',
  confidence smallint,
  created_at timestamptz not null default now(),
  primary key (raw_item_id, tag_id)
);
```

## 9. raw_item_processing

### 9.1 用途

`raw_item_processing` 是 V1 reliable processing queue，同時保存 normalizer-classifier 的處理結果。

它解決兩個問題：

- `LISTEN/NOTIFY` 不是可靠 queue。
- 需要可查詢每筆 raw item 的處理狀態、模型輸出與錯誤。

### 8.2 欄位

```sql
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
);
```

`event_id` 可在 `events` 建立後回填。為避免 circular dependency，實作 migration 時可以先建表，再 add foreign key：

```sql
alter table raw_item_processing
  add constraint raw_item_processing_event_fk
  foreign key (event_id) references events(id);
```

### 8.3 Constraints / Indexes

```sql
create unique index raw_item_processing_raw_item_uidx
  on raw_item_processing (raw_item_id);

create index raw_item_processing_claim_idx
  on raw_item_processing (status, next_retry_at, created_at);

create index raw_item_processing_locked_idx
  on raw_item_processing (locked_at)
  where status = 'running';

create index raw_item_processing_relevance_idx
  on raw_item_processing (is_relevant, relevance_score desc);
```

### 8.4 Worker Claim Query

建議 worker 使用：

```sql
select id
from raw_item_processing
where status in ('pending', 'retry')
  and (next_retry_at is null or next_retry_at <= now())
order by created_at
limit 50
for update skip locked;
```

stale running task 恢復：

```sql
update raw_item_processing
set status = 'retry',
    next_retry_at = now(),
    locked_by = null,
    locked_at = null,
    updated_at = now()
where status = 'running'
  and locked_at < now() - interval '10 minutes';
```

## 9. events

### 9.1 用途

`events` 保存由 normalizer-classifier 判定有價值的標準事件。V1 的 event 可由單一 raw item 生成，後續版本再支援多 raw item 合併與完整事件生命週期。

### 9.2 欄位

```sql
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
  xauusd_impact_channel text[] not null default '{}',
  requires_confirmation boolean not null default true,
  raw_item_ids uuid[] not null default '{}',
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
    confirmation_state in ('unconfirmed', 'partially_confirmed', 'confirmed', 'contradicted')
  )
);
```

### 9.3 event_type V1 建議值

```text
TRUMP_TRUTH
US_WHITEHOUSE
US_FED
US_SANCTIONS
US_MILITARY
IRAN_GOVERNMENT
IRAN_IRGC
IRAN_SUPREME_LEADER
IRAN_NUCLEAR
ISRAEL_MILITARY
ENERGY_HORMUZ
MARKET_SQUAWK
OTHER_RELEVANT_NEWS
```

`MARKET_MOVE_EXPLAINER` 屬於行情層後續版本。

### 9.4 xauusd_impact_channel V1 建議值

```text
safe_haven
real_rate
inflation
dollar
liquidity
oil
fed_expectation
geopolitical_risk
uncertain
```

V1 不加 check constraint，避免模型輸出與規則調整造成 migration 頻繁變更。

### 9.5 Indexes

```sql
create unique index events_dedupe_key_uidx
  on events (dedupe_key)
  where dedupe_key is not null;

create index events_detected_idx
  on events (detected_at desc);

create index events_severity_detected_idx
  on events (severity, detected_at desc);

create index events_type_detected_idx
  on events (event_type, detected_at desc);

create index events_source_group_idx
  on events (source_group, detected_at desc);

create index events_relevance_idx
  on events (relevance_score desc, detected_at desc);
```

### 9.6 raw_item_ids 設計說明

V1 使用 `uuid[]` 保存 event 對應 raw items，因為單事件多數只對應一筆原始消息。

後續若需要完整多對多關係，可新增：

```text
event_raw_items(event_id, raw_item_id, relation_type)
```

## 10. event_claims

### 10.1 用途

V1 的 `event_claims` 是簡化 claim 保存，用於記錄單條事件中的 claim direction。完整 claim group 與跨來源衝突偵測屬於 V2。

### 10.2 欄位

```sql
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
    claim_direction in ('confirm', 'deny', 'warn', 'escalate', 'deescalate', 'neutral', 'unknown')
  ),
  constraint event_claims_confidence_check check (
    confidence is null or (confidence >= 0 and confidence <= 100)
  )
);
```

### 10.3 Indexes

```sql
create index event_claims_event_idx
  on event_claims (event_id);

create index event_claims_group_idx
  on event_claims (claim_group_id)
  where claim_group_id is not null;

create index event_claims_source_idx
  on event_claims (source_id, created_at desc);
```

## 11. alerts

### 11.1 用途

`alerts` 保存 Telegram / Pushover 發送紀錄、狀態、錯誤與 provider response。

### 11.2 欄位

```sql
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
  alert_score integer,
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
  ),
  constraint alerts_alert_score_check check (
    alert_score is null or alert_score >= 0
  )
);
```

### 11.3 Dedupe

```text
alert:{event_id}:{channel}
```

### 11.4 Indexes

```sql
create unique index alerts_dedupe_key_uidx
  on alerts (dedupe_key);

create index alerts_delivery_claim_idx
  on alerts (delivery_status, next_retry_at, created_at);

create index alerts_event_idx
  on alerts (event_id);

create index alerts_channel_created_idx
  on alerts (channel, created_at desc);
```

## 11.5 event_route_decisions，V1+

### 11.5.1 用途

`event_route_decisions` 保存 `event-router` 對每個出口 route 的 queued / skipped 結果。它不是 delivery queue，而是 audit log，用於回答「為什麼這個 event 有或沒有送到某個出口」。

### 11.5.2 欄位

```sql
create table event_route_decisions (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references events(id) on delete cascade,
  route_key text not null,
  decision_status text not null,
  route_score integer,
  reason text,
  payload_table text,
  payload_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint event_route_decisions_status_check check (
    decision_status in ('queued', 'skipped')
  ),
  constraint event_route_decisions_route_score_check check (
    route_score is null or route_score >= 0
  )
);
```

### 11.5.3 Indexes

```sql
create unique index event_route_decisions_event_route_uidx
  on event_route_decisions (event_id, route_key);

create index event_route_decisions_route_created_idx
  on event_route_decisions (route_key, created_at desc);

create index event_route_decisions_status_created_idx
  on event_route_decisions (decision_status, created_at desc);
```

### 11.5.4 Route keys

```text
private.telegram
private.pushover
public.telegram_channel
public.website
public.x
```

## 11.6 public_outbox，V1+

### 11.6.1 用途

`public_outbox` 保存由 `event-router` 產生、已去敏、可公開、可重試的公共發布 payload。公共網站 sync、Telegram Channel publisher 與 X publisher 都應讀取這張表，而不是各自直接從 `events` 臨時組文案。

### 11.6.2 欄位

```sql
create table public_outbox (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references events(id) on delete cascade,
  public_source_links jsonb not null default '[]'::jsonb,
  severity text not null default 'B',
  relevance_score smallint,
  confirmation_state text,
  topic_tags text[] not null default '{}'::text[],
  approved_for_public boolean not null default false,
  publish_status_web text not null default 'pending',
  publish_status_telegram text not null default 'pending',
  publish_status_x text not null default 'pending',
  retry_count_web integer not null default 0,
  retry_count_telegram integer not null default 0,
  retry_count_x integer not null default 0,
  last_error_web text,
  last_error_telegram text,
  last_error_x text,
  provider_response_telegram jsonb,
  provider_response_x jsonb,
  provider_response_web jsonb,
  external_telegram_message_id text,
  external_x_post_id text,
  external_web_id text,
  next_retry_telegram_at timestamptz,
  next_retry_x_at timestamptz,
  next_retry_web_at timestamptz,
  locked_by_telegram text,
  locked_at_telegram timestamptz,
  locked_by_x text,
  locked_at_x timestamptz,
  locked_by_web text,
  locked_at_web timestamptz,
  generated_at timestamptz not null default now(),
  published_web_at timestamptz,
  published_telegram_at timestamptz,
  published_x_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

### 11.6.3 Indexes

```sql
create unique index public_outbox_event_uidx
  on public_outbox (event_id);

create index public_outbox_telegram_claim_idx
  on public_outbox (publish_status_telegram, next_retry_telegram_at, generated_at)
  where approved_for_public = true;

create index public_outbox_generated_idx
  on public_outbox (generated_at desc);
```

### 11.6.4 發布邊界

- `public_outbox` 只保存 public-safe payload，不保存完整 `text_raw`。
- 公共文案保存在 `public_outbox_translations`，以 `(public_outbox_id, language)` 表示不同語言；`public_outbox` 不再保存固定語言文案欄位。
- `approved_for_public = true` 是所有公共出口的必要條件。
- 不同平台各自使用獨立 status、retry count、error 與 provider response，避免 Telegram Channel、X 與 public web sync 互相影響。
- Publisher 不應讀取 raw item 原文來補寫內容；若 payload 不足，應回到 `event-router` 修正。

## 12. ai_model_calls

### 12.1 用途

`ai_model_calls` 保存 `normalizer-classifier` 每次 AI API 呼叫的 usage 與成本資料，用於評估運行成本、模型品質與不同 source 對 AI call 的消耗。

記錄原則：

- 優先使用 provider response 的 `usage.prompt_tokens`、`usage.completion_tokens`、`usage.total_tokens`。
- 若 provider 未回傳 usage，使用 OpenAI 官方 tokenizer library `tiktoken` 估算，並在 `usage_json.estimated = true` 標記。
- 保存 `request_hash`，不保存完整 prompt。
- 成本先使用內建 pricing table，後續可移到 `infra/model-pricing.json`。

目前 V1 pricing：

| Provider / Model | Input / M token | Output / M token |
| --- | --- | --- |
| `openai_compatible:gpt-5.4-mini` | `$0.75` | `$4.50` |
| `openrouter:openai/gpt-oss-20b` | `$0.029` | `$0.14` |
| `openrouter:openai/gpt-oss-20b:free` | `$0` | `$0` |

### 12.2 欄位

```sql
create table ai_model_calls (
  id uuid primary key default gen_random_uuid(),
  raw_item_id uuid references raw_items(id) on delete set null,
  event_id uuid references events(id) on delete set null,
  source_id uuid references sources(id) on delete set null,
  service_name text not null,
  ai_layer text not null,
  route_name text not null,
  provider text not null,
  model_name text not null,
  request_kind text not null,
  input_tokens integer,
  output_tokens integer,
  total_tokens integer,
  estimated_cost_usd numeric(12, 6),
  latency_ms integer,
  success boolean not null,
  error_type text,
  error_message text,
  response_format text,
  usage_json jsonb not null default '{}'::jsonb,
  request_hash text,
  created_at timestamptz not null default now()
);
```

### 12.3 Indexes

```sql
create index ai_model_calls_created_idx
  on ai_model_calls (created_at desc);

create index ai_model_calls_model_idx
  on ai_model_calls (provider, model_name, created_at desc);

create index ai_model_calls_source_idx
  on ai_model_calls (source_id, created_at desc);

create index ai_model_calls_layer_idx
  on ai_model_calls (ai_layer, created_at desc);

create index ai_model_calls_raw_item_idx
  on ai_model_calls (raw_item_id, created_at desc);
```

## 13. source_health

### 13.1 用途

`source_health` 保存 collector 對每個 source 的運行狀態，供 Dashboard API 與人工排障使用。

同一個 source 可能被不同 service 使用，因此 unique key 應包含 `service_name`。

### 13.2 欄位

```sql
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
    backfill_status is null or backfill_status in ('pending', 'running', 'completed', 'failed')
  )
);
```

### 13.3 Indexes

```sql
create unique index source_health_source_service_uidx
  on source_health (source_id, service_name);

create index source_health_status_idx
  on source_health (status, updated_at desc);

create index source_health_service_idx
  on source_health (service_name, updated_at desc);
```

## 14. schema_migrations

若使用 Alembic，Alembic 會管理版本表。若不用 Alembic，可使用簡單表：

```sql
create table schema_migrations (
  version text primary key,
  applied_at timestamptz not null default now()
);
```

V1 建議使用 Alembic，因為 Python 後端服務為主。incremental migration 與 Docker Compose boot-time migration job 詳見 [Database Migration 策略](./database-migrations.md)。

## 15. Triggers 與 NOTIFY

### 15.1 updated_at trigger

所有有 `updated_at` 的表建議共用：

```sql
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;
```

對各表建立：

```sql
create trigger trg_sources_updated_at
before update on sources
for each row execute function set_updated_at();
```

其他表同理。

### 15.2 raw item processing task trigger

V1 建議在 `raw_items` insert 後自動建立 processing row：

```sql
create or replace function enqueue_raw_item_processing()
returns trigger as $$
begin
  insert into raw_item_processing (raw_item_id)
  values (new.id)
  on conflict (raw_item_id) do nothing;

  perform pg_notify('raw_item_created', new.id::text);
  return new;
end;
$$ language plpgsql;
```

Trigger：

```sql
create trigger trg_raw_items_enqueue_processing
after insert on raw_items
for each row execute function enqueue_raw_item_processing();
```

### 15.3 event created notify

`events` insert 後通知 `event-router`：

```sql
create or replace function notify_event_created()
returns trigger as $$
begin
  perform pg_notify('event_created', new.id::text);
  return new;
end;
$$ language plpgsql;
```

Trigger：

```sql
create trigger trg_events_notify_created
after insert on events
for each row execute function notify_event_created();
```

## 16. Worker 狀態流

### 16.1 raw_item_processing

```text
pending
  ↓ worker claimed
running
  ↓ success irrelevant
skipped

running
  ↓ success relevant
completed

running
  ↓ transient failure
retry

running / retry
  ↓ max attempts exceeded
failed
```

### 16.2 alerts

```text
pending
  ↓ sender claimed
retry
  ↓ provider success
sent

pending / retry
  ↓ provider transient failure
retry

pending / retry
  ↓ permanent failure or max attempts
failed

pending
  ↓ duplicate / policy says no
skipped
```

## 17. Dashboard API 查詢支援

V1 Dashboard API 需要以下查詢高效：

### 17.1 Live Timeline

```sql
select *
from events
order by detected_at desc
limit 50;
```

支援 index：

```text
events_detected_idx
```

### 17.2 High Impact Events

```sql
select *
from events
where severity in ('S', 'A')
order by detected_at desc
limit 50;
```

支援 index：

```text
events_severity_detected_idx
```

### 17.3 Source Health

```sql
select *
from source_health
where service_name = 'telegram-collector'
order by updated_at desc;
```

支援 index：

```text
source_health_service_idx
```

### 17.4 Processing Debug

```sql
select *
from raw_item_processing
where status in ('pending', 'retry', 'failed')
order by created_at desc;
```

支援 index：

```text
raw_item_processing_claim_idx
```

## 18. V1 Seed Data

V1 建議準備 seed migration 或 seed script 寫入 sources。

Telegram examples：

```text
@TrumpTruthSocial_Alert
@Irna_en
@Tasnimnews
@Khamenei_en
@idfofficial
@presstv
@enmehrnews
@israelmfa
@FinancialJuice
@Middle_East_Spectator
@OSINTdefender
```

RSS / HTML examples：

```text
Fed RSS
CENTCOM Press Releases
State Department RSS
Tasnim RSS
SepahNews RSS
Mehr RSS
Press TV RSS / page
Treasury Press Releases
OFAC Recent Actions
Jerusalem Post Iran / Middle East
```

Seed data 應包含：

- `name`
- `handle_or_url`
- `source_type`
- `source_group`
- `official_level`
- `stance`
- `language`
- `priority`
- `reliability_score`
- `latency_score`
- `requires_confirmation`
- `source_config`

## 19. 後續版本 Schema

以下不進 V1 migration。

### 19.1 market_snapshots，V3

用途：保存 XAUUSD 與關聯市場行情。

```text
id
symbol
timeframe
timestamp
open
high
low
close
volume
source
created_at
```

### 19.2 market_move_reviews，V3

用途：行情先動後反查新聞。

```text
id
symbol
window_start
window_end
move_size
move_percent
candidate_event_ids
candidate_raw_item_ids
summary_zh
created_at
```

### 19.3 event_raw_items，V2 / V3

用途：完整支援多 raw items 合併成同一 event。

```text
event_id
raw_item_id
relation_type
created_at
```

### 19.4 raw_item_versions，V2+

用途：保存 Telegram edited message 或 RSS item 更新前後版本。

```text
id
raw_item_id
version_number
title
text_raw
raw_json
created_at
```

### 19.5 claim_groups，V2

用途：完整口徑衝突識別。

```text
id
topic_key
title
summary_zh
confirmation_state
created_at
updated_at
```

## 20. Migration 順序

建議 migration 順序：

1. extensions。
2. `sources`。
3. `raw_items`。
4. `raw_item_processing`，先不加 `event_id` FK。
5. `events`。
6. 補 `raw_item_processing.event_id` FK。
7. `event_claims`。
8. `alerts`。
9. `source_health`。
10. triggers：`updated_at`、`enqueue_raw_item_processing`、`notify_event_created`。
11. seed sources。

## 21. 開放問題

以下細節可在實作 migration 前最後確認：

- V1 是否使用 Alembic 作為 migration 工具。
- `raw_item_processing` 是否同時保存模型輸出，或拆成 `processed_items`。
- `events.raw_item_ids` 使用 `uuid[]` 是否足夠，或一開始就建 `event_raw_items`。
- 是否需要 `source_config` 中的 RSS `etag` / `last_modified` 拆成 typed columns。
- Dashboard API 是否需要 full-text search；若需要，是否加入 `tsvector` 欄位。
