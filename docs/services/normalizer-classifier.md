# normalizer-classifier 功能需求

## 1. 服務定位

`normalizer-classifier` 是 V1 新聞消息層的處理核心，負責讀取 `raw_items`，完成文字預處理、低價值消息過濾、重複合併、模型路由、相關度判斷、事件生成與結果回寫 DB。

此服務是 collector 與 event-router 之間的語義處理層。它可以使用規則、本地 8B model、雲端 small model，或備選整合 Claude Code Agent SDK 提供高階模型能力，但不得輸出交易方向或自動交易建議。

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
- 觸發 `event_created`，交由 `event-router` 決定出口。

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
| Database | PostgreSQL 16+ | 讀寫 processing、raw item translation、events、event claims |
| DB driver | psycopg 3 | 支援 task locking |
| Text cleanup | regex / trafilatura 可選 | V1 以輕量清洗為主 |
| Language detection | source metadata + lightweight script detection | V1 先用來源設定與簡單 script fallback |
| Similarity | rapidfuzz / pg_trgm | 近似重複檢測，V1 先保留依賴與 DB index |
| Local model | OpenAI-compatible local endpoint | local 8B model route，可由 HomeLab 另一台 server 提供 |
| Cloud model | OpenAI-compatible API | cloud small model route，例如 GPT 5.5 mini 類模型 |
| OpenRouter translation-summary model | OpenRouter OpenAI-compatible API | 雙語摘要與全文翻譯，可測試 free / cheap models |
| Agent SDK | Claude Code Agent SDK，備選 | 高階模型能力，非 V1 必需依賴 |
| Schema validation | pydantic | 驗證模型 JSON output |
| Token usage | tiktoken | OpenAI 官方 tokenizer library；provider 未回 usage 時用於估算 token |
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
- `raw_items.summary_zh` / `raw_items.summary_en`，translation-summary layer 回寫雙語摘要，讓 Dashboard 可在 raw item 層直接顯示已處理消息摘要。
- `raw_items.full_translation_zh` / `raw_items.full_translation_en`，translation-summary layer 回寫雙語全文翻譯，供 raw item detail 閱讀。
- `raw_items.translation_status` 與 translation model metadata。
- `raw_item_processing` / `processed_items`。
- `events`。
- `event_claims`，V1 可簡化。
- `ai_model_calls`，保存 Layer 1 / Layer 2 的 token usage、model route、latency 與估算成本。
- `event_created` notification，供 `event-router` 消費。

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
  ├── Layer 2 classification-reasoning
  │     - input: source metadata + original text_clean/text_raw only
  │     - output: relevance, event_type, claim_direction, event fields
  │     - write processing result / create event / notify event-router
  ↓
  Layer 1 translation-summary, best-effort after classification
        - input: original text only
        - output: summary_zh, summary_en, full_translation_zh, full_translation_en
        - write raw_items translation fields
```

Layer 1 不參與優先級、相關度、claim direction 或 severity 判斷。Layer 2 不使用 Layer 1 的翻譯結果作為 evidence，避免低成本翻譯模型的錯譯影響事件判斷。

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
| `openrouter_free` | 摘要、翻譯、低風險輔助任務 | OpenRouter free / cheap models；不作 V1 主分類 |
| `claude_code_agent` | 後續需要高階模型能力或工具型推理 | 備選 route，不阻塞 V1 |

目前骨架已實作 `local_8b` 與 `cloud_small` 兩種 OpenAI-compatible `/chat/completions` route；兩者都使用相同的 JSON schema。`claude_code_agent` 保留在文件與部署設定中，尚未接入 runtime。

V1 決策：

- `gpt-5.4-mini` 是預設分類模型。
- OpenRouter free / cheap models、local LLM 與 `gpt-5.4-nano` 只用於 summary / translation / 輔助預處理。
- 不讓 OpenRouter free model、local LLM 或 nano model 單獨決定 `is_relevant`、`relevance_score`、`claim_direction` 或 `severity`。
- 若 cloud model 不可用，local route 可以暫時保留事件候選，但應標記為較低信心或等待 cloud retry。

V1 runtime 支援兩個 AI layer：

```text
Layer 1: translation-summary
  primary: openai/gpt-oss-20b:free
  fallback: openai/gpt-oss-20b
  output:
    raw_items.summary_zh / summary_en
    raw_items.full_translation_zh / full_translation_en
    raw_items.content_category / topic_tags / mentioned_actors

Layer 2: classification-reasoning
  basic: gpt-5.4-mini
  advanced: reserved for Claude Code Agent SDK / stronger model
```

Layer 1 使用 OpenRouter OpenAI-compatible API。預設先呼叫 `openai/gpt-oss-20b:free`；若 free route 429、timeout、invalid JSON 或其他 transient failure，且 `TRANSLATION_PAID_FALLBACK_ENABLED=true`，則 fallback 到 `openai/gpt-oss-20b`。Paid fallback 在 development 也預設開啟，但 `make dev` 會提供小的 translation budget 避免 backfill 時無限制消耗。

Layer 1 單次 API call 直接產生四項：

```json
{
  "summary_zh": "繁體中文摘要",
  "summary_en": "English summary",
  "full_translation_zh": "繁體中文全文翻譯",
  "full_translation_en": "English full translation",
  "content_category": "diplomacy",
  "topic_tags": ["iran", "nuclear", "sanctions"],
  "mentioned_actors": ["Iran", "United States", "State Department"],
  "detected_language": "fa",
  "notes": null
}
```

`content_category`、`topic_tags` 與 `mentioned_actors` 只用於 Timeline 檢索與資訊分類，不代表交易相關性、通知優先級或事件嚴重度。Layer 1 不輸出 `severity`、`relevance_score` 或 `should_alert`。

Taxonomy 規則：

- `content_category` 是 controlled category，Layer 1 prompt 會帶入 DB 中啟用的 `content_categories`，模型必須優先從這些 keys 選擇；若都不適合，使用 `other`。
- `topic_tags` 是 semi-controlled tags，Layer 1 會看到一批 known tags，但可以輸出新的短 tag。
- normalizer 回寫前會對 tags 做 lowercase、slug normalization、alias mapping 與去重。
- normalized tags 會自動 upsert 到 `tags`，並寫入 `raw_item_tags` 關聯；`raw_items.topic_tags` 保留作為 Timeline 查詢快取。
- `mentioned_actors` V1 仍保留在 `raw_items.mentioned_actors`，不併入 tags，避免 topic 與 entity 混淆。

Layer 2 只讀 `source` metadata、`text_clean` / `text_raw` 原文、rule prefilter 結果。它不讀 `summary_zh`、`summary_en` 或 full translation。

## 10.1 AI Usage Tracking

每次 AI API call 都應寫入 `ai_model_calls`：

| Layer | `ai_layer` | `request_kind` | 主要模型 |
| --- | --- | --- | --- |
| Layer 1 | `translation_summary` | `translate_summary` | `openai/gpt-oss-20b:free`，fallback `openai/gpt-oss-20b` |
| Layer 2 | `classification_reasoning` | `classify_raw_item` | `gpt-5.4-mini` |

Token 來源：

1. 優先使用 OpenAI-compatible response 的 `usage.prompt_tokens`、`usage.completion_tokens`、`usage.total_tokens`。
2. 若 provider 未回 usage，使用 `tiktoken` 估算 input / output token，並在 `usage_json.estimated = true` 標記。
3. 成本使用內建 pricing table 估算：
   - `gpt-5.4-mini`: input `$0.75/M`，output `$4.50/M`
   - `openai/gpt-oss-20b`: input `$0.029/M`，output `$0.14/M`
   - `openai/gpt-oss-20b:free`: `$0`

`request_hash` 用於排查重複 call，不保存完整 prompt。

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
STALE_TASK_TIMEOUT_SECONDS=900
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
AUXILIARY_MODEL_ENABLED=false
AUXILIARY_MODEL_ROUTE=disabled
OPENROUTER_MODEL_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL_API_KEY=...
OPENROUTER_MODEL_NAME=...
OPENROUTER_MODEL_RESPONSE_FORMAT=json_object
OPENROUTER_MODEL_REASONING_EFFORT=
OPENROUTER_HTTP_REFERER=
OPENROUTER_APP_TITLE=XAUUSD Event Radar
TRANSLATION_MODEL_ENABLED=true
TRANSLATION_MODEL_BASE_URL=https://openrouter.ai/api/v1
TRANSLATION_MODEL_API_KEY=
TRANSLATION_PRIMARY_MODEL_NAME=openai/gpt-oss-20b:free
TRANSLATION_FALLBACK_MODEL_NAME=openai/gpt-oss-20b
TRANSLATION_PAID_FALLBACK_ENABLED=true
TRANSLATION_MODEL_RESPONSE_FORMAT=none
TRANSLATION_MODEL_REASONING_EFFORT=
TRANSLATION_HTTP_REFERER=
TRANSLATION_APP_TITLE=XAUUSD Event Radar
TRANSLATION_DEFAULT_MAX_CHARS=20000
TRANSLATION_HIGH_PRIORITY_MAX_CHARS=100000
TRANSLATION_SINGLE_CALL_MAX_CHARS=100000
MAX_CLASSIFICATION_CALLS_PER_RUN=0
MAX_TRANSLATION_CALLS_PER_RUN=0
MAX_TRANSLATION_PAID_FALLBACK_CALLS_PER_RUN=0
CLAUDE_CODE_AGENT_ENABLED=false
CLAUDE_CODE_AGENT_MODEL=...
MODEL_TIMEOUT_SECONDS=30
MAX_MODEL_CALLS_PER_RUN=0
RELEVANCE_THRESHOLD_EVENT=70
RELEVANCE_THRESHOLD_PUSHOVER=85
LOG_LEVEL=INFO
```

`LOCAL_MODEL_BASE_URL`、`CLOUD_MODEL_BASE_URL` 與 `OPENROUTER_MODEL_BASE_URL` 都應指向 OpenAI-compatible `/v1` base URL；service 會呼叫 `{BASE_URL}/chat/completions`。若 local endpoint 不需要 key，`LOCAL_MODEL_API_KEY` 可留空。

`OPENROUTER_MODEL_BASE_URL` 預設為 `https://openrouter.ai/api/v1`。OpenRouter 建議帶上 `HTTP-Referer` 與 `X-Title`，因此可透過 `OPENROUTER_HTTP_REFERER` / `TRANSLATION_HTTP_REFERER` 與 `OPENROUTER_APP_TITLE` / `TRANSLATION_APP_TITLE` 設定。若只想測試模型品質，可以先在 OpenRouter UI 或 curl 中使用 [OpenRouter 測試 Prompt](/Users/lukesun/Projects/ongoing/xauusd-trading-monitor/docs/model-evaluation-openrouter.md)。

`*_MODEL_RESPONSE_FORMAT` 支援：

- `none`：不送 `response_format`，適合多數 Ollama OpenAI-compatible endpoint。
- `json_object`：OpenAI JSON mode。
- `json_schema`：LM Studio structured output。
- `text`：明確要求 text mode。

`*_MODEL_REASONING_EFFORT` 可留空；若本地 OpenAI-compatible server 支援，可設為 `none`。目前 Ollama + Qwen thinking model 在 `reasoning_effort=none` 下可避免大量 reasoning token，延遲明顯下降。

`MAX_MODEL_CALLS_PER_RUN` 是開發環境成本保護閥。`0` 表示不限制；設定為 `20` 這類小數字時，worker 本次啟動最多只會對模型發出 20 次分類請求。達到上限後不再 claim 新任務，已進入處理中的任務若遇到上限會回到 `retry` 並延後一小時。這適合 DB reset 後 collector 自動 backfill 大量消息但仍想避免 paid cloud model 無限制消耗。

生產環境可用 Docker Compose `--scale normalizer-classifier=N` 啟動多個 instance。V1 預設 `NORMALIZER_REPLICAS=2`、`WORKER_CONCURRENCY=2`，總併發約 4。`claim_next_task` 使用 `FOR UPDATE SKIP LOCKED`，同一筆 `raw_item_processing` task 不會被多個 worker 同時 claim。

`normalizer-classifier` 需要使用 PostgreSQL connection pool，而不是讓所有 worker coroutine 共用同一條 `AsyncConnection`。每個 DB method 會從 pool 取得 connection 並在獨立 transaction 中執行，避免不同 worker 的 `commit` / `rollback` 互相影響，也讓 `FOR UPDATE SKIP LOCKED` 能真正支援併發 claim。

Pool 設定：

- local/dev service env 使用 `DB_POOL_MIN_SIZE` / `DB_POOL_MAX_SIZE`。
- production compose 使用 `NORMALIZER_DB_POOL_MIN_SIZE` / `NORMALIZER_DB_POOL_MAX_SIZE`，再映射給 container。
- `DB_POOL_MAX_SIZE=0` 表示依 `WORKER_CONCURRENCY` 自動推導，預設為 `max(WORKER_CONCURRENCY + 2, DB_POOL_MIN_SIZE, 4)`。
- 每個 container 都有自己的 pool；總連線數約為 `NORMALIZER_REPLICAS * DB_POOL_MAX_SIZE`，調高 replicas 前需要確認 PostgreSQL `max_connections`。

`STALE_TASK_TIMEOUT_SECONDS` 用於 worker crash recovery。若 task 長時間停在 `running` 且 `locked_at` 超過門檻，下一次 claim 前會恢復為 `retry`，避免 backlog 永久卡住。

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
