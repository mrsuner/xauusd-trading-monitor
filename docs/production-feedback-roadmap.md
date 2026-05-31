# Production Feedback Roadmap

## 1. 文件目的

本文整理 HomeLab 首次上線後觀察到的三個優先問題，作為接下來逐項實作的工作記憶：

- 多消息源導致 API call 與通知量快速上升。
- AI 使用成本需要可觀測，包含 input token、output token、model、provider 與 route。
- 消息源需要在 Dashboard 中新增、刪除、停用與測試。

本文不替代既有服務文檔，而是補充 V1+ 的產品與工程規劃。實作時仍應分別更新：

- `docs/services/normalizer-classifier.md`
- `docs/services/alert-dispatcher.md`
- `docs/services/dashboard-api.md`
- `docs/services/dashboard-web.md`
- `docs/database-schema.md`

## 2. 優先級

| 項目 | 優先級 | 原因 |
| --- | --- | --- |
| 通知降噪與 source-aware alert policy | P0 | 直接影響使用體驗，避免 Telegram / Pushover 被噪音淹沒 |
| AI token / model usage 統計 | P0 | 已使用 paid cloud model，需要盡快建立成本可觀測性 |
| Source management | P1 | 目前新增 source 仍偏工程操作，後續需要 Dashboard 管理 |

## 3. 通知降噪規劃

### 3.1 問題

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

新增 model pricing config：

```text
AI_PRICING_CONFIG_PATH=infra/model-pricing.json
```

範例：

```json
{
  "openrouter:openai/gpt-oss-20b": {
    "input_per_1m_usd": 0.0,
    "output_per_1m_usd": 0.0
  },
  "openai_compatible:gpt-5.4-mini": {
    "input_per_1m_usd": null,
    "output_per_1m_usd": null
  }
}
```

若價格未知，`estimated_cost_usd` 可留空，但 token 必須記錄。

### 4.5 Dashboard 統計頁

`dashboard-api` 後續新增：

```text
GET /stats/ai-usage
GET /stats/ai-usage/by-model
GET /stats/ai-usage/by-source
GET /stats/ai-usage/by-layer
```

`dashboard-web` 後續新增 AI Usage view：

- 今日 / 24h / 7d token。
- 按 model 分組。
- 按 source 分組。
- 按 AI layer 分組。
- Error rate / latency p50 / p95。
- Backfill 導致的 call 可單獨標記。

## 5. Source Management

### 5.1 問題

目前 source registry 已在 DB 中，但管理仍偏 seed / migration / SQL 操作。後續需要從 Dashboard 完成：

- 新增 Telegram channel。
- 新增 RSS / HTML polling source。
- 停用 noisy source。
- 修改 priority、reliability、translation policy、alert policy。
- 測試 source 是否可讀。

### 5.2 Dashboard API endpoints

建議把 `dashboard-api` 從 read-only 擴展為受 token 保護的管理 API：

```text
GET /sources
GET /sources/{source_id}
POST /sources
PATCH /sources/{source_id}
DELETE /sources/{source_id}
POST /sources/{source_id}/enable
POST /sources/{source_id}/disable
POST /sources/{source_id}/test
POST /sources/{source_id}/backfill
```

刪除策略：

- V1 不做 hard delete。
- `DELETE /sources/{source_id}` 實際執行 soft delete 或 `enabled=false`。
- 保留歷史 `raw_items`、`events` 與 `alerts` 的外鍵語意。

### 5.3 Source test 行為

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

### 5.4 Dashboard Web views

新增 `Sources` 頁面：

- Filter：source type、priority、enabled、source group、official level。
- 列表：name、handle/url、priority、reliability、alert policy、translation policy、health。
- Actions：enable、disable、edit、test、backfill。
- Edit drawer / modal：修改 source metadata。
- Create source flow：選擇 Telegram / RSS / HTML polling 後填寫必要欄位。

### 5.5 權限與安全

V1 仍為單使用者 HomeLab 工具，先使用 `DASHBOARD_API_TOKEN`。但 source management 是寫入能力，需加強：

- 所有 write endpoint 必須要求 API token。
- request body 使用 pydantic schema 驗證。
- 不允許透過 UI 修改 secret env。
- test endpoint 需要 timeout。
- backfill endpoint 需要限制時間窗口與數量。

## 6. 建議實作順序

### Phase 1: 通知降噪

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

- 新增 `ai_model_calls` migration。
- 在 Layer 1 / Layer 2 client wrapper 中記錄 usage。
- 記錄 model、provider、route、latency、success/error。
- 新增 dashboard API stats endpoint。
- 新增 Processing / AI Usage 顯示。

驗收：

- 可按日期、model、source、AI layer 查看 token 使用量。
- provider 沒有 usage 時也能看到 request count、latency 與估算標記。

### Phase 3: Source management API

- 新增 `dashboard-api` write endpoints。
- 加入 source validation / test。
- soft delete / enable / disable。
- 支援小範圍 backfill。

驗收：

- 不改 SQL 即可停用 noisy source。
- 可新增 Telegram / RSS source 並測試。

### Phase 4: Source management UI

- 新增 `Sources` 頁面。
- 支援 create/edit/disable/test/backfill。
- 在 Timeline / Processing filter 中使用 source metadata。

驗收：

- Dashboard 可完成日常 source registry 維護。
- 修改 source policy 後 collector / dispatcher 可在短時間內生效。

## 7. 開放問題

- `alert_score` 是否應保存到 `alerts` 表，方便後續 audit？建議保存。
- Pushover allowlist 放在 source 欄位還是全局 policy config？V1 建議 source 欄位，便於 Dashboard 管理。
- AI token usage 是否需要保存 prompt hash？建議保存 hash，不保存完整 prompt，避免資料量與隱私問題。
- Source management 的 `DELETE` 是否命名為 `archive` 更清楚？API 可用 `DELETE`，UI 顯示為 Disable / Archive。
- Backfill 是否需要單獨標記到 `raw_item_processing`？建議新增 `ingest_mode` 或在 `raw_json` / processing metadata 保存 `backfill=true`。
