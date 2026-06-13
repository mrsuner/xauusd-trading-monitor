# public-syncer 功能需求

## 1. 服務定位

`public-syncer` 部署在 HomeLab，負責把 `public_outbox` 中已核准公開的事件同步到 VPS `public-api`。它也可選擇性同步 public-safe `raw_items` feed，作為獨立於 events 的公共原始資料源。

它不是 publisher，也不直接發布到社交平台。它的輸出目標只有公共網站 ingest API。

VPS 上的 `public-api` 有自己的 PostgreSQL 與 migrations；`public-syncer` 不需要知道 VPS schema，只需要遵守 `public_event.v1` 與 `public_raw_item.v1` ingest contract。

目標資料流：

```text
public_outbox
  ↓
public-syncer
  ↓ HTTPS
VPS public-api
  ↓
public-postgres
```

Raw feed 資料流：

```text
raw_items + raw_item_translations
  ↓
public_raw_item_sync_state
  ↓
public-syncer
  ↓ HTTPS
VPS public-api /ingest/raw-items
```

## 2. 目標

- 讀取 HomeLab PostgreSQL 的 `public_outbox`。
- 只處理 `approved_for_public = true`。
- 只處理 `publish_status_web in ('pending', 'retry')`。
- 將 `public_outbox` 映射成 `public_event.v1` payload。
- 選擇性將 eligible `raw_items` 映射成 `public_raw_item.v1` payload。
- 以 HTTPS POST 到 VPS `public-api` ingest endpoint。
- 支援 idempotency。
- 支援 HMAC / API key auth。
- 支援 retry / backoff / rate limit。
- 寫回 `publish_status_web`、`published_web_at`、`provider_response_web`、`external_web_id`、`last_error_web`。
- sync 失敗不得影響私人 alert、Telegram Channel 或 X publisher。
- public website 前端由 Cloudflare Pages 部署，`public-syncer` 不直接與 Cloudflare Pages 溝通，只呼叫 VPS `public-api`。

## 3. 非目標

V1 不包含：

- 從 VPS 拉資料。
- 讓 VPS 回調 HomeLab。
- 同步未清洗的 `raw_items.text_raw`、`raw_json`、prompt、AI raw response、token usage。
- public copywriting 或 AI 改寫。
- 社交平台發布。
- 多個 public website destination。
- 人工審核 UI。

## 4. 技術棧

| 類別 | 選型 | 說明 |
| --- | --- | --- |
| Language | Python 3.12+ | 與 HomeLab 後端服務一致 |
| Database | PostgreSQL 16+ | 讀 `public_outbox`，寫 web delivery state |
| DB driver | psycopg 3 | row lock / retry queue |
| HTTP client | httpx | 呼叫 VPS public-api |
| Config | pydantic-settings | env 管理 |
| Validation | pydantic | payload schema |
| Logging | standard logging / structlog | structured logs |
| Packaging | uv | dependency 管理 |
| Container | Docker | HomeLab Compose 部署 |

Go 可作後續備選，但 V1 建議維持 Python。

## 5. 輸入與輸出

### 5.1 輸入

- `public_outbox`。
- optional：`events`，只用於補 event time 或 debug。

### 5.2 輸出

- `POST /ingest/events` 到 VPS `public-api`。
- optional：`POST /ingest/raw-items` 到 VPS `public-api`。
- `public_outbox.publish_status_web`。
- `public_outbox.published_web_at`。
- `public_outbox.provider_response_web`。
- `public_outbox.external_web_id`。
- `public_outbox.last_error_web`。

## 6. Payload Mapping

V1 payload：

```json
{
  "schema_version": "public_event.v1",
  "idempotency_key": "event:<event_id>:v1",
  "upstream_event_id": "uuid",
  "generated_at": "2026-06-01T10:00:00Z",
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
  "route_metadata": {
    "source": "public_outbox"
  }
}
```

欄位原則：

- `idempotency_key` 必須穩定。
- `schema_version` 仍使用 `public_event.v1`；`translations` 是 optional additive field。
- legacy `public_title_*` / `public_summary_*` 必須保留，供已部署 consumer、debug 與 backfill 使用。
- `schema_version` 必須明確。
- `public_source_links` 必須只包含公開 URL。
- 不得加入完整 raw item 原文。
- 不得加入內部 provider response。
- 不得直接同步 `raw_item_translations`；public payload 只包含 public-safe copy。

### 6.1 Raw Item Payload Mapping

`PUBLIC_SYNC_RAW_ITEMS_ENABLED=true` 時，服務會以獨立 state table `public_raw_item_sync_state` 同步 eligible raw items。

V1 payload：

```json
{
  "schema_version": "public_raw_item.v1",
  "idempotency_key": "raw_item:<raw_item_id>:v1",
  "upstream_raw_item_id": "uuid",
  "source": {
    "name": "...",
    "source_type": "telegram",
    "source_group": "macro",
    "official_level": "official",
    "priority": "P1"
  },
  "source_url": "https://...",
  "published_at": "2026-06-13T10:00:00Z",
  "ingested_at": "2026-06-13T10:00:05Z",
  "title": "...",
  "original_content": "scrubbed raw_items.text_clean, capped",
  "summary_zh": "...",
  "summary_en": "...",
  "full_translation_zh": "...",
  "full_translation_en": "...",
  "translations": [
    {
      "language": "zh-Hant",
      "summary": "...",
      "full_translation": "...",
      "status": "completed"
    }
  ],
  "classification": {
    "is_relevant": true,
    "relevance_score": 88
  },
  "topic_tags": [],
  "mentioned_actors": [],
  "upstream_event_ids": []
}
```

Raw feed 欄位原則：

- 只使用 scrub 後的 `raw_items.text_clean`，不得同步 `text_raw`。
- 不同步 `raw_json`、collector metadata、model prompt、model raw response、token usage、私人通知狀態。
- `original_content` 與 `full_translation` 會依 env limit 截斷，並在 payload `scrub_metadata` 中標記。
- raw sync 先處理 event outbox，再處理 raw items，避免 backfill 阻塞事件發布。

## 7. Claim 與並行控制

V1 建議單實例。若多實例，使用 row lock：

```sql
select id
from public_outbox
where approved_for_public = true
  and publish_status_web in ('pending', 'retry')
  and (next_retry_web_at is null or next_retry_web_at <= now())
for update skip locked
limit 1;
```

流程：

```text
claim public_outbox row
  ↓
set publish_status_web = 'sending'
  ↓
build public_event.v1 payload
  ↓
POST VPS public-api
  ↓
success: mark sent
failure: retry / failed
```

## 8. 認證

建議使用 HMAC：

```text
PUBLIC_API_BASE_URL=https://...
PUBLIC_SYNC_KEY_ID=homelab-main
PUBLIC_SYNC_SECRET=...
PUBLIC_SYNC_SIGNATURE_VERSION=hmac-sha256-v1
```

Headers：

```text
X-XER-Key-Id
X-XER-Timestamp
X-XER-Nonce
X-XER-Signature
Idempotency-Key
```

簽名內容：

```text
timestamp + "\n" + nonce + "\n" + idempotency_key + "\n" + sha256(body)
```

V1 可先支援 API key：

```text
Authorization: Bearer <PUBLIC_SYNC_API_KEY>
```

但程式結構應保留 HMAC signer。

## 9. Retry 與 Rate Limit

建議設定：

```text
PUBLIC_SYNCER_ENABLED=false
PUBLIC_SYNCER_DRY_RUN=true
PUBLIC_SYNCER_BATCH_SIZE=10
PUBLIC_SYNCER_MAX_ATTEMPTS=5
PUBLIC_SYNCER_RETRY_BACKOFF_SECONDS=60
PUBLIC_SYNCER_MAX_PER_MINUTE=60
PUBLIC_SYNCER_PROVIDER_TIMEOUT_SECONDS=10
PUBLIC_SYNCER_LOCK_TIMEOUT_SECONDS=300
PUBLIC_SYNCER_POLL_INTERVAL_SECONDS=10
PUBLIC_SYNC_RAW_ITEMS_ENABLED=false
PUBLIC_RAW_BACKFILL_ENABLED=false
PUBLIC_RAW_BATCH_SIZE=20
PUBLIC_RAW_MAX_PER_MINUTE=30
PUBLIC_RAW_MIN_RELEVANCE_SCORE=50
PUBLIC_RAW_MAX_ORIGINAL_CHARS=4000
PUBLIC_RAW_MAX_TRANSLATION_CHARS=8000
```

錯誤處理：

| 錯誤 | 處理 |
| --- | --- |
| 200 / 201 / 202 | mark sent |
| 409 idempotency duplicate | mark sent 或 skipped，保存 external id |
| 400 validation | failed |
| 401 / 403 | failed，operator action required |
| 429 | retry with provider reset / backoff |
| 5xx / timeout | retry |

## 10. 設定

```text
SERVICE_NAME=public-syncer
DATABASE_URL=
PUBLIC_SYNCER_ENABLED=false
PUBLIC_SYNCER_DRY_RUN=true
PUBLIC_API_BASE_URL=
PUBLIC_INGEST_PATH=/ingest/events
PUBLIC_RAW_INGEST_PATH=/ingest/raw-items
PUBLIC_SYNC_AUTH_MODE=hmac
PUBLIC_SYNC_KEY_ID=
PUBLIC_SYNC_SECRET=
PUBLIC_SYNC_API_KEY=
PUBLIC_SYNCER_BATCH_SIZE=10
PUBLIC_SYNCER_MAX_ATTEMPTS=5
PUBLIC_SYNCER_RETRY_BACKOFF_SECONDS=60
PUBLIC_SYNCER_MAX_PER_MINUTE=60
PUBLIC_SYNCER_PROVIDER_TIMEOUT_SECONDS=10
PUBLIC_SYNCER_LOCK_TIMEOUT_SECONDS=300
PUBLIC_SYNCER_POLL_INTERVAL_SECONDS=10
PUBLIC_SYNC_RAW_ITEMS_ENABLED=false
PUBLIC_RAW_BACKFILL_ENABLED=false
PUBLIC_RAW_BATCH_SIZE=20
PUBLIC_RAW_MAX_PER_MINUTE=30
PUBLIC_RAW_MIN_RELEVANCE_SCORE=50
PUBLIC_RAW_MAX_ORIGINAL_CHARS=4000
PUBLIC_RAW_MAX_TRANSLATION_CHARS=8000
LOG_LEVEL=INFO
```

Production 初期應預設：

```text
PUBLIC_SYNCER_ENABLED=false
PUBLIC_SYNCER_DRY_RUN=true
```

HomeLab production Compose 中此服務使用 `public-website` profile；啟用公共網站同步時才啟動。

## 11. 測試策略

Unit tests：

- payload mapping。
- raw item payload scrub / truncation。
- source URL validation。
- HMAC signature。
- idempotency key generation。
- provider error classification。

Integration tests：

- fake `public-api` server。
- dry-run 不送 HTTP 但保存 payload preview。
- 409 duplicate 處理。
- 429 retry。
- 400 validation failed。

Manual test：

- 對 staging VPS 發送 1 筆 fixture。
- 檢查 public database 只有 public-safe 欄位。
- 檢查重複送同一 `idempotency_key` 不新增第二筆事件。

## 12. 驗收標準

- 只同步 `approved_for_public = true` 的資料。
- 同一事件重複同步不產生 duplicate。
- public-api 失敗不影響 HomeLab 其他服務。
- `publish_status_web`、`last_error_web`、`provider_response_web` 可用於排障。
- event payload 不包含 raw item 原文、prompt、token usage 或內部 URL。
- raw item payload 不包含 `text_raw`、`raw_json`、prompt、token usage 或私人 metadata。
