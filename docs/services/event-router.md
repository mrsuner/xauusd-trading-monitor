# event-router 功能需求

## 1. 服務定位

`event-router` 是 `events` 之後的出口決策服務。它負責判斷一個已標準化事件應該送往哪些下游出口，並建立對應的 delivery queue row。

它不做資料採集、不做 AI 分析、不呼叫平台 API、不直接發送通知。它只回答三個問題：

- 這個 event 是否值得送出？
- 應該送到哪些 route？
- 每個 route 的 payload、priority、初始狀態與跳過原因是什麼？

跨來源語義合併不屬於 `event-router`。若多個來源報導同一事件，應先由 `event-clustering` 合併成 canonical event，再交給 `event-router` 決定是否廣播。設計見 [event-clustering / semantic dedupe 設計草案](./event-clustering.md)。

目標資料流：

```text
normalizer-classifier
  ↓
events / event_claims
  ↓
event-router
  ├── alerts
  │     └── alert-dispatcher
  │           └── private Telegram / Pushover
  └── public_outbox
        ├── telegram-channel-publisher
        ├── x-publisher
        └── public-syncer / public website
```

核心邊界：

```text
event-router = what / where / why
dispatcher / publisher = how to send
```

## 2. 設計原則

### 2.1 路由決策集中化

所有出口判斷集中在 `event-router`，避免 `alert-dispatcher`、`telegram-channel-publisher`、`x-publisher` 各自重複判斷事件價值。

下游服務只處理：

- claim queue row。
- 按平台 API 要求做最後一層 deterministic packaging。
- 發送 request。
- 寫回 delivery status、provider response 與 external id。

### 2.2 內容與格式分離

不同 publisher 需要不同格式，但不應各自重新理解事件。

V1 使用既有 AI Layer 1 / Layer 2 產出的結構化內容：

- `raw_items.summary_zh`
- `raw_items.summary_en`
- `events.title`
- `events.summary_zh`
- `events.summary_en`
- `events.severity`
- `events.relevance_score`
- `events.confirmation_state`
- `events.xauusd_impact_channel`
- `event_claims`

`event-router` 產生 route payload；publisher 只做 deterministic formatter。

V1 不針對每個 publisher 再次呼叫 AI 改寫。後續若加入 `public-copy-adapter`，也只能做低風險壓縮與語氣適配，不得新增事實或改變不確定性。

### 2.3 可審計

每個 route 都應能回答：

- 為什麼送出？
- 為什麼跳過？
- 使用了什麼 score？
- 寫入了哪個下游 queue？

因此建議新增 `event_route_decisions` 作為 audit log。

## 3. Route Keys

V1 建議使用固定 route key：

```text
private.telegram
private.pushover
public.telegram_channel
public.website
public.x
```

V1 初期啟用：

```text
private.telegram
private.pushover
public.telegram_channel
```

後續啟用：

```text
public.website
public.x
```

## 4. 輸入與輸出

### 4.1 輸入

- `events`
- `event_claims`
- `sources`
- primary `raw_items`
- existing route / delivery rows

### 4.2 輸出

- `alerts`：私人 Telegram / Pushover delivery queue。
- `public_outbox`：公共出口 public-safe payload 與平台 delivery status。
- `event_route_decisions`：每個 route 的 queued / skipped audit log。
- structured logs。

## 5. Route Score

`event-router` 應計算中性的 `route_score`，不稱為交易分數，也不代表方向判斷。

建議公式：

```text
route_score =
  severity_score
  + relevance_score_component
  + source_priority_score
  + official_level_score
  + source_alert_weight
  + confirmation_bonus_or_penalty
  - aggregator_penalty
  - low_confidence_penalty
  - duplicate_penalty
```

參考權重：

| 因子 | 分數 |
| --- | --- |
| `severity = S` | +50 |
| `severity = A` | +35 |
| `severity = B` | +15 |
| `severity = C` | +0 |
| `relevance_score` | `score / 5` |
| `source.priority = P0` | +20 |
| `source.priority = P1` | +12 |
| `source.priority = P2` | +4 |
| `official_level = official` | +20 |
| `official_level = semi_official` | +12 |
| `official_level = unofficial_mirror` | +6 |
| `official_level = aggregator` | -8 |
| `source_group in osint_aggregator / market_squawk` | -20 |
| `requires_confirmation` 且未確認 | -15 |
| `confidence < 60` | -10 |

## 6. Route Policy

### 6.1 Private Telegram

條件：

```text
source.telegram_alert_enabled = true
severity >= source.telegram_min_severity
not source rate limited
route_score >= 45
```

S 級事件可使用較低 threshold，但仍需保留 source cooldown。

輸出：

```text
alerts.channel = 'telegram'
alerts.priority = high if severity = S else normal
alerts.dedupe_key = alert:{event_id}:telegram
```

### 6.2 Private Pushover

條件：

```text
source.pushover_alert_enabled = true
severity >= source.pushover_min_severity
source_group not in aggregator groups
official_level != aggregator
not source rate limited
route_score >= 85
```

`emergency` 必須更保守：

```text
severity = S
route_score >= 95
source.priority in ('P0', 'P1')
official_level in ('official', 'semi_official')
confirmation_state in ('confirmed', 'partially_confirmed')
```

輸出：

```text
alerts.channel = 'pushover'
alerts.priority = normal / high / emergency
alerts.dedupe_key = alert:{event_id}:pushover
```

### 6.3 Public Telegram Channel

條件：

```text
severity in ('S', 'A')
or severity = 'B' and relevance_score >= 80
has public source URL
route_score >= 65
```

Aggregator / OSINT 限制：

```text
source_group in ('osint_aggregator', 'market_squawk')
requires confirmation:
  confirmation_state in ('confirmed', 'partially_confirmed')
  or multiple independent claims exist
```

輸出：

```text
public_outbox.publish_status_telegram = 'pending'
approved_for_public = true or false by public safety policy
```

### 6.4 Public Website

條件較 Telegram Channel 寬鬆：

```text
severity in ('S', 'A', 'B')
route_score >= 50
has usable public summary
```

輸出：

```text
public_outbox.publish_status_web = 'pending'
```

V1 可以先不啟用 public website route，等 VPS `public-api` / `public-web` 實作後再開啟。

### 6.5 Public X

條件最保守：

```text
severity = 'S'
or severity = 'A' and relevance_score >= 90
has public source URL
has concise public title / summary
route_score >= 85
```

輸出：

```text
public_outbox.publish_status_x = 'pending'
```

V1 不啟用，待 `x-publisher` 完成後再開啟。

## 7. Public Payload

`event-router` 負責從 event semantic data 建立 public-safe payload：

```text
public_title_zh
public_summary_zh
public_title_en
public_summary_en
public_source_links
severity
relevance_score
confirmation_state
topic_tags
approved_for_public
```

Public payload 規則：

- 中文優先，英文 fallback。
- 不包含私人 Telegram chat id、Pushover user key、內部 API URL 或 HomeLab IP。
- 不發布完整 `text_raw`。
- 不新增事件中不存在的事實。
- 未確認事件必須保留不確定性描述。
- 至少保留一個可公開 source URL；否則 `approved_for_public = false`。

`public_outbox` 是公共出口 contract。Publisher 不應再讀 raw item 原文來補寫內容。

## 8. Private Alert Payload

`event-router` 同時負責建立私人通知 payload，寫入 `alerts.message`。`alert-dispatcher` 不重新組文案，只依 `alerts.channel` 與 `alerts.priority` 選擇 provider。

私人 Telegram 可包含較完整的 operational context：

```text
[A] IRAN_NUCLEAR | relevance 86 | confidence 72

Tasnim 否認伊朗將放棄濃縮鈾的說法。

Source: Tasnim (@Tasnimnews)
Group: iran_irgc_adjacent
Official: semi_official
Confirmation: unconfirmed; requires confirmation
Impact: safe_haven, oil_inflation

URL: https://...
```

Pushover 應更短，只保留手機上需要立即掃描的資訊：

```text
[S] IRAN_IRGC relevance 94

SepahNews 發布與報復、導彈或霍爾木茲相關聲明。
Source: SepahNews
Confirmed / Requires confirmation
https://...
```

格式原則：

- 不輸出交易指令。
- 中文摘要優先，英文 fallback。
- Telegram 可包含 source group、official level、impact channel、confirmation state。
- Pushover 只放最短摘要、來源與確認狀態。
- message text 由 deterministic formatter 生成，不再呼叫 AI。

## 9. Platform Payload Strategy

V1 不為每個 publisher 再次呼叫 AI 改寫內容。資料來源順序：

```text
events.summary_zh
events.summary_en
raw_items.summary_zh
raw_items.summary_en
raw_items.text_clean
```

平台差異由 deterministic formatter 處理：

| Outlet | Payload source | Formatter owner |
| --- | --- | --- |
| private Telegram | `alerts.message` | `event-router` |
| private Pushover | `alerts.message` | `event-router` |
| Telegram Channel | `public_outbox` | `telegram-channel-publisher` final packaging only |
| X | `public_outbox` | `x-publisher` final packaging only |
| Public Website | `public_outbox` | `public-web` renderer |

若 V2 加入 `public-copy-adapter`，必須保存 model、prompt version、token usage 與 rendered payload，且只能做壓縮與語氣適配，不得新增事實或改變不確定性。

## 10. event_route_decisions

建議新增資料表：

```text
event_route_decisions
  id
  event_id
  route_key
  decision_status        queued / skipped
  route_score
  reason
  payload_table          alerts / public_outbox / none
  payload_id
  created_at
  updated_at
```

約束：

```text
unique(event_id, route_key)
```

用途：

- Dashboard 顯示 route audit。
- 排查為什麼某事件沒有推 Pushover。
- 排查為什麼某事件沒有進公共 Channel。
- 後續支持 route rule editor。

## 11. Queue Writer

`event-router` 不發送任何外部 request，只寫下游 queue。

Private routes：

```text
private.telegram
  → alerts(channel='telegram')

private.pushover
  → alerts(channel='pushover')
```

Public routes：

```text
public.telegram_channel
  → public_outbox(publish_status_telegram='pending')

public.website
  → public_outbox(publish_status_web='pending')

public.x
  → public_outbox(publish_status_x='pending')
```

目前 `public_outbox` 使用 `event_id` unique，足以支援同一 event 的多 public outlet status。若後續有多個 Telegram Channel 或多個公共網站 destination，再擴展為：

```text
public_posts
public_deliveries
```

或在 `public_deliveries` 加入：

```text
platform
channel_key
unique(public_outbox_id, platform, channel_key)
```

## 12. 與下游服務的邊界

### 12.1 alert-dispatcher

`alert-dispatcher` 只負責：

- claim `alerts` pending / retry rows。
- 呼叫 Telegram Bot API / Pushover API。
- 寫回 delivery status。

它不再掃描 `events` 建立 alert decision。

### 12.2 telegram-channel-publisher

`telegram-channel-publisher` 只負責：

- claim `public_outbox` Telegram pending / retry rows。
- 根據 Telegram API 做 HTML escape、link rendering、parse fallback。
- 呼叫 Telegram Bot API。
- 寫回 Telegram delivery status。

它不判斷事件是否重要，也不讀 raw item 原文補內容。

### 12.3 x-publisher

`x-publisher` 只負責：

- claim X pending / retry rows。
- 套用 X API 限制與字數限制。
- 呼叫 X API。
- 寫回 X delivery status。

它不使用 AI 改寫，不做 public-safe 判斷。

## 13. 技術棧

| 類別 | 選型 | 說明 |
| --- | --- | --- |
| Language | Python 3.12+ | 與其他 backend services 一致 |
| Database | PostgreSQL 16+ | 讀 `events`，寫 `alerts` / `public_outbox` / `event_route_decisions` |
| DB driver | psycopg 3 | row locking、JSONB、array、upsert |
| Config | pydantic-settings | env 管理 |
| Validation | pydantic | route payload schema |
| Logging | standard logging / structlog | structured route decision logs |
| Packaging | uv | dependency 管理 |
| Container | Docker | HomeLab Compose 部署 |

## 14. V1 實作順序

1. 新增 `services/event-router` skeleton。
2. 新增 `event_route_decisions` migration。
3. 從 `alert-dispatcher` 搬出 private notification policy 與 alert decision writer。
4. 在 `event-router` 中建立：
   - private route policy。
   - public route policy。
   - `alerts` writer。
   - `public_outbox` writer。
   - route audit writer。
5. `alert-dispatcher` 改為只 claim / deliver `alerts`。
6. `telegram-channel-publisher` 繼續只讀 `public_outbox` 發送。
7. 更新 Compose / Makefile / tests。

## 15. 驗收標準

- 新 event 由 `event-router` 建立 route decisions。
- `private.telegram` 可寫入 `alerts` 並由 `alert-dispatcher` 發送。
- `private.pushover` 可依 source policy 與 route score 降噪。
- `public.telegram_channel` 可寫入 `public_outbox`。
- `telegram-channel-publisher` 可從 `public_outbox` 發送公共 Channel 訊息。
- Publisher 不需要讀 `events` 以外的語義資料，也不需要呼叫 AI。
- Dashboard 後續可查到每個 event 的 route decision 與 skipped reason。
