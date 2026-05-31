# dashboard-api 功能需求

## 1. 服務定位

`dashboard-api` 是 V1 可選的最小查詢 API，負責讓使用者或後續 Dashboard Web 查看系統狀態、來源健康、原始消息、處理結果、事件與通知紀錄。

V1 不要求完整前端，但建議先建立 API 邊界，方便 debug 與後續 Dashboard Web 開發。

## 2. V1 目標

- 提供 read-only API 查詢 V1 核心資料。
- 支援 source health 檢查。
- 支援 raw items 查詢。
- 支援 processing status 查詢。
- 支援 events 查詢。
- 支援 alerts 查詢。
- 提供基本 health endpoint。

## 2.1 實作狀態

目前已建立 `services/dashboard-api` 最小服務骨架：

- FastAPI app factory。
- PostgreSQL connection pool。
- API token middleware。
- CORS 設定。
- read-only list / detail endpoints。
- pagination helper。
- Dockerfile。
- `make dev` 本機啟動整合。

V1 實作仍維持 read-only，不包含 source 管理寫入。

## 3. 非目標

V1 不包含：

- 完整 dashboard web UI。
- 使用者登入與多租戶。
- source 編輯 UI；後續版本需要支援從 Dashboard 新增、停用與測試 Telegram/RSS sources。
- alert preference UI。
- market chart。
- 行情事件疊加。
- WebSocket 即時推送，除非實作成本很低。

## 4. 技術棧

| 類別 | 選型 | 說明 |
| --- | --- | --- |
| Language | Python 3.12+ | V1 主語言 |
| Web framework | FastAPI | read-only API |
| Database | PostgreSQL 16+ | 查詢核心資料 |
| DB driver | psycopg 3 / asyncpg | async preferred |
| Schema | pydantic | response schema |
| Config | pydantic-settings | env 管理 |
| Logging | structlog / standard logging | structured logs |
| Packaging | uv | dependency 管理 |
| Container | Docker | HomeLab 部署 |

Go 備選：`chi` / `fiber` + `pgx`。

## 5. 前端技術約束

後續 `dashboard-web` 統一使用：

- React Router V7
- TanStack Query
- TailwindCSS V4
- DaisyUI V5

因此 API response 應適合 TanStack Query 消費：

- JSON response。
- 穩定 query params。
- pagination metadata。
- 明確 error format。

## 6. API 範圍

V1 endpoints 建議：

```text
GET /health
GET /sources
GET /sources/{source_id}
GET /source-health
GET /raw-items
GET /raw-items/{raw_item_id}
GET /processing
GET /events
GET /events/{event_id}
GET /alerts
```

可選：

```text
GET /stats/overview
GET /stats/ingestion
```

後續 source 管理 endpoints：

```text
POST /sources
PATCH /sources/{source_id}
POST /sources/{source_id}/test
POST /sources/{source_id}/backfill
```

用途：

- 從 Dashboard 新增 Telegram channel，例如 `@fbsanalytics`。
- 測試 source 是否可 resolve / fetch。
- 啟用或停用 source。
- 觸發小範圍 backfill，確認 raw item 能入庫。

## 7. 查詢需求

### 7.1 Sources

支援 filter：

```text
source_type
source_group
priority
enabled
```

用途：

- 確認 source registry。
- 查看來源立場與官方程度。

### 7.2 Source Health

支援：

```text
service_name
status
source_type
```

回傳：

- last success。
- last error。
- last message time。
- 1h / 24h ingest count。

### 7.3 Raw Items

支援 filter：

```text
source_id
source_type
source_group
published_from
published_to
ingested_from
ingested_to
q
```

要求：

- 預設按 `published_at desc`。
- 需要 pagination。
- list response 需包含 `summary_zh`、`summary_en`、`translation_status`，方便 timeline 顯示。
- raw item detail / event detail 需包含 `full_translation_zh`、`full_translation_en`、`translation_model` 與 `translation_error`，方便閱讀與 debug。
- 大欄位如 `raw_json` 可在 list response 中省略，detail endpoint 再回傳。

### 7.4 Processing

支援 filter：

```text
status
stage
is_relevant
min_relevance_score
model_provider
```

用途：

- debug pending / failed tasks。
- 查看模型輸出。

### 7.5 Events

支援 filter：

```text
severity
event_type
source_group
min_relevance_score
created_from
created_to
```

用途：

- Live Timeline。
- High Impact Events。

### 7.6 Alerts

支援 filter：

```text
channel
delivery_status
priority
created_from
created_to
```

用途：

- 檢查通知是否發送。
- debug provider error。

## 8. Response 格式

List response：

```json
{
  "items": [],
  "page": 1,
  "page_size": 50,
  "total": 123
}
```

Error response：

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Invalid source_id"
  }
}
```

## 9. 安全需求

V1 如果只部署在 HomeLab 內網，可先使用簡單 API token。

要求：

- read-only DB user，除 health endpoint 外不寫資料。
- `GET /health` 不需要 token。
- 其他 endpoints 若設定 `API_TOKEN`，需使用 `Authorization: Bearer <token>` 或 `X-API-Token: <token>`。
- 不暴露 secrets。
- 不在 API 回傳 Telegram session path。
- `raw_json` detail endpoint 需避免回傳敏感 auth 資訊。
- 若透過 Tailscale / reverse proxy 對外，必須加 token。

## 10. Runtime 設定

必要 env：

```text
DATABASE_URL=postgresql://xauusd:password@postgres:5432/xauusd_event_radar
API_TOKEN=change-me
CORS_ORIGINS=http://localhost:5173
DEFAULT_PAGE_SIZE=50
MAX_PAGE_SIZE=200
HOST=0.0.0.0
PORT=8080
LOG_LEVEL=INFO
```

本機開發：

```text
make dev
curl http://localhost:8080/health
```

## 11. Observability

Metrics：

- request count
- request latency
- 4xx / 5xx count
- DB query latency

Logs：

- method
- path
- status_code
- duration_ms
- error_type

## 12. 測試需求

單元測試：

- query param validation。
- response schema。
- pagination。
- auth token middleware。

整合測試：

- test database query。
- list/detail endpoints。
- filter combinations。
- read-only DB behavior。

## 13. 驗收標準

- `/health` 可回傳服務狀態。
- 可查 sources、source health、raw items、processing、events、alerts。
- list endpoints 支援 pagination。
- detail endpoints 可查看 debug 所需內容。
- API 不修改核心資料。
- response 可直接被 TanStack Query 消費。
