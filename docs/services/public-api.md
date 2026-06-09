# public-api 功能需求

## 1. 服務定位

`public-api` 部署在 VPS，負責接收 HomeLab `public-syncer` 推送的 public-safe events，保存到 public database，並提供公共網站讀取 API。

它不是 HomeLab dashboard API，不讀 HomeLab DB，也不保存內部敏感資料。

VPS 端使用獨立 Docker Compose 啟動 `public-api`、`public-postgres` 與一次性 migration service。公共網站前端 `public-web` 不部署在 VPS Compose 中，後續由 Cloudflare Pages 部署，並透過 public read API 讀取資料。

目標資料流：

```text
HomeLab public-syncer
  ↓ HTTPS ingest
public-api
  ↓
public-postgres
  ↓
public-web
```

## 2. 目標

- 提供 event ingest endpoint。
- 驗證 API key 或 HMAC signature。
- 支援 idempotency。
- 保存 public event 到 VPS database。
- 提供 read-only public endpoints。
- 支援 pagination、filter、event detail。
- 記錄 ingest request audit。
- 可透過 Cloudflare Tunnel 暴露。

## 3. 非目標

V1 不包含：

- 連接 HomeLab DB。
- 管理 HomeLab source registry。
- 私人通知、alert delivery 或 publisher delivery。
- 使用者登入、多租戶、訂閱付費。
- 寫入 raw item、prompt、AI raw response、token usage。
- 在 public-api 內做 AI 分析或事件重新分類。

## 4. 技術棧

| 類別 | 選型 | 說明 |
| --- | --- | --- |
| Language | Python 3.12+ | 與後端服務一致 |
| Web framework | FastAPI | ingest + public read API |
| Database | PostgreSQL 16+ | VPS public database |
| DB driver | psycopg 3 / asyncpg | async preferred |
| Schema | pydantic | request / response schema |
| Config | pydantic-settings | env 管理 |
| Logging | standard logging / structlog | structured logs |
| Packaging | uv | dependency 管理 |
| Container | Docker | VPS Compose 部署 `public-api` 與 migration |

Go 可作後續備選。若 public website 流量變大，`public-api` 可獨立水平擴展。

## 5. API 範圍

### 5.1 Health

```text
GET /health
```

回傳：

```json
{
  "status": "ok",
  "service": "public-api"
}
```

### 5.2 Ingest

```text
POST /ingest/events
```

Headers：

```text
Authorization: Bearer <token>
```

或 HMAC：

```text
X-XER-Key-Id
X-XER-Timestamp
X-XER-Nonce
X-XER-Signature
Idempotency-Key
```

Request body：

```json
{
  "schema_version": "public_event.v1",
  "idempotency_key": "event:<event_id>:v1",
  "upstream_event_id": "uuid",
  "event_time": "2026-06-01T10:00:00Z",
  "generated_at": "2026-06-01T10:00:05Z",
  "severity": "A",
  "relevance_score": 88,
  "confirmation_state": "partially_confirmed",
  "public_title_zh": "...",
  "public_summary_zh": "...",
  "public_title_en": "...",
  "public_summary_en": "...",
  "translations": [
    {
      "language": "en",
      "title": "...",
      "summary": "..."
    },
    {
      "language": "zh-Hant",
      "title": "...",
      "summary": "..."
    }
  ],
  "public_source_links": [],
  "topic_tags": [],
  "content_category": "geopolitics",
  "mentioned_actors": [],
  "route_metadata": {}
}
```

Response：

```json
{
  "status": "accepted",
  "public_event_id": "uuid",
  "idempotency_key": "event:<event_id>:v1"
}
```

重複 `idempotency_key` 應回傳 200 或 409，但 response 必須包含既有 `public_event_id`，方便 HomeLab mark sent。

V1 實作採用 idempotent upsert：同一 `idempotency_key` 不新增第二筆資料，但可以更新 public-safe 文案與 metadata。`upstream_event_id` 建 index，不做 unique constraint，避免未來同一事件因 schema version 或公開文案版本升級而被卡死。

### 5.3 Public Read API

```text
GET /events
GET /events/{public_event_id}
GET /tags
GET /categories
GET /stats/overview
```

`GET /events` filters：

```text
lang
severity
confirmation_state
tag
category
q
from
to
page
page_size
```

`lang` 支援：

- 任意有效 BCP-47-like language code，例如 `en`, `zh-Hant`, `ja`, `fr`。

缺省或無效的 `lang` 會使用 `en`。Read API 會在每筆 event 上衍生：

- `title`
- `summary`
- `language`
- `available_languages`
- `translations`

Fallback 規則：

- 優先使用 requested language 對應的 `public_events_translations` row。
- requested language 缺內容時 fallback 到 English (`en`)。
- English 也缺內容時 fallback 到第一個 available public language。
- Response `language` 必須標示實際使用語言，而不只是 request language。
- 原始 `public_title_*` / `public_summary_*` 欄位在 V1 繼續保留，供前端過渡與 debug；它們只作為 row 缺失時的 fallback/backfill source。

Response 應適合 TanStack Query：

```json
{
  "items": [
    {
      "id": "uuid",
      "title": "Fed rhetoric turns more hawkish",
      "summary": "Fed-linked remarks emphasized persistent inflation...",
      "language": "en",
      "available_languages": ["en", "zh-Hant"],
      "translations": [
        {
          "language": "en",
          "title": "Fed rhetoric turns more hawkish",
          "summary": "Fed-linked remarks emphasized persistent inflation..."
        }
      ],
      "public_title_zh": "...",
      "public_summary_zh": "...",
      "public_title_en": "...",
      "public_summary_en": "..."
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 100
}
```

## 6. Database Schema

V1 建議：

```sql
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
  updated_at timestamptz not null default now()
);

create unique index public_events_idempotency_key_uidx
  on public_events (idempotency_key);

create index public_events_upstream_event_id_idx
  on public_events (upstream_event_id);

create index public_events_event_time_idx
  on public_events (event_time desc);

create index public_events_topic_tags_gin_idx
  on public_events using gin (topic_tags);

create table public_events_translations (
  id uuid primary key default gen_random_uuid(),
  public_event_id uuid not null references public_events(id) on delete cascade,
  language text not null,
  title text,
  summary text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (public_event_id, language)
);
```

Audit table：

```sql
create table public_ingest_requests (
  id uuid primary key default gen_random_uuid(),
  idempotency_key text,
  upstream_event_id uuid,
  request_hash text,
  key_id text,
  status text not null,
  error_message text,
  received_at timestamptz not null default now()
);
```

## 7. Validation

Ingest validation：

- `schema_version` 必須是 supported version。
- `idempotency_key` required。
- `upstream_event_id` required。
- `severity in ('S', 'A', 'B', 'C')`。
- `relevance_score` 介於 0-100 或 null。
- `public_source_links` 必須是 array。
- URL 只允許 `https://` 或 `http://`。
- payload size limit，例如 256 KB。
- summary 欄位長度限制，避免被誤用成全文存放。

## 8. Security

- Ingest endpoint 必須要求 auth。
- Public read endpoints 可以公開，但應經 Cloudflare rate limit。
- HMAC compare 使用 constant-time compare。
- timestamp 允許 skew，例如 5 分鐘。
- nonce / idempotency key 應防 replay。
- 不在 logs 中輸出完整 secret 或 signature。
- 不保存 authorization header。

## 9. 設定

```text
SERVICE_NAME=public-api
PUBLIC_DATABASE_URL=
PUBLIC_API_TOKEN=
PUBLIC_INGEST_AUTH_MODE=hmac
PUBLIC_INGEST_KEY_ID=
PUBLIC_INGEST_SECRET=
PUBLIC_INGEST_MAX_BODY_BYTES=262144
PUBLIC_INGEST_TIMESTAMP_SKEW_SECONDS=300
CORS_ORIGINS=https://...
DEFAULT_PAGE_SIZE=20
MAX_PAGE_SIZE=100
LOG_LEVEL=INFO
```

VPS Docker Compose 使用：

```text
infra/docker-compose.public-api.yml
infra/.env.public-api.example
```

啟動順序：

```text
public-postgres
  ↓ healthy
public-api-migrate
  ↓ alembic upgrade head
public-api
```

公共網站 `public-web` 由 Cloudflare Pages 部署，不加入這份 Compose。

## 10. 測試策略

Unit tests：

- request schema validation。
- idempotency handling。
- HMAC verification。
- URL validation。
- filter query builder。

Integration tests：

- ingest event fixture。
- duplicate ingest。
- invalid signature。
- read events pagination。
- hidden event 不出現在 public list。

## 11. 驗收標準

- HomeLab 可透過 HTTPS ingest 成功寫入 public event。
- 重複 `idempotency_key` 不產生重複資料。
- public read API 不回傳任何 private/internal 欄位。
- invalid auth 無法 ingest。
- public-web 可以只透過 public-api 完成事件列表與詳情頁。
