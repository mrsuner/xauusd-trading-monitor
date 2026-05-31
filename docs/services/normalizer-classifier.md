# normalizer-classifier 功能需求

## 1. 服務定位

`normalizer-classifier` 是 V1 新聞消息層的處理核心，負責讀取 `raw_items`，完成文字預處理、低價值消息過濾、重複合併、模型路由、相關度判斷、事件生成與結果回寫 DB。

此服務是 collector 與 alert-dispatcher 之間的邏輯層。它可以使用規則、本地 8B model、雲端 small model，或備選整合 Claude Code Agent SDK 提供高階模型能力，但不得輸出交易方向或自動交易建議。

## 2. V1 目標

- 從 processing table 或 `raw_item_created` notification 取得待處理 `raw_item_id`。
- 讀取 `raw_items` 與對應 `sources` metadata。
- 清洗文字與標準化欄位。
- 語言辨識。
- 使用關鍵字、來源權重與規則做初篩。
- 過濾低價值、重複與近似重複消息。
- 對通過初篩的消息呼叫 local 8B model 或 cloud small model。
- 取得 JSON-friendly 模型輸出。
- 回寫 processing result。
- 對高相關消息建立 `events`。
- 可選建立簡化 `event_claims`。
- 觸發 `event_created` 或 alert processing task。

## 3. 非目標

V1 不包含：

- 自動交易。
- 交易方向建議。
- 完整 claim graph。
- 複雜跨來源事件鏈推理。
- 長時間事件生命週期管理。
- 行情資料參與分級。
- 多模型投票。
- 大模型深度分析報告。

## 4. 技術棧

| 類別 | 選型 | 說明 |
| --- | --- | --- |
| Language | Python 3.12+ | V1 主語言 |
| Database | PostgreSQL 16+ | 讀寫 processing、events、alerts |
| DB driver | psycopg 3 | 支援 task locking |
| Text cleanup | regex / trafilatura 可選 | V1 以輕量清洗為主 |
| Language detection | source metadata + lightweight script detection | V1 先用來源設定與簡單 script fallback |
| Similarity | rapidfuzz / pg_trgm | 近似重複檢測，V1 先保留依賴與 DB index |
| Local model | OpenAI-compatible local endpoint | local 8B model route，可由 HomeLab 另一台 server 提供 |
| Cloud model | OpenAI-compatible API | cloud small model route，例如 GPT 5.5 mini 類模型 |
| Agent SDK | Claude Code Agent SDK，備選 | 高階模型能力，非 V1 必需依賴 |
| Schema validation | pydantic | 驗證模型 JSON output |
| Logging | structlog / standard logging | structured logs |
| Packaging | uv | dependency 管理 |
| Container | Docker | HomeLab 部署 |

Go 可作為後續備選，但 V1 建議 Python，因為文字處理與模型 SDK 生態較直接。

## 5. 輸入與輸出

輸入：

- `raw_items`
- `sources`
- `raw_item_processing` pending tasks，或 `raw_item_created` notification

輸出：

- `raw_items.text_clean`，如果 collector 未清洗或需要補齊。
- `raw_item_processing` / `processed_items`。
- `events`。
- `event_claims`，V1 可簡化。
- `event_created` notification 或 alert processing task。

## 6. Processing Table

V1 建議使用 `raw_item_processing` 作為可靠處理狀態。

欄位建議：

```text
id
raw_item_id
stage                   normalize / classify / event_create / completed
status                  pending / running / completed / skipped / failed / retry
is_relevant
relevance_score
filter_reason
model_provider
model_name
model_output_json
attempt_count
next_retry_at
locked_by
locked_at
error_message
created_at
updated_at
```

處理 worker 需要支援 row locking：

```sql
select ...
for update skip locked
```

## 7. 資料流

```text
raw_item_processing pending
  ↓
load raw_item + source
  ↓
normalize text
  ↓
rule prefilter
  ↓
dedupe / near-dedupe
  ↓
model relevance scoring
  ↓
write processing result
  ↓
create event if relevant
  ↓
notify alert-dispatcher
```

## 8. 預處理規則

文字清洗：

- 移除多餘空白。
- 正規化 URL。
- 保留原文，不破壞 `text_raw`。
- 將清洗結果寫入 `text_clean` 或 processing result。

語言辨識：

- 優先使用 `sources.language`。
- 若 source language 為 unknown，使用 detector。
- 支援 `en`、`fa`、`he`、`ar`，以及 fallback `unknown`。

低價值過濾：

- 空內容。
- 純圖片無文字。
- 純廣告。
- 與 XAUUSD 雷達完全無關的一般新聞。
- 明顯重複轉發。

## 9. 關鍵字初篩

V1 初篩應結合 source priority 與 keyword。

高價值主題：

- Trump / Truth Social / sanctions / deal / no deal
- Iran / nuclear / enrichment / uranium
- IRGC / Sepah / Revolutionary Guards
- Khamenei / Supreme Leader
- Israel / IDF / strike / missile / drone
- CENTCOM / vessel / Strait of Hormuz / Red Sea
- Fed / Powell / rate cuts / inflation / restrictive
- Treasury / OFAC / sanctions / oil exports

規則原則：

- P0 官方 / 半官方 source 可降低 keyword 門檻。
- OSINT / aggregator source 需要更高 keyword 門檻。
- market squawk source 需要保留 Fed、Trump、Iran、oil、gold、XAUUSD 相關內容。

## 10. 模型路由

V1 支援以下模型路徑：

| Route | 條件 | 說明 |
| --- | --- | --- |
| `cloud_small` | V1 事件分類預設路徑 | 使用 `gpt-5.4-mini`，負責相關度、claim direction、impact channel、event severity input |
| `local_8b` | 摘要、翻譯、低風險輔助任務 | 成本低，但不作 V1 最終相關度與分級判斷 |
| `cloud_nano` | 摘要、翻譯、低風險輔助任務 | 例如 `gpt-5.4-nano`，可用於快速 summary / translation，不作 V1 主分類 |
| `claude_code_agent` | 後續需要高階模型能力或工具型推理 | 備選 route，不阻塞 V1 |

目前骨架已實作 `local_8b` 與 `cloud_small` 兩種 OpenAI-compatible `/chat/completions` route；兩者都使用相同的 JSON schema。`claude_code_agent` 保留在文件與部署設定中，尚未接入 runtime。

V1 決策：

- `gpt-5.4-mini` 是預設分類模型。
- local LLM 與 `gpt-5.4-nano` 只用於 summary / translation / 輔助預處理。
- 不讓 local LLM 或 nano model 單獨決定 `is_relevant`、`relevance_score`、`claim_direction` 或 `severity`。
- 若 cloud model 不可用，local route 可以暫時保留事件候選，但應標記為較低信心或等待 cloud retry。

code interface 抽象為：

```text
class ModelClient:
  classify(item, source) -> ClassificationResult
```

所有 route 必須輸出相同 schema，並通過 pydantic validation。Claude Code Agent SDK route 即使提供更強推理能力，也不得繞過 V1 的 JSON schema 與禁止交易指令規則。

## 11. 模型輸出 Schema

模型必須輸出 JSON-friendly 結構：

```json
{
  "is_relevant": true,
  "relevance_score": 82,
  "event_type": "IRAN_NUCLEAR",
  "source_stance": "iran_irgc_adjacent",
  "claim_direction": "deny",
  "claim_text": "Tasnim denies Iran will abandon uranium enrichment.",
  "summary_zh": "Tasnim 否認伊朗將放棄濃縮鈾的說法。",
  "summary_en": "Tasnim denies Iran will abandon uranium enrichment.",
  "actors": ["Iran", "Trump", "IRGC"],
  "xauusd_impact_channel": ["safe_haven", "oil_inflation"],
  "requires_confirmation": true,
  "confidence": 76,
  "reason": "來源與伊朗核談判、Trump 敘事及 IRGC-adjacent 口徑相關。",
  "region": "Middle East",
  "primary_actor": "Iran",
  "secondary_actor": "Trump",
  "market_relevance": "可能影響避險需求與制裁預期。"
}
```

不允許輸出：

- buy / sell
- long / short
- entry
- stop loss
- take profit
- position size

模型輸出必須經 pydantic validation，失敗時進入 retry 或 fallback route。

## 12. Event 建立規則

建立 `events` 的初始條件：

| 條件 | 行為 |
| --- | --- |
| `is_relevant = true` 且 `relevance_score >= 70` | 建立 event |
| `relevance_score >= 85` 且 source P0 / P1 | 建立 high priority event |
| OSINT 單源且未確認 | 建立 B 級或只保存 processed item |
| duplicate / near-duplicate | 合併到近期 event 或 skipped |
| `is_relevant = false` | 不建立 event |

V1 severity 建議：

```text
S: relevance >= 90 and P0/P1 official or semi-official
A: relevance >= 80
B: relevance >= 70
C: archive only
```

severity 由規則與 relevance score 決定，不由模型單獨決定。

## 13. Event Type

V1 event types：

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

`MARKET_MOVE_EXPLAINER` 暫緩到行情層版本。

## 14. 簡化 Claim Handling

V1 可先保存單條 claim：

```text
event_id
source_id
claim_text
claim_direction
stance
confidence
```

完整 claim group、跨來源口徑衝突與事件鏈合併屬於 V2。

## 15. 錯誤處理

| 類型 | 處理方式 |
| --- | --- |
| DB lock timeout | retry |
| malformed raw item | mark skipped，保存原因 |
| language detection failed | fallback `unknown` |
| model timeout | retry，或 fallback route |
| invalid JSON output | retry with stricter prompt，仍失敗則 failed |
| duplicate event | 合併或 skipped |

Retry：

```text
max_attempts = 3
initial_backoff = 10s
max_backoff = 300s
```

## 16. Observability

Metrics：

- pending processing count
- processed count per minute
- skipped count
- model call count
- model latency
- model failure count
- relevance score distribution
- events created per hour
- duplicate / near-duplicate count

Logs：

- `raw_item_id`
- `source_id`
- `stage`
- `model_provider`
- `relevance_score`
- `event_id`
- `error_type`

## 17. 設定項

```text
APP_ENV=development
SERVICE_NAME=normalizer-classifier
DATABASE_URL=postgresql://...
WORKER_CONCURRENCY=4
POLL_INTERVAL_SECONDS=2
MODEL_ROUTE=cloud_small
LOCAL_MODEL_BASE_URL=http://localhost:11434/v1
LOCAL_MODEL_API_KEY=
LOCAL_MODEL_NAME=...
LOCAL_MODEL_RESPONSE_FORMAT=none
LOCAL_MODEL_REASONING_EFFORT=
CLOUD_MODEL_BASE_URL=https://api.openai.com/v1
CLOUD_MODEL_API_KEY=...
CLOUD_MODEL_NAME=gpt-5.4-mini
CLOUD_MODEL_RESPONSE_FORMAT=json_object
CLOUD_MODEL_REASONING_EFFORT=
CLAUDE_CODE_AGENT_ENABLED=false
CLAUDE_CODE_AGENT_MODEL=...
MODEL_TIMEOUT_SECONDS=30
RELEVANCE_THRESHOLD_EVENT=70
RELEVANCE_THRESHOLD_PUSHOVER=85
LOG_LEVEL=INFO
```

`LOCAL_MODEL_BASE_URL` 與 `CLOUD_MODEL_BASE_URL` 都應指向 OpenAI-compatible `/v1` base URL；service 會呼叫 `{BASE_URL}/chat/completions`。若 local endpoint 不需要 key，`LOCAL_MODEL_API_KEY` 可留空。

`*_MODEL_RESPONSE_FORMAT` 支援：

- `none`：不送 `response_format`，適合多數 Ollama OpenAI-compatible endpoint。
- `json_object`：OpenAI JSON mode。
- `json_schema`：LM Studio structured output。
- `text`：明確要求 text mode。

`*_MODEL_REASONING_EFFORT` 可留空；若本地 OpenAI-compatible server 支援，可設為 `none`。目前 Ollama + Qwen thinking model 在 `reasoning_effort=none` 下可避免大量 reasoning token，延遲明顯下降。

## 18. 測試需求

單元測試：

- text cleanup。
- language fallback。
- keyword prefilter。
- model output validation。
- relevance to severity mapping。
- duplicate / near-duplicate detection。

整合測試：

- pending task processing。
- DB row locking。
- local model mock。
- cloud model mock。
- event creation。
- retry and failed state。

## 19. 驗收標準

- 能從 processing table 取得 pending `raw_item_id`。
- 能完成清洗、初篩、模型分類與結果回寫。
- 低相關消息不建立 event。
- 高相關消息建立 event。
- 模型 JSON output 驗證失敗時可 retry 或 fallback。
- duplicate / near-duplicate 不重複建立事件。
- 不輸出交易方向或自動交易建議。

## 20. 目前骨架實作狀態

已完成：

- `normalizer-classifier run` CLI。
- Python 3.12 service package 與 Dockerfile。
- `raw_item_processing` polling worker，使用 `for update skip locked` claim task。
- `raw_items` + `sources` metadata 載入。
- text cleanup、language fallback、keyword prefilter。
- OpenAI-compatible model client。
- pydantic model output validation。
- processing result 回寫。
- relevance threshold 達標時建立 `events`。
- 有 `claim_text` 時建立簡化 `event_claims`。
- model failure retry / failed state。

尚未完成：

- `LISTEN raw_item_created` wake-up，現在先使用 polling。
- local route parse failed 時自動 fallback cloud route。
- 近似重複合併到既有 event。
- Claude Code Agent SDK route。
- metrics endpoint。
