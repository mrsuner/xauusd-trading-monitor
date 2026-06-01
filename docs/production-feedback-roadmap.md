# Production Feedback Roadmap

## 1. 文件目的

本文整理 HomeLab 首次上線後觀察到的優先問題，作為接下來逐項實作的工作記憶：

- 多消息源導致 API call 與通知量快速上升。
- AI 使用成本需要可觀測，包含 input token、output token、model、provider 與 route。
- source 增加後，`normalizer-classifier` 可能處理不完待處理消息，需要多 worker queue 與水平擴展能力。
- Telegram channel 可能出現一組圖片加一則文字，V1 Timeline 需要避免顯示多則空白圖片消息。
- `sources.priority`、`reliability_score`、`latency_score` 只能描述來源本身，不等於單條消息一定有交易價值；P0 source 也會發布日常新聞。
- 消息源需要在 Dashboard 中新增、archive、停用與測試。
- 系統後續需要從個人通知工作台擴展出 public publishing plane，讓去敏後的重要事件可由公共網站、Telegram Channel 與 X 提供給更多訂閱者。

本文不替代既有服務文檔，而是補充 V1+ 的產品與工程規劃。實作時仍應分別更新：

- `docs/services/normalizer-classifier.md`
- `docs/services/event-router.md`
- `docs/services/alert-dispatcher.md`
- `docs/services/dashboard-api.md`
- `docs/services/dashboard-web.md`
- `docs/database-schema.md`

## 2. 優先級

| 項目 | 優先級 | 狀態 | 原因 |
| --- | --- | --- | --- |
| 通知降噪與 source-aware alert policy | P0 | 已完成第一版 | 直接影響使用體驗，避免 Telegram / Pushover 被噪音淹沒 |
| AI token / model usage 統計 | P0 | 已完成第一版 | 已使用 paid cloud model，需要盡快建立成本可觀測性 |
| Normalizer 多 worker queue | P0 | 部分完成 | 已支援 production compose scale 2 個 normalizer instance、PostgreSQL `FOR UPDATE SKIP LOCKED` claim、stale running task recovery；backlog 指標與跨 worker budget guard 待補 |
| Timeline taxonomy filters | P0 | 已完成第一版 | Layer 1 已回寫 category/tags/actors，Timeline 可按分類、主題與角色檢索 |
| Per-item value scoring / Timeline relevance UI | P0 | 部分完成 | Timeline 已顯示 Layer 2 relevance / event state；後續再補 `item_value_score` 與 source metadata 融合 |
| Event routing layer | P0 | 已完成第一版 | `event-router` 已集中建立 `alerts`、`public_outbox` 與 `event_route_decisions`，dispatcher / publisher 收斂為 delivery |
| Timeline 非文本消息降噪 | P1 | 待實作 | Telegram media-only raw item 會在 Timeline 形成多則空消息 |
| Source management | P1 | 部分完成 | Dashboard 已可 create/edit/enable/disable/archive；test/backfill 與 collector reload 尚未完成 |
| Public publishing plane | P2 | 規劃中 | HomeLab 控制公共發布，VPS 只承擔 public API / public website / public DB |

### 2.1 Current Todo List

此清單是 2026-06-01 對照文檔與目前程式狀態後整理出的未完成項目。已完成第一版的 notification policy、AI usage 統計、taxonomy filters、source CRUD 與 HomeLab deployment 不再列入主待辦。

P0：

- Per-item value scoring：在現有 Layer 2 relevance 基礎上，後續加入可解釋的 `item_value_score` / routing decision，融合 AI relevance、event type、actor、keyword、source priority / reliability、routine / commentary / duplicate penalty。
- Normalizer 多 worker queue：支援多個 `normalizer-classifier` instance 並行、stale lock recovery、production compose replicas、backlog / oldest pending age / throughput 指標，以及跨 worker AI budget guard。

P1：

- Source test API / UI：支援 Telegram resolve channel、RSS fetch / parse、HTML polling selector test；Dashboard `Sources` 頁加入 test action。
- Source 小範圍 backfill API / UI：限制時間窗口與數量，避免大量 AI call；Dashboard `Sources` 頁加入 backfill action。
- Collector registry auto-reload：新增 / 修改 / disable / archive source 後，Telegram / RSS collector 不需要重啟即可生效。
- Timeline / Processing 補齊 source metadata filters：目前 Timeline 已有部分 filter，後續需補齊 source metadata；Processing 也應支援更完整 source filter。
- Telegram media-only 降噪收尾：`/raw-items` 已有預設過濾空文本的部分實作，但仍需補測試、確認 photo / video / document 無 caption 不顯示，並更新文檔狀態。

P2 / 技術債：

- `normalizer-classifier` 改用 `LISTEN raw_item_created` wake-up；目前仍使用 polling。
- local route parse failed 時自動 fallback cloud route。
- 近似重複合併到既有 event。
- Claude Code Agent SDK route。
- normalizer metrics endpoint。

後續大版本：

- V2 Claim Conflict Engine：完整 claim group、跨來源口徑衝突偵測。
- V3 Market Context Layer：`mt5-collector`、`market_snapshots`、XAUUSD 異動偵測、行情先動反查消息、market move explainer。
- Public Publishing Plane：公共網站、public ingest API、`event-router`、`public_outbox`、`public-syncer`、Telegram Channel publisher 與 X publisher。
- Dashboard review system：Claim Groups 專頁、Market Move Review、行情 overlay、WebSocket / SSE、Replay mode、User preferences、Alert rule editor。

### 2.2 Timeline Relevance UI Plan

實作狀態：已完成第一版。此項改善多消息源上線後的閱讀效率，並優先使用既有 `raw_item_processing.relevance_score`，沒有新增模型或大幅修改 queue。

第一階段先不新增 DB 欄位：

- `raw_item_processing.relevance_score` 作為 item-level relevance 的主要分數。
- `raw_item_processing.is_relevant` 作為相關 / 低相關 filter。
- `raw_item_processing.filter_reason` 作為卡片上的 classification reason。
- `events.raw_item_ids` 或 event lookup 作為 `has_event` 判斷。

Dashboard API 已完成：

- `/raw-items` join 最新 `raw_item_processing` row。
- 回傳：
  - `is_relevant`
  - `relevance_score`
  - `filter_reason`
  - `classification_status`
  - `classification_stage`
  - `has_event`
  - `event_id`，若可唯一對應。
- 新增 query filters：
  - `min_relevance_score`
  - `is_relevant`
  - `has_event`
  - `classification_status`
- 保留 `include_empty_text` debug 參數，不影響 Processing 頁排障。

Dashboard Web 已完成：

- Timeline filter bar 加入：
  - `min_relevance_score`
  - `is_relevant`
  - `has_event`
  - `classification_status`
- Timeline card 顯示：
  - source priority badge，維持來源層級概念。
  - relevance score badge，表示單條消息與系統目標的相關性。
  - classification reason / filter reason。
  - has event badge 或 event link。
- 視覺分層：
  - 高 relevance：正常顯示，可稍微加強左側 border 或 badge。
  - 中 relevance：正常顯示。
  - 低 relevance：預設淡化，或只在 `All raw items` / debug mode 顯示。
- Timeline 預設可先維持目前「全部但可過濾」模式；待數據觀察後再改成 `relevant-first timeline`。

驗收標準：

- P0 source 的 routine / social / commentary 類消息不再在視覺上被誤認為高價值。
- 使用者可以透過 `min_relevance_score` 或 `is_relevant` 快速收斂 Timeline。
- 卡片同時顯示 source priority 與 item relevance，避免把來源重要性誤解為消息價值。
- 低 relevance raw item 仍可在 debug / all 模式查到，便於調整 prompt 與 scoring。

## 3. 通知降噪規劃

### 3.1 問題

實作狀態：已完成第一版。`0005_source_alert_policy` 已新增 source-level alert policy 欄位，`alert-dispatcher` 已整合 source-aware score、Pushover allowlist、rate limit / cooldown 與 backfill mode。

V1 上線後，Telegram / RSS sources 的消息密度高。即使 classifier 已經做相關度判斷，仍可能產生過多事件與通知：

- Telegram channel 本身更新頻率高。
- Aggregator / market squawk 會重複轉述同一條消息。
- Pushover 是高干擾渠道，不適合作為所有 A/B 事件出口。
- Backfill 或 database reset 可能造成短時間大量事件與通知。

### 3.2 設計原則

- Telegram 可以承擔較高頻的「事件流」通知。
- Pushover 只承擔重大、可靠、需要立即注意的事件。
- Source metadata 必須參與通知決策，不只看 `events.severity`。
- Aggregator / OSINT 單源消息預設不得觸發 Pushover。
- `alert-dispatcher` 是最後一層保護，即使 classifier 建立 event，也不代表一定要推送。

### 3.3 建議新增 source 欄位

可在 `sources` 增加以下欄位，或先放入 `source_config`，待規則穩定後再實體化：

```text
telegram_alert_enabled boolean default true
pushover_alert_enabled boolean default false
telegram_min_severity text default 'B'
pushover_min_severity text default 'S'
alert_weight smallint default 50
alert_rate_limit_per_hour integer
alert_cooldown_minutes integer
```

欄位含義：

| 欄位 | 說明 |
| --- | --- |
| `telegram_alert_enabled` | 此 source 是否允許 Telegram 通知 |
| `pushover_alert_enabled` | 此 source 是否允許 Pushover 通知 |
| `telegram_min_severity` | Telegram 最低通知等級 |
| `pushover_min_severity` | Pushover 最低通知等級 |
| `alert_weight` | source-level 通知權重，參與最終分數 |
| `alert_rate_limit_per_hour` | 單一 source 每小時最多通知數 |
| `alert_cooldown_minutes` | 同一 source 兩次通知的最小間隔 |

### 3.4 Alert score

建議在 `alert-dispatcher` 中引入 deterministic score：

```text
alert_score =
  event_severity_score
  + relevance_score_weight
  + source_priority_score
  + official_level_score
  + source_alert_weight
  - requires_confirmation_penalty
  - aggregator_penalty
  - duplicate_penalty
  - rate_limit_penalty
```

範例分數：

| 因子 | 分數 |
| --- | --- |
| `severity = S` | +50 |
| `severity = A` | +35 |
| `severity = B` | +15 |
| `source.priority = P0` | +20 |
| `source.priority = P1` | +12 |
| `official_level = official` | +20 |
| `official_level = semi_official` | +12 |
| `source_group in osint_aggregator / market_squawk` | -20 |
| `requires_confirmation = true` | -15 |
| near duplicate | -30 |

Channel threshold：

```text
telegram:
  send if alert_score >= 45

pushover:
  send if alert_score >= 85
  and source.pushover_alert_enabled = true
  and source.official_level in ('official', 'semi_official', 'unofficial_mirror')
  and not single-source aggregator
```

### 3.5 Pushover policy

Pushover V1+ 建議改為明確 allowlist：

| Source group | Pushover 預設 |
| --- | --- |
| `us_trump` | enabled，但要求原始連結與高 severity |
| `us_fed` | enabled |
| `us_military` | enabled |
| `us_diplomacy` | enabled for S/A |
| `us_sanctions` | enabled for S/A |
| `iran_government` | enabled |
| `iran_irgc_adjacent` | enabled only for S |
| `iran_irgc_official` | enabled |
| `iran_supreme_leader` | enabled |
| `israel_military` | enabled |
| `market_squawk` | disabled unless cross-confirmed |
| `osint_aggregator` | disabled unless cross-confirmed |

Telegram 則可以保留更寬鬆策略：

- S/A：正常推送。
- B：只要超過 score threshold 就推送。
- C：不推送。

### 3.6 Backfill / development 保護

新增運行模式：

```text
ALERT_BACKFILL_MODE=skip|telegram_only|normal
ALERT_DRY_RUN=true|false
ALERT_MAX_PER_BOOT=integer
ALERT_MAX_PER_HOUR=integer
PUSHOVER_ENABLED=true|false
TELEGRAM_ALERT_ENABLED=true|false
```

建議預設：

- development：`ALERT_BACKFILL_MODE=skip`、`PUSHOVER_ENABLED=false`。
- production 首次 boot：先用 `ALERT_DRY_RUN=true` 觀察。
- production 穩定後：`ALERT_DRY_RUN=false`，但保留 rate limit。

## 4. AI 使用成本統計

### 4.1 問題

目前 `normalizer-classifier` 會呼叫：

- Layer 1 translation-summary。
- Layer 2 classification-reasoning。

但若缺少 token usage 與模型路由紀錄，運行一段時間後無法回答：

- 每天花了多少 token？
- 哪個 model / provider 成本最高？
- 哪些 source 造成最多 AI call？
- translation-summary 與 classification-reasoning 的成本比例？
- backfill 是否造成異常成本？

### 4.2 建議新增資料表：`ai_model_calls`

實作狀態：已於 `0006_ai_model_calls` migration 與 `normalizer-classifier` model client wrapper 中完成第一版。

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

欄位含義：

| 欄位 | 說明 |
| --- | --- |
| `ai_layer` | `translation_summary` / `classification_reasoning` / `advanced_reasoning` |
| `route_name` | `openrouter_free` / `openrouter_paid` / `cloud_small` / `local_8b` |
| `provider` | `openrouter` / `openai_compatible` / `ollama` |
| `request_kind` | `translate_summary` / `classify_raw_item` / `advanced_event_review` |
| `usage_json` | 保存 provider 原始 usage payload |
| `request_hash` | 用於排查重複 call，不保存完整 prompt |

### 4.3 Token 來源

優先順序：

1. 使用 API response 的 `usage.prompt_tokens`、`usage.completion_tokens`、`usage.total_tokens`。
2. 若 provider 不返回 usage，使用 tokenizer 估算並標記 `usage_json.estimated = true`。
3. 若 local model 無法估算，仍記錄 model、latency、success 與 request kind。

### 4.4 成本估算

V1+ 先使用內建 pricing table：

| Provider / Model | Input / M token | Output / M token |
| --- | --- | --- |
| `openai_compatible:gpt-5.4-mini` | `$0.75` | `$4.50` |
| `openrouter:openai/gpt-oss-20b` | `$0.029` | `$0.14` |
| `openrouter:openai/gpt-oss-20b:free` | `$0` | `$0` |

若價格未知，`estimated_cost_usd` 可留空，但 token 必須記錄。後續可將 pricing table 移到 `infra/model-pricing.json`。

### 4.5 Dashboard 統計頁

`dashboard-api` 已新增：

```text
GET /stats/ai-usage
```

目前 `/stats/ai-usage` 一次回傳 totals、by-model、by-source 與 by-layer。

`dashboard-web` Processing 頁已新增 AI Usage summary：

- 24h token。
- 按 model 分組。
- 按 source 分組。
- 按 AI layer 分組。
- failure count / average latency。
- Backfill 導致的 call 可後續單獨標記。

## 5. Normalizer 多 Worker Queue

### 5.1 問題

HomeLab 運行一段時間後觀察到：當 Telegram / RSS source 數量增加時，`raw_items` 與 `raw_item_processing` pending backlog 會快速上升。即使目前 `normalizer-classifier` 支援單進程內 `WORKER_CONCURRENCY`，整體吞吐仍受限於：

- 單個 service instance 的 CPU / memory。
- 同一進程內 AI API call latency。
- translation-summary 與 classification-reasoning 都消耗 worker 時間。
- paid model budget / rate limit 可能讓任務被 defer。
- database reset / collector backfill 會短時間灌入大量 pending task。

此問題的本質不是單純調大 concurrency，而是需要可靠隊列與可水平擴展的 worker pool。

### 5.2 V1+ 設計方向

保留 PostgreSQL 作為可靠 queue source of truth，先不要引入 RabbitMQ：

```text
raw_items insert
  ↓
raw_item_processing pending
  ↓
multiple normalizer-classifier workers
  ↓ for update skip locked
running / completed / skipped / retry / failed
```

核心原則：

- 多個 `normalizer-classifier` instance 可以同時啟動。
- 每個 instance 使用不同 `worker_id`。
- `claim_next_task` 必須使用 `for update skip locked`，避免重複處理。
- `running` task 需要 stale lock recovery，避免 worker crash 後永遠卡住。
- classification 與 translation 的 budget / rate limit 需要全局或近似全局化，避免多 instance 放大 API 成本。

### 5.3 建議拆分

短期：

- production compose 支援 `normalizer-classifier` 多 replicas 或多 service instance。已完成第一版，使用 `NORMALIZER_REPLICAS=2` 與 `infra/scripts/prod-up.sh`。
- 加入 stale running task recovery。已完成第一版：
  - `locked_at < now() - interval 'N minutes'`
  - 將任務恢復為 `retry`
- Dashboard Processing 增加 queue backlog 指標：
  - pending count
  - running count
  - retry count
  - oldest pending age
  - average processing latency

中期：

- 將 Layer 1 translation-summary 與 Layer 2 classification-reasoning 拆成不同 queue stage：

```text
raw_item_processing
  stage = normalize / classify / translate / completed
```

或拆成兩張 queue：

```text
classification_tasks
translation_tasks
```

拆分後可以：

- 優先處理 classification，先決定是否建立 event / alert。
- 對低 priority source 延後 translation。
- 單獨擴展 translation workers。
- 更精準控制 paid model 使用量。

後期：

- 若 PostgreSQL queue 壓力變大，再評估 RabbitMQ / Redis Streams。
- RabbitMQ 適合需要 ack、retry、dead-letter queue 與多 consumer group 時引入。

### 5.4 風險與注意事項

- 多 worker 會放大 AI API call 速度，必須先有 AI usage 統計與 budget guard。
- 若不做 source-aware priority queue，低價值 source 可能擠壓 P0 source。
- translation full text 對吞吐影響大，可能需要改為低優先級背景任務。
- 開發環境 database reset / backfill 應避免自動消耗大量 paid model call。

### 5.5 驗收標準

- 可以安全啟動多個 `normalizer-classifier` worker instance。
- 同一 `raw_item_processing` task 不會被重複處理。
- worker crash 後 running task 可自動恢復。
- Dashboard 能看到 backlog 與吞吐狀態。
- 增加 worker 數量後 pending backlog 下降，且 AI 成本仍可控。

## 6. Telegram Media / Non-text Raw Items

### 6.1 問題

Telegram channel 常見消息格式是：

```text
photo
photo
photo
caption / text message
```

目前 collector 會把這些 Telegram updates 分別寫入 `raw_items`。若圖片消息沒有文字，normalizer 會跳過或只保存空內容，但 Dashboard Timeline 仍可能顯示多則空白消息，然後再顯示一則真正有內容的文字消息。

V1 不需要立即處理圖片內容，也不需要做 image OCR / vision model。但 Timeline 應避免把 media-only raw item 當作可讀消息展示。

### 6.2 V1 簡化策略

短期：

- Timeline / raw item list 預設不顯示非文本內容：
  - `text_clean`、`summary_zh`、`summary_en`、`text_raw` 都為空時不顯示。
  - 或 `media_type` 是 photo / video / document 且沒有 caption/text 時不顯示。
- 保留 raw item 入庫，不刪除資料。
- Processing 頁可以保留 skipped 記錄，用於排障。

這樣可以降低 UI 噪音，同時不阻斷後續補 media 支援。

### 6.3 後續設計方向

完整處理 Telegram media 需要重新設計資料結構：

- `raw_items.media_type` 只能表示粗略類型，無法完整描述多附件。
- 需要 media attachment table：

```text
raw_item_media
  id
  raw_item_id
  telegram_file_id / media_id
  media_type
  mime_type
  file_name
  width
  height
  file_size
  storage_provider
  storage_key
  thumbnail_storage_key
  created_at
```

- 需要支持 Telegram grouped media / album：

```text
media_group_id
caption_raw_item_id
related_raw_item_ids
```

- 需要決定圖片存儲位置：
  - 本地 volume
  - S3-compatible storage / MinIO
  - 只保存 Telegram file reference，按需下載

### 6.4 後續展示

Dashboard 後續可加入：

- Event detail / raw item detail 中展示縮圖。
- Timeline 只顯示 caption/message，並用 attachment count 表示有圖片。
- Media-only item 不獨立出現在 Timeline，但可在 detail 裡作為附件查看。
- 若後續加入 OCR / vision model，結果應保存為 `media_text_extracted` 或獨立 `raw_item_media_analysis`，避免污染原文。

### 6.5 驗收標準

V1 簡化版：

- Timeline 不再顯示空白圖片 raw item。
- 有 caption / text 的 Telegram 消息仍正常顯示。
- 非文本 raw item 仍保留在 DB，可供後續 media 支援使用。

後續完整版：

- Telegram album 可被合併展示。
- 圖片有可追蹤的 storage metadata。
- Dashboard 可以在 detail view 查看附件。

## 7. Source Management

### 7.1 問題

實作狀態：部分完成。`dashboard-api` 與 `dashboard-web` 已支援 source create / edit / enable / disable / archive，且不提供 hard delete。尚未完成 source test、source backfill 與 collector registry auto-reload。

目前 source registry 已在 DB 中，但管理仍偏 seed / migration / SQL 操作。後續需要從 Dashboard 完成：

- 新增 Telegram channel。已完成。
- 新增 RSS / HTML polling source。已完成 UI / API 層，collector reload 仍待補強。
- 停用 noisy source。已完成。
- Archive retired source。已完成，不 hard delete。
- 修改 priority、reliability、translation policy、alert policy。已完成。
- 測試 source 是否可讀。待實作。

### 7.2 Dashboard API endpoints

建議把 `dashboard-api` 從 read-only 擴展為受 token 保護的管理 API：

```text
GET /sources
GET /sources/{source_id}
POST /sources
PATCH /sources/{source_id}
POST /sources/{source_id}/enable
POST /sources/{source_id}/disable
POST /sources/{source_id}/archive
POST /sources/{source_id}/test
POST /sources/{source_id}/backfill
```

Archive 策略：

- V1 不做 hard delete。
- `POST /sources/{source_id}/archive` 會設定 `enabled=false` 與 `archived_at`。
- 保留歷史 `raw_items`、`events` 與 `alerts` 的外鍵語意。

### 7.3 Source test 行為

Telegram source test：

- 驗證 handle 格式。
- 使用 Telethon resolve channel。
- 回傳 channel title、id、username、access status。
- 可選抓取最近 1-3 條消息，但不入庫。

RSS source test：

- Fetch feed。
- 驗證 HTTP status。
- 驗證 feed parse 結果。
- 回傳 title、latest item、last modified / etag。

HTML polling source test：

- Fetch page。
- 驗證 selector 是否存在。
- 回傳匹配數量與第一筆摘要。

### 7.4 Dashboard Web views

新增 `Sources` 頁面：

- Filter：source type、priority、enabled、source group、official level。
- 列表：name、handle/url、priority、reliability、alert policy、translation policy、health。
- Actions：create、edit、enable、disable、archive 已完成；test、backfill 待實作。
- Edit drawer / modal：修改 source metadata。
- Create source flow：選擇 Telegram / RSS / HTML polling 後填寫必要欄位。
- 可枚舉欄位使用 dropdown，避免自由輸入造成 registry 不一致。

### 7.5 權限與安全

V1 仍為單使用者 HomeLab 工具，先使用 `DASHBOARD_API_TOKEN`。但 source management 是寫入能力，需加強：

- 所有 write endpoint 必須要求 API token。
- request body 使用 pydantic schema 驗證。
- 不允許透過 UI 修改 secret env。
- test endpoint 需要 timeout。
- backfill endpoint 需要限制時間窗口與數量。

## 8. Timeline Taxonomy 與後續 Per-item Value Scoring

### 8.1 問題

`sources.priority`、`sources.reliability_score`、`sources.latency_score` 描述的是來源層級，不是單條消息層級。上線後已觀察到：即使是 P0 / semi-official source，例如 Tasnim News，也會發布大量日常或背景性新聞。這些消息來源可靠，但未必與 XAUUSD、地緣衝突、Fed、制裁、能源或市場異動有直接關係。

典型例子：

```text
在2024年9月20日和2025年3月20日，伊朗社會出現兩種截然不同的反應，為何會如此？本報採訪了大學教授阿米尼博士，探討其背後原因。

Source:
  name: Tasnim News
  official_level: semi_official
  priority: P0
```

這類消息不應因為 source 是 P0 就在 Timeline 視覺上被視為高價值，也不應提升通知權重。Phase 4 先完成較低風險的 Timeline taxonomy：Layer 1 在翻譯摘要時同步輸出內容分類、主題標籤與提及角色，讓使用者可以在 Timeline 做檢索與過濾。真正的 value scoring / alert scoring 仍保留給 Layer 2 與規則系統。

### 8.2 設計原則

- Source priority 是來源權重，不是消息價值。
- Layer 1 taxonomy 只描述內容，不做交易判斷、嚴重度、相關度或通知決策。
- 單條消息的展示與通知應以 `raw_item_processing.relevance_score`、`events.relevance_score`、`event_type`、`claim_direction`、`market_relevance` 等 item-level / event-level 結果為主。
- Source metadata 只作為加權因子，不應覆蓋 AI relevance 與 deterministic keyword / actor scoring。
- P0 source 的低相關消息應能保留在 DB 與 Processing 頁，但 Timeline 預設可以降權、淡化或隱藏。
- UI 應清楚區分：
  - source priority：來源重要性。
  - relevance score：此消息對本系統目標的相關性。
  - alert score：此事件是否值得通知。

### 8.3 已完成：Controlled Categories + Semi-controlled Tags

已新增 `raw_items` 描述型欄位：

```text
content_category
topic_tags
mentioned_actors
```

Layer 1 translation-summary 單次 API call 會回寫：

```json
{
  "summary_zh": "繁體中文摘要",
  "summary_en": "English summary",
  "full_translation_zh": "繁體中文全文翻譯",
  "full_translation_en": "English full translation",
  "content_category": "diplomacy",
  "topic_tags": ["iran", "nuclear", "sanctions"],
  "mentioned_actors": ["Iran", "United States", "State Department"]
}
```

Dashboard API 已支援：

```text
content_category
topic_tag
actor
GET /raw-items/filters
```

Timeline 已支援 category / topic / actor filters，並在 card 顯示 category badge、topic tags 與 mentioned actors。

已新增 taxonomy dictionary：

```text
content_categories  -- controlled category dictionary
tags                -- semi-controlled normalized tag dictionary
raw_item_tags       -- raw item 與 tag 的正規關聯
```

Category 規則：

- `content_category` 必須優先使用啟用的 `content_categories.key`。
- 若模型輸出不在 dictionary，normalizer 回寫為 `other`。
- Timeline category dropdown 讀 `/taxonomy/categories`，不再由前端 hard code。

Tag 規則：

- Layer 1 可輸出新 tags。
- normalizer 做 lowercase、slug normalization、alias mapping、去重與數量限制。
- normalized tag 自動 upsert 到 `tags`，並寫入 `raw_item_tags`。
- Timeline tag dropdown 讀 `/taxonomy/tags`。

### 8.4 後續：Scoring fusion 方向

後續 `normalizer-classifier` 與 `alert-dispatcher` 應採用可解釋的融合分數，而不是只看 source priority：

```text
item_value_score =
  ai_relevance_score
  + event_type_weight
  + actor_weight
  + keyword_weight
  + source_priority_weight
  + source_reliability_weight
  - routine_news_penalty
  - commentary_penalty
  - duplicate_penalty
```

其中：

| 因子 | 說明 |
| --- | --- |
| `ai_relevance_score` | Layer 2 對單條消息與 XAUUSD Event Radar 目標的相關度 |
| `event_type_weight` | Fed、制裁、軍事、核、霍爾木茲、Trump 等高價值類型加權 |
| `actor_weight` | Trump、Fed 官員、CENTCOM、IRGC、最高領袖、IDF 等行動者加權 |
| `source_priority_weight` | P0/P1 source 的來源權重，但只能有限加分 |
| `source_reliability_weight` | 官方/半官方/可信媒體可提高可信度 |
| `routine_news_penalty` | 社會評論、歷史回顧、日常政治新聞、人物訪談等降權 |
| `commentary_penalty` | 分析評論或非即時消息降權 |
| `duplicate_penalty` | 重複轉述或同源重發降權 |

重要限制：

- `source_priority_weight` 不應大到讓低相關 P0 消息變成高價值消息。
- `reliability_score` 應主要影響可信度，不應直接等同交易相關性。
- `latency_score` 只應影響突發消息時效評估，不應讓日常消息提升通知等級。

### 8.5 後續：Timeline Relevance UI 方向

Timeline 應加入 item-level relevance 展示與過濾：

- 新增 filter：
  - `min_relevance_score`
  - `event_type`
  - `is_relevant`
  - `has_event`
  - `source_priority`
  - `source_group`
- 卡片視覺分層：
  - 高 relevance：正常或高亮顯示。
  - 中 relevance：正常顯示但不突出。
  - 低 relevance：預設可折疊、淡化或在「All raw items」模式才顯示。
- 卡片上同時顯示：
  - source priority badge。
  - relevance score / item value score。
  - classification reason / filter reason。
  - 是否已產生 event。
- Timeline 預設視圖建議由「所有 raw items」改為「relevant-first timeline」，保留 Debug / All 模式查看完整採集流。

### 8.6 後續：API / DB 方向

V1 現有 `raw_item_processing.relevance_score` 可先作為 Timeline relevance 的主要來源，不必立即新增欄位。後續若需要更清楚分離概念，可新增：

```text
raw_item_processing.item_value_score
raw_item_processing.routing_decision
raw_item_processing.routine_news_score
raw_item_processing.classification_tags
```

Dashboard API 可先在 Timeline / raw items endpoint join 最新 processing row，回傳：

```text
is_relevant
relevance_score
filter_reason
classification_stage
classification_status
event_id / has_event
```

### 8.7 驗收

- P0 source 的日常消息不會在 Timeline 被誤認為高價值。
- Timeline 可以用 `min_relevance_score` 或 `is_relevant` 過濾低價值消息。
- 卡片同時顯示 source priority 與 item relevance，避免概念混淆。
- 通知策略不會因 source 是 P0 就放大低相關消息。
- Processing / Debug 頁仍能查看被降權或跳過的消息，方便調整 prompt 與 scoring。

## 9. 建議實作順序

### Phase 1: 通知降噪

實作狀態：已於 `0005_source_alert_policy` migration 與 `alert-dispatcher` policy 中完成第一版。

- 調整 schema：source alert policy 欄位。
- 更新 seed source 的 Pushover allowlist。
- 修改 `alert-dispatcher` policy。
- 加入 per-source rate limit。
- 加入 backfill alert mode。
- 更新 alert docs 與測試。

驗收：

- Telegram 通知量下降但仍保留重要事件流。
- Pushover 只在 S 級或高可信 A 級事件發送。
- Backfill 不再造成 Pushover spam。

### Phase 2: AI usage 統計

實作狀態：已完成第一版。

- 新增 `ai_model_calls` migration。
- 在 Layer 1 / Layer 2 client wrapper 中記錄 usage。
- 記錄 model、provider、route、latency、success/error。
- 新增 dashboard API stats endpoint。
- 新增 Processing / AI Usage 顯示。

驗收：

- 可按日期、model、source、AI layer 查看 token 使用量。
- provider 沒有 usage 時也能看到 request count、latency 與估算標記。

### Phase 3: Normalizer 多 worker queue

- [x] 確認 `raw_item_processing` claim query 支援多 instance 競爭。
- [x] 加入 stale lock recovery。
- [x] production compose 支援擴展 `normalizer-classifier` replicas。
- 增加 queue backlog / oldest pending age / throughput 統計。
- 重新檢查 AI budget guard 是否能跨 worker 控制成本。

驗收：

- 多個 worker instance 並行時不重複處理任務。
- pending backlog 可被多 worker 加速消化。
- crash / restart 後任務可恢復。

### Phase 4: Timeline taxonomy filters

- 狀態：已完成 V1 taxonomy 版本與 Phase 4.1 dictionary 版本。
- Layer 1 translation-summary 回寫 `content_category`、`topic_tags`、`mentioned_actors`。
- 新增 controlled `content_categories` 與 semi-controlled `tags` / `raw_item_tags`。
- Dashboard API `/raw-items` 支援 `content_category`、`topic_tag`、`actor` filters。
- Dashboard API `/raw-items/filters` 回傳 dropdown options。
- Dashboard API `/taxonomy/categories` 與 `/taxonomy/tags` 回傳正式 taxonomy options。
- Timeline card 顯示 category、topic tags 與 mentioned actors。

後續獨立處理：

- [x] Timeline / raw items endpoint join 最新 `raw_item_processing` 結果。
- [x] 回傳 `is_relevant`、`relevance_score`、`filter_reason` 與 `has_event`。
- [x] Timeline 新增 `min_relevance_score`、`is_relevant`、`has_event` filters。
- [x] 低 relevance 消息預設淡化或只在 Debug / All 模式顯示。
- 調整 `alert-dispatcher` 權重，避免 source P0 放大低相關消息。

驗收：

- Timeline 可按 category、topic、actor 快速檢索消息。
- P0 source 的日常消息可以透過 `routine` / `social` 等 category 過濾。
- Processing 仍能查到低 relevance 消息與模型判斷原因。

### Phase 5: Timeline 非文本消息降噪

- Dashboard API / web 預設過濾 media-only raw item。
- Timeline card fallback 僅在有 `summary_zh` / `summary_en` / `text_clean` / `text_raw` 時顯示。
- Processing 可保留 media-only skipped item，方便排障。

驗收：

- Telegram 圖片組不再在 Timeline 顯示多則空白消息。
- 帶 caption 的消息仍正常顯示。
- 原始 media-only raw item 不從 DB 刪除。

### Phase 6: Source management API

實作狀態：部分完成。

- [x] 新增 `dashboard-api` write endpoints。
- [x] 加入 pydantic source validation。
- [x] enable / disable。
- [x] archive，不做 hard delete。
- [ ] source test。
- [ ] 支援小範圍 backfill。
- [ ] collector registry auto-reload。

驗收：

- [x] 不改 SQL 即可停用 noisy source。
- [x] 可新增 Telegram / RSS source。
- [ ] 可測試 Telegram / RSS source 是否可讀。
- [ ] 新增 source 後 collector 可不重啟生效。

### Phase 7: Source management UI

實作狀態：部分完成。

- [x] 新增 `Sources` 頁面。
- [x] 支援 create / edit / enable / disable / archive。
- [x] 可枚舉欄位使用 dropdown。
- [x] 顯示 source alert policy、translation policy、health 與 24h activity。
- [ ] test source action。
- [ ] backfill source action。
- [ ] 在 Timeline / Processing filter 中補齊所有 source metadata filter。

驗收：

- [x] Dashboard 可完成日常 source registry 維護。
- [x] 修改 source policy 後 dispatcher 可在下一輪查詢中使用新 policy。
- [ ] 修改 collector source registry 後可在短時間內自動生效。

### Phase 8: Public publishing plane

實作狀態：規劃中。此階段目標是把系統從個人工作台延伸成公共資訊平台，但不走 SaaS 多租戶路線。

部署邊界：

- HomeLab 保留核心資料採集、AI 處理、事件判斷、私人通知與公共發布控制。
- VPS 只部署 `public-api`、`public-web` 與 public database。
- Cloudflare Tunnel 只部署在 VPS 側，用於保護 public website / API，不作為 HomeLab 與 VPS 的內網通道。
- HomeLab 與 VPS 不建立內部網路；HomeLab 只透過 outbound HTTPS push public-safe payload。

HomeLab 新增元件：

- `event-router`：集中根據 `events`、source metadata 與 route policy 建立 `alerts`、`public_outbox` 與 route audit。
- `public_outbox`：保存已去敏、可公開、可重試的事件草稿。`0010_public_outbox` 已完成第一版 schema。
- `public-syncer`：把 `public_outbox` 中可公開的資料同步到 VPS `public-api`。
- `telegram-channel-publisher`：把 public-safe event 發布到公共 Telegram Channel。runtime skeleton 已完成，預設 dry-run 且需透過 `public-publishing` profile 啟動。
- `x-publisher`：把 public-safe event 發布到 X。

VPS 新增元件：

- `public-api`：提供 ingest endpoint 與 public read API。
- `public-web`：公共網站，只讀取 public database。
- `public-postgres`：只保存 public-safe event，不保存 raw item、prompt、私人通知設定或 Telegram session。

安全與資料邊界：

- public payload 必須是摘要與來源連結，不發布完整 `text_raw` 或大段原文。
- public ingest API 需要 HMAC / API key、timestamp / nonce、`idempotency_key`、`schema_version`、rate limit 與 audit log。
- `event-router` 統一管理出口策略；public publisher 與 `alert-dispatcher` 不共用 delivery 狀態，前者面向公開訂閱者，後者面向個人通知。
- aggregator / OSINT 單源消息需要標記未確認，或預設不進入公共發布。

建議實作順序：

1. 定義 public payload schema 與 `public_outbox` migration。已完成第一版。
2. 實作 `event-router`，從 `events` 生成 private alert decisions 與 public-safe content。已完成第一版。
3. 實作 VPS `public-api` ingest，先不做 public website UI。
4. 實作 HomeLab `public-syncer`，支援 retry 與 idempotency。
5. 實作 `public-web` 第一版列表與事件詳情。
6. 實作 Telegram Channel publisher。已完成第一版 runtime skeleton，尚未做真實 Channel 發布驗證。
7. 實作 X publisher。

驗收：

- HomeLab 不開放 inbound port 也能同步公共事件到 VPS。
- VPS public website 只展示去敏後資料。
- 公共網站、Telegram Channel 與 X 可基於同一份 `public_outbox` 內容發布，避免三個出口文案不一致。
- public 發布失敗不影響核心採集、AI 處理與私人通知。

## 10. 開放問題

- `alert_score` 已保存到 `alerts` 表，方便後續 audit。
- Pushover allowlist 放在 source 欄位還是全局 policy config？V1 建議 source 欄位，便於 Dashboard 管理。
- AI token usage 是否需要保存 prompt hash？建議保存 hash，不保存完整 prompt，避免資料量與隱私問題。
- Source management 已採用 `POST /sources/{source_id}/archive`，不提供 `DELETE`。
- Backfill 是否需要單獨標記到 `raw_item_processing`？建議新增 `ingest_mode` 或在 `raw_json` / processing metadata 保存 `backfill=true`。
- Telegram media-only raw item 是否應在 API 層預設過濾，或由 Dashboard Web filter 控制？V1 建議 API 預設過濾，保留 query param 用於 debug。
- 是否需要把 `item_value_score` 與 `relevance_score` 拆開？短期可共用 `relevance_score`，長期建議拆開，避免 source weighting 與模型相關度混在同一欄位。
