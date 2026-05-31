# 最終目標與 V1 實作範圍

## 1. 文件目的

本文整理 XAUUSD Event Radar 的長期最終目標與目前 V1 實作範圍。

目前 V1 先專注「新聞消息層」閉環，不實作 `mt5-collector`、`market_snapshots` 與行情異動反查。V1 的目標是先把 Telegram / RSS / 官方頁面消息可靠採集、預處理、過濾、評分、通知的主流程跑通，為後續行情層與衝突識別能力打基礎。

V1 database schema 詳見 [Database Schema 設計](./database-schema.md)。

## 2. 最終目標

XAUUSD Event Radar 的最終目標不是自動交易，也不是預測黃金方向，而是在 XAUUSD 劇烈波動或高風險新聞出現時，快速回答：

- 是否存在消息面驅動？
- 消息來自哪一個來源群組或權力系統？
- 來源官方程度與可靠度如何？
- 是否存在相反口徑？
- 是否有官方確認或只是市場聚合 / OSINT 傳聞？
- 這條消息可能透過哪個路徑影響 XAUUSD？
- 是否值得即時通知使用者？

最終系統應把速度不同、立場不同、官方程度不同的消息源，整理成一個可回放、可驗證、可分級的事件系統。

## 3. 最終資料流

長期完整資料流如下：

```text
Telegram / RSS / Official Pages / Market Data
  ↓
Collectors
  ↓
raw_items / market_snapshots
  ↓
Queue or Event Notification
  ↓
normalizer-classifier
  ↓
filtered_items / events / event_claims
  ↓
relevance scoring
  ↓
alert-dispatcher
  ↓
Telegram / Pushover / Dashboard
```

長期版本會包含兩條輸入線：

- 新聞消息層：Telegram、RSS、官方頁面。
- 市場行情層：XAUUSD、DXY、US10Y、US02Y、WTI / Brent、VIX 等。

V1 只做新聞消息層。

## 4. V1 實作範圍

V1 的實作流程收斂為：

```text
Telegram / RSS / Official Pages
  ↓
collector services
  ↓
raw_items
  ↓
event notification / queue / processing table
  ↓
normalizer-classifier
  ↓
filtered_items or processed fields in DB
  ↓
event trigger
  ↓
model relevance scoring
  ↓
alert-dispatcher
  ↓
Telegram / Pushover
```

V1 暫時不接入 MT5，也不要求行情資料參與分級。

## 5. V1 核心原則

### 5.1 先建立新聞閉環

第一階段只要穩定完成以下閉環即可：

1. 採集 Telegram / RSS / 官方頁面消息。
2. 原始資料完整寫入 `raw_items`。
3. 觸發處理事件。
4. `normalizer-classifier` 做預處理與過濾。
5. 過濾後結果回寫 DB。
6. 事件觸發後由模型判斷相關度。
7. 根據相關度、來源優先級與規則決定是否通知。

### 5.2 採集器只做採集

Collector 只負責：

- 拉取或接收資料。
- 標準化來源 metadata。
- 去重。
- 寫入 `raw_items`。
- 更新 source health。
- 觸發後續處理。

Collector 不負責：

- AI 摘要。
- 事件分級。
- 交易相關度判斷。
- 告警發送。
- 交易方向推論。

### 5.3 預處理與相關度判斷分離

V1 中 `normalizer-classifier` 分兩個層次：

第一層是預處理：

- 清洗文字。
- 語言辨識。
- 來源 metadata 補齊。
- 關鍵字初篩。
- 垃圾訊息與低價值內容過濾。
- 重複或近似重複消息合併。

第二層是模型判斷：

- 判斷是否與 XAUUSD 事件雷達相關。
- 判斷主題類型。
- 判斷來源立場與 claim direction。
- 產生短摘要。
- 給出 relevance score。

預處理可以由規則完成，模型只處理通過初篩的消息，以降低成本與延遲。

### 5.4 模型可本地或雲端

V1 允許兩種模型路徑：

| 模型路徑 | 用途 | 適用情境 |
| --- | --- | --- |
| cloud small model | V1 主分類、相關度判斷、claim extraction、impact channel | 使用 `gpt-5.4-mini`，重要來源、高優先級消息 |
| local 8B model | 摘要、翻譯、低成本輔助處理 | HomeLab 可用、低風險任務 |
| cloud nano model | 摘要、翻譯、低成本輔助處理 | 例如 `gpt-5.4-nano`，不作最終分類 |
| OpenRouter free / cheap model | 摘要、翻譯、低風險文字處理 | 可作為 local LLM 之外的穩定外部輔助路徑，不作最終分類 |

V1 預設用 `gpt-5.4-mini` 做最終分類。OpenRouter free / cheap model、local LLM 與 nano model 可降低摘要與翻譯成本，但不應單獨決定 `is_relevant`、`relevance_score`、`claim_direction` 或 severity input。

## 6. V1 服務範圍

| Service | V1 狀態 | 說明 |
| --- | --- | --- |
| `telegram-collector` | 實作 | 使用 Telethon 監聽 Telegram channels，寫入 `raw_items` |
| `rss-collector` | 實作 | 輪詢 RSS / 官方頁面，寫入 `raw_items` |
| `normalizer-classifier` | 實作 | 預處理、過濾、摘要、相關度判斷、回寫 DB |
| `alert-dispatcher` | 實作 | 根據事件與相關度發送 Telegram / Pushover |
| `dashboard-api` | 可選 / 最小實作 | V1 可先只提供 health 與事件查詢 API |
| `dashboard-web` | 可選 / 極簡 | V1 可先做 read-only UI，用於查看 timeline、events、sources、processing 與 alerts |
| `mt5-collector` | 暫緩 | V1 不接行情資料 |

## 7. V1 資料表範圍

### 7.1 V1 必要資料表

| Table | V1 狀態 | 用途 |
| --- | --- | --- |
| `sources` | 實作 | 定義 Telegram / RSS / 官方頁面來源 |
| `raw_items` | 實作 | 保存所有原始消息 |
| `processed_items` 或 `raw_item_processing` | 實作 | 保存預處理狀態、過濾結果、模型輸出 |
| `events` | 實作 | 保存被判定有價值的事件 |
| `event_claims` | 可選 / 簡化 | V1 可先保存單條 claim，完整 claim group 後續強化 |
| `alerts` | 實作 | 保存通知發送紀錄 |
| `source_health` | 實作 | 保存來源與採集器健康狀態 |

### 7.2 V1 暫緩資料表

| Table | 狀態 | 原因 |
| --- | --- | --- |
| `market_snapshots` | 暫緩 | V1 不接 MT5 / market API |
| `market_move_reviews` | 暫緩 | 行情異動反查後續版本再做 |
| `raw_item_versions` | 暫緩 | edited message 歷史版本可後續加入 |

## 8. V1 事件通知 / Queue 設計

V1 對 queue 的要求是簡單、可恢復、容易 debug。

可接受方案：

### 8.1 PostgreSQL processing table

使用資料表保存處理任務，例如 `raw_item_processing`：

```text
id
raw_item_id
stage
status
attempt_count
next_retry_at
locked_by
locked_at
error_message
created_at
updated_at
```

優點：

- PostgreSQL 仍是 source of truth。
- 任務狀態可查詢。
- 容易 retry。
- 適合 V1。

### 8.2 PostgreSQL LISTEN/NOTIFY

在 `raw_items` insert 後觸發：

```text
NOTIFY raw_item_created, payload = raw_item_id
```

優點：

- 延遲低。
- 實作簡單。

限制：

- `NOTIFY` 本身不是可靠 queue。
- consumer 斷線期間可能錯過通知。

建議用法：

```text
processing table 作為可靠狀態
LISTEN/NOTIFY 作為即時喚醒訊號
```

### 8.3 Redis queue

Redis 可作為 V1 備選，但不建議一開始成為唯一任務狀態來源。

若使用 Redis：

- DB 仍保存 `raw_items` 與 processing status。
- Redis 只放 `raw_item_id`。
- consumer 啟動時仍需掃描 DB 中 pending / retry tasks。

## 9. V1 Normalizer / Classifier 輸出

V1 模型輸出應是 JSON-friendly 結構，不輸出交易建議。

建議欄位：

```json
{
  "is_relevant": true,
  "relevance_score": 82,
  "event_type": "IRAN_NUCLEAR",
  "source_stance": "iran_irgc_adjacent",
  "claim_direction": "deny",
  "summary_zh": "Tasnim 否認伊朗將放棄濃縮鈾的說法。",
  "actors": ["Iran", "Trump", "IRGC"],
  "xauusd_impact_channel": ["safe_haven", "oil_inflation"],
  "requires_confirmation": true,
  "confidence": 76,
  "reason": "來源與伊朗核談判、Trump 敘事及 IRGC-adjacent 口徑相關。"
}
```

V1 不允許模型輸出：

- buy
- sell
- long
- short
- entry
- stop loss
- take profit
- position size

## 10. V1 通知決策

V1 通知層根據以下因素決定是否推送：

- `relevance_score`
- `source.priority`
- `source.reliability_score`
- `source.official_level`
- `event_type`
- `requires_confirmation`
- 是否為重複消息
- 是否與近期事件相似

初始規則：

| 條件 | 行為 |
| --- | --- |
| `relevance_score >= 85` 且來源為 P0 / P1 | Telegram + Pushover |
| `relevance_score >= 70` | Telegram |
| `relevance_score < 70` | 只入庫，不推送 |
| OSINT / aggregator 單源消息 | 最多 Telegram，不發 Pushover |
| duplicate / near-duplicate | 合併或忽略 |

V1 仍可保留 S / A / B / C severity，但 severity 應由規則與 relevance score 共同決定，不由模型單獨決定。

## 11. V1 實作項目

### 11.1 採集層

V1 實作：

- `telegram-collector`
- `rss-collector`
- `sources` registry
- `source_health`
- `raw_items`
- dedupe key
- basic retry

V1 暫緩：

- media download
- OCR
- 自動加入 Telegram channels
- 多 Telegram session sharding

### 11.2 預處理層

V1 實作：

- text cleanup
- language detection
- keyword prefilter
- source metadata enrichment
- duplicate / near-duplicate detection
- processing status tracking
- model routing

V1 暫緩：

- 複雜跨來源 claim grouping
- 多事件鏈推理
- 長時間事件追蹤

### 11.3 模型層

V1 實作：

- local 8B model 或 cloud small model 其中一種先跑通。
- JSON output schema。
- relevance score。
- short Chinese summary。
- event type classification。
- claim direction。

V1 暫緩：

- 大模型深度分析。
- 多模型投票。
- 自動交易判斷。
- 大規模 prompt orchestration。

### 11.4 通知層

V1 實作：

- Telegram Bot API notification。
- Pushover notification。
- alert dedupe。
- alert delivery status。

V1 暫緩：

- rich dashboard notification center。
- escalation policy。
- user preference UI。

## 12. V1 暫時跳過項目

以下項目屬於最終目標或後續版本，V1 不實作：

- `mt5-collector`
- `market_snapshots`
- XAUUSD 5m / 15m 行情異動偵測
- 行情先動後反查新聞
- DXY / US10Y / US02Y / WTI / Brent / VIX 採集
- Fed rate probability API
- market move explainer
- dashboard 完整圖表與事件疊加
- RabbitMQ / Kafka
- 完整 claim graph
- media OCR
- automatic trading
- trade recommendation

## 13. 後續版本路線

### V1: News Intelligence Loop

目標：

- 消息採集。
- 原始入庫。
- 預處理。
- 模型相關度判斷。
- 事件生成。
- 通知。

### V2: Claim Conflict Engine

目標：

- 完整 `event_claims`。
- claim group 合併。
- 來源口徑衝突偵測。
- Trump / IRNA / Tasnim / SepahNews / Khamenei 之間的同事件對照。

### V3: Market Context Layer

目標：

- `mt5-collector`。
- `market_snapshots`。
- XAUUSD 異動偵測。
- 行情先動時反查消息。
- market move explainer。

### V4: Dashboard Review System

目標：

- Live Timeline。
- High Impact Events。
- Claim Groups。
- Market Move Review。
- source health UI。
- alert review UI。

## 14. V1 成功標準

V1 成功不以資料源數量或模型複雜度衡量，而以閉環穩定性衡量。

完成標準：

- Telegram / RSS 消息能穩定入庫。
- `raw_items` 去重可靠。
- 每筆新資料能觸發處理任務。
- `normalizer-classifier` 能完成預處理與模型相關度判斷。
- 過濾結果能回寫 DB。
- 高相關度消息能觸發 Telegram / Pushover。
- 低相關度消息只入庫，不打擾使用者。
- 所有處理階段可查詢狀態與錯誤。
- 系統不輸出交易方向與自動交易建議。
