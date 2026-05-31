# alert-dispatcher 功能需求

## 1. 服務定位

`alert-dispatcher` 是 V1 新聞消息層的通知出口服務，負責把 `normalizer-classifier` 產生的高相關 `events` 轉換成可掃描、可追蹤、可重試的 Telegram Bot 與 Pushover 通知。

此服務不做採集、不做 AI 分析、不做交易判斷。它只根據已入庫的事件、來源 metadata、相關度分數、severity 與通知規則決定是否發送、發送到哪個 channel、用什麼 priority，並把 delivery result 寫回 `alerts`。

V1 的目標不是「每條新聞都提醒」，而是建立一條低噪音通知通道：

```text
events
  ↓
alert-dispatcher
  ↓
alerts pending / sent / failed / skipped
  ↓
Telegram Bot / Pushover
```

## 2. V1 目標

- 監聽 `event_created` PostgreSQL notification，或以 polling fallback 掃描近期未處理事件。
- 讀取 `events`、`sources`、`raw_items`、`event_claims` 與既有 `alerts`。
- 根據 relevance score、severity、source priority、official level、requires confirmation 與 source group 決定通知策略。
- 對每個應通知 channel 建立或 claim `alerts` row。
- 格式化 Telegram / Pushover message。
- 發送 Telegram Bot API message。
- 發送 Pushover message。
- 記錄 provider response、sent time、delivery status、attempt count 與 error message。
- 支援 dedupe，避免同一事件同一 channel 重複通知。
- 支援 retry 與 backoff。
- 對 OSINT / aggregator 單源消息降噪。
- 保證通知內容不包含交易指令。

## 2.1 實作狀態

目前已完成：

- DB schema：`alerts` table、dedupe index、delivery claim index。
- DB trigger：`events` insert 後 `pg_notify('event_created', event_id)`。
- Production Compose placeholder：`infra/docker-compose.prod.yml` 已定義 `alert-dispatcher` service。
- `services/alert-dispatcher` Python service。
- Telegram / Pushover provider adapter。
- `make dev` 本機啟動整合。
- 單元測試與整合測試。
- 文檔規格：本文件。

V1 runtime 已實作：

- 以 polling fallback 掃描 `events` 並建立 `alerts` decision rows。
- 根據 policy 對 `telegram` / `pushover` 建立 `pending` 或 `skipped` alert。
- 根據 source-level alert policy、`alert_score`、Pushover allowlist、rate limit 與 cooldown 進行通知降噪。
- claim `pending` / `retry` alerts 並發送 provider request。
- 支援 `ALERT_DRY_RUN`，開發模式可記錄決策但不實際推送。
- 支援 `ALERT_BACKFILL_MODE=skip|telegram_only|normal`，避免 backfill 或首次啟動造成 Pushover spam。
- 支援 provider error retry / backoff / max attempts。
- 已加入 `make dev` 與 production Compose。

後續可補強：

- 直接使用 PostgreSQL `LISTEN event_created` 降低延遲。
- 更細緻的 user preference / quiet hours / 多 chat routing。

## 3. 非目標

V1 不包含：

- 自動交易、做多/做空建議、倉位建議或風險參數。
- 使用者偏好 UI。
- 多使用者、多 chat routing 或權限模型。
- 複雜 escalation policy。
- 排班與 quiet hours。
- 通知中心寫入 API。
- WebSocket push。
- 以行情波動反查消息；這屬於後續 market layer。

## 4. 技術棧

| 類別 | 選型 | 說明 |
| --- | --- | --- |
| Language | Python 3.12+ | V1 主語言，與其他 backend services 保持一致 |
| Database | PostgreSQL 16+ | 讀 `events`，寫 `alerts` |
| DB driver | psycopg 3 | `LISTEN/NOTIFY`、row locking、JSONB |
| HTTP client | httpx | Telegram Bot API / Pushover REST |
| Config | pydantic-settings | env 管理 |
| Validation | pydantic | message payload / provider response schema |
| Logging | standard logging / structlog | structured logs |
| Packaging | uv | dependency 管理 |
| Container | Docker | HomeLab 部署 |

Go 可作為後續備選，適合單 binary、低 footprint 的通知 worker，但 V1 建議使用 Python 以降低 monorepo 複雜度。

## 5. 輸入與輸出

### 5.1 輸入

- `events`
- `sources`
- `raw_items`
- `event_claims`
- `alerts`
- `event_created` notification

### 5.2 輸出

- Telegram Bot message。
- Pushover message。
- `alerts` delivery tracking rows。
- structured logs。

## 6. 資料流

V1 推薦採用「notification 加 polling fallback」：

```text
normalizer-classifier creates event
  ↓
PostgreSQL trigger emits event_created(event_id)
  ↓
alert-dispatcher receives event_id
  ↓
load event context
  ↓
evaluate notification policy
  ↓
upsert or claim alerts rows per channel
  ↓
send provider request
  ↓
write delivery result
```

若 `LISTEN/NOTIFY` 斷線或服務重啟，dispatcher 必須靠 polling 補漏：

```text
poll events from last N minutes
  ↓
find events without sent/skipped alerts for required channels
  ↓
evaluate and send
```

關鍵原則：

- PostgreSQL 是 source of truth。
- `NOTIFY` 只用於降低延遲，不是唯一可靠 queue。
- `alerts` table 保存每次通知決策與發送狀態。
- 同一 `event_id` 同一 channel 只允許一筆有效通知紀錄。

## 7. Notification Policy

V1+ 已改為 source-aware policy。`alert-dispatcher` 不再只依賴 `severity`，而是計算可 audit 的 `alert_score`：

```text
alert_score =
  severity_score
  + relevance_score_weight
  + source_priority_score
  + official_level_score
  + source_alert_weight
  - requires_confirmation_penalty
  - aggregator_penalty
  - low_confidence_penalty
```

Channel decision：

| Channel | 條件 |
| --- | --- |
| Telegram | `source.telegram_alert_enabled = true`、達到 `source.telegram_min_severity`、未超過 source rate limit / cooldown、`alert_score >= 45`；S 級事件可用較低 threshold |
| Pushover | `source.pushover_alert_enabled = true`、達到 `source.pushover_min_severity`、不是 aggregator source、未超過 source rate limit / cooldown、`alert_score >= 85` |

Source-level policy 欄位：

| 欄位 | 說明 |
| --- | --- |
| `telegram_alert_enabled` | 此 source 是否允許 Telegram 通知 |
| `pushover_alert_enabled` | 此 source 是否允許 Pushover 通知 |
| `telegram_min_severity` | Telegram 最低通知等級 |
| `pushover_min_severity` | Pushover 最低通知等級 |
| `alert_weight` | source-level 權重，0-100 |
| `alert_rate_limit_per_hour` | 單一 source 每小時最多 pending/sent/retry alert 數量 |
| `alert_cooldown_minutes` | 同一 source 兩次通知的最小間隔 |

`Pushover emergency` 必須保守使用。V1 只允許以下情境進入 emergency 候選：

- `severity = S`。
- `alert_score >= 95`。
- `source.priority in ('P0', 'P1')`。
- `source.official_level in ('official', 'semi_official')`。
- `source.source_group` 不屬於 `osint_aggregator` 或純 `market_squawk`。
- `requires_confirmation = false`，或已有官方 / 半官方來源確認。

Backfill policy：

| `ALERT_BACKFILL_MODE` | 行為 |
| --- | --- |
| `skip` | 對 dispatcher 啟動前已存在的 event 建立 skipped decision，不實際推送 |
| `telegram_only` | 啟動前 event 只允許 Telegram，不允許 Pushover |
| `normal` | 啟動前 event 依正常 policy 判斷 |

## 8. Event Context

發送前需要組裝最小 context：

```text
event
  ├── source metadata
  ├── primary raw item
  ├── related event_claims
  └── existing alerts
```

V1 可先使用 `events.raw_item_ids[0]` 作為 primary raw item。若事件沒有 raw item 或 source metadata 不完整，仍可發 Telegram，但應降低 Pushover priority 或跳過 Pushover。

必要欄位：

- `events.id`
- `events.event_time`
- `events.event_type`
- `events.severity`
- `events.relevance_score`
- `events.confidence`
- `events.title`
- `events.summary_zh`
- `events.confirmation_state`
- `events.requires_confirmation`
- `events.xauusd_impact_channel`
- `sources.name`
- `sources.source_group`
- `sources.official_level`
- `sources.priority`
- `raw_items.url`

## 9. Alerts Table Contract

既有 schema：

```text
id
event_id
channel                  telegram / pushover
priority                 normal / high / emergency
dedupe_key
message
sent_at
delivery_status          pending / sent / failed / skipped / retry
attempt_count
next_retry_at
locked_by
locked_at
provider_response_json
error_message
created_at
updated_at
```

Unique：

```text
unique(dedupe_key)
```

建議 dedupe key：

```text
alert:{event_id}:{channel}
```

後續若支援近似去重，可新增 policy 層級 dedupe key，但不要取代 event-channel dedupe：

```text
alert-policy:{event_type}:{source_group}:{normalized_title_hash}:{time_bucket}
```

## 10. Delivery State Machine

狀態轉換：

```text
pending
  ├── sent
  ├── skipped
  ├── retry
  └── failed

retry
  ├── sent
  ├── retry
  └── failed
```

規則：

- `pending`：已決定要通知，但尚未送出。
- `sent`：provider 成功接受。
- `skipped`：規則判定不應發送、duplicate，或必要 provider config 缺失。
- `retry`：暫時性錯誤，等待 `next_retry_at`。
- `failed`：超過 retry 次數，或永久錯誤。

Worker claim 使用：

```sql
select ...
from alerts
where delivery_status in ('pending', 'retry')
  and (next_retry_at is null or next_retry_at <= now())
order by created_at asc
for update skip locked
limit ...
```

更新時寫入：

- `locked_by`
- `locked_at`
- `attempt_count`
- `provider_response_json`
- `error_message`

## 11. Message 格式

### 11.1 Telegram

Telegram message 要短、可掃描、可人工驗證。

範例：

```text
[A] IRAN_NUCLEAR | relevance 86 | confidence 72

Tasnim 否認伊朗將放棄濃縮鈾的說法。

Source: Tasnim (@Tasnimnews)
Group: iran_irgc_adjacent
Official: semi_official
Confirmation: requires confirmation
Impact: safe_haven, oil_inflation

URL: https://...
```

要求：

- 顯示 severity。
- 顯示 event type。
- 顯示 relevance score 與 confidence。
- 優先顯示 `summary_zh`。
- 顯示 source name / source group / official level。
- 顯示 confirmation state 或 requires confirmation。
- 顯示 impact channel。
- 有 URL 時提供 URL。
- 不輸出交易指令、進場點、止損、止盈、倉位建議。

### 11.2 Pushover

Pushover 用於手機即時提醒，訊息應更短。

Title：

```text
[A] IRAN_NUCLEAR relevance 86
```

Message：

```text
Tasnim 否認伊朗將放棄濃縮鈾的說法。
Source: Tasnim
Requires confirmation.
```

Priority mapping：

| Severity | Pushover priority |
| --- | --- |
| S | 1 或 2 |
| A | 0 |
| B | 不發送 |
| C | 不發送 |

若使用 priority `2` emergency，必須帶：

- `retry = PUSHOVER_EMERGENCY_RETRY_SECONDS`
- `expire = PUSHOVER_EMERGENCY_EXPIRE_SECONDS`

## 12. Provider Adapter

建議抽象：

```text
class AlertProvider:
  send(alert, context) -> ProviderResult
```

Provider：

- `TelegramProvider`
- `PushoverProvider`

`ProviderResult`：

```text
success
status_code
response_json
retry_after_seconds
error_message
is_transient
```

### 12.1 Telegram Bot API

V1 使用：

```text
POST https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage
```

Payload：

```json
{
  "chat_id": "...",
  "text": "...",
  "disable_web_page_preview": true
}
```

V1 可先不使用 Markdown / HTML parse mode，避免來源文字破壞格式。後續需要格式化時再加入 escaping。

### 12.2 Pushover

V1 使用：

```text
POST https://api.pushover.net/1/messages.json
```

Payload：

```json
{
  "token": "...",
  "user": "...",
  "title": "...",
  "message": "...",
  "priority": 0
}
```

Emergency payload 額外包含：

```json
{
  "priority": 2,
  "retry": 60,
  "expire": 600
}
```

## 13. 錯誤處理與 Retry

| 類型 | 處理方式 |
| --- | --- |
| Telegram `429` | respect `retry_after`，設為 `retry` |
| Telegram `400 chat not found` | 設為 `failed`，需人工修設定 |
| Telegram token missing | 建立 `skipped` 或 `failed`，依 channel policy 決定 |
| Pushover transient error | 設為 `retry` |
| Pushover credential error | 設為 `failed` |
| DB connection failed | service-level retry |
| message formatting failed | 設為 `failed`，保存 error |
| duplicate alert | 設為 `skipped` 或忽略 insert conflict |

Retry 建議：

```text
MAX_ATTEMPTS=3
INITIAL_BACKOFF_SECONDS=10
MAX_BACKOFF_SECONDS=300
```

Backoff：

```text
next_retry_at = now + min(MAX_BACKOFF_SECONDS, INITIAL_BACKOFF_SECONDS * 2 ^ attempt_count)
```

若 provider 明確回傳 `retry_after`，優先使用 provider 建議。

## 14. 設定項

```text
APP_ENV=development
SERVICE_NAME=alert-dispatcher
DATABASE_URL=postgresql://...

TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

PUSHOVER_APP_TOKEN=...
PUSHOVER_USER_KEY=...
PUSHOVER_EMERGENCY_RETRY_SECONDS=60
PUSHOVER_EMERGENCY_EXPIRE_SECONDS=600

ENABLE_TELEGRAM_ALERTS=true
ENABLE_PUSHOVER_ALERTS=true
ENABLE_POLLING_FALLBACK=true
POLL_INTERVAL_SECONDS=2
EVENT_LOOKBACK_MINUTES=120

MAX_ATTEMPTS=3
INITIAL_BACKOFF_SECONDS=10
MAX_BACKOFF_SECONDS=300

LOG_LEVEL=INFO
```

Secrets 不得提交到 repo。Production 使用 `infra/.env.example` 作為模板，本機使用 `infra/.env.dev`。

## 15. Deployment

Production：

- `infra/docker-compose.prod.yml` 啟動 `alert-dispatcher`。
- image path：

```text
ghcr.io/mrsuner/xauusd-trading-monitor/alert-dispatcher:<tag>
```

啟動順序：

```text
postgres healthy
  ↓
db-migrate completed
  ↓
normalizer-classifier / alert-dispatcher
```

本機開發：

- 後續建立 `services/alert-dispatcher` 後加入 `make dev`。
- 本機可以先只啟用 Telegram alert，Pushover 用 mock 或 disabled。

## 16. Observability

Metrics 建議：

- pending alert count。
- retry alert count。
- failed alert count。
- sent count by channel。
- skipped count by reason。
- provider latency。
- provider error count。
- duplicate count。

Structured logs 欄位：

- `service_name`
- `event_id`
- `alert_id`
- `channel`
- `priority`
- `delivery_status`
- `attempt_count`
- `provider_status_code`
- `error_type`
- `latency_ms`

Dashboard V1 已可透過 `GET /alerts` 查看 delivery status。後續可加入 alert health card。

## 17. 測試需求

單元測試：

- notification decision rules。
- Pushover priority mapping。
- emergency guardrail。
- dedupe key generation。
- Telegram formatter。
- Pushover formatter。
- provider response parsing。
- retry backoff calculation。

整合測試：

- mock Telegram Bot API。
- mock Pushover API。
- `events` insert 後可產生 alert。
- failed retry。
- duplicate skip。
- alerts table status update。
- missing provider config 時不 crash。

手動 smoke test：

1. 插入一筆 `severity = A`、`relevance_score >= 85` 的 event。
2. 確認 Telegram 收到通知。
3. 確認 Pushover 收到通知，priority 為 normal。
4. 重跑 dispatcher，確認同一 event 不重複發送。
5. 停用 Telegram token，確認 alert row 進入 `failed` 或 `skipped` 並保存 error。

## 18. 驗收標準

- 高相關事件能按規則發送 Telegram / Pushover。
- 中等相關事件只發 Telegram。
- 低相關事件不發送。
- OSINT / aggregator 單源不發 Pushover。
- 同一事件同一 channel 不重複發送。
- provider 失敗可 retry。
- retry 超限後進入 `failed`。
- 發送結果完整寫入 `alerts`。
- Dashboard API 能查到 alerts delivery status。
- 通知內容不包含交易指令。

## 19. 後續增強

V1 後可考慮：

- Dashboard source / alert preference UI。
- per-source 或 per-source-group notification policy。
- quiet hours。
- 多 Telegram chat routing。
- alert grouping。
- market move explainer 通知。
- Slack / Discord / email provider。
- WebSocket 即時通知 Dashboard。
