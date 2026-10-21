# normalizer-classifier 功能需求

## 1. 服務定位

`normalizer-classifier` 是 V1 新聞消息層的處理核心，負責讀取 `raw_items`，完成文字預處理、低價值消息過濾、重複合併、模型路由、相關度判斷、事件生成與結果回寫 DB。

此服務是 collector 與 event-router 之間的語義處理層。它使用規則初篩與 OpenRouter／Ollama Cloud API 提供模型能力，但不得輸出交易方向或自動交易建議。

## 2. V1 目標

- 從 processing table 或 `raw_item_created` notification 取得待處理 `raw_item_id`。
- 讀取 `raw_items` 與對應 `sources` metadata。
- 清洗文字與標準化欄位。
- 語言辨識。
- 使用關鍵字、來源權重與規則做初篩。
- 過濾低價值、重複與近似重複消息。
- 對通過初篩的消息呼叫選定的雲端 provider。
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
| Cloud model | OpenRouterClient／OllamaCloudClient | 兩個獨立 provider 實作，Layer 1／Layer 2 各自選用 |
| Translation-summary | 雲端 API | 依設定產生多語摘要與全文翻譯 |
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
- `raw_item_translations`，translation-summary layer 以 `(raw_item_id, language)` 回寫多語摘要與全文翻譯，讓 Dashboard / public syncer 讀取語言 row。
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
  │     - output: relevance, event_type, claim_direction, event fields, taxonomy
  │     - write processing result / create event / notify event-router
  ↓
  Layer 1 translation-summary, best-effort after classification
        - input: original text only
        - output: translations[]
        - write raw_item_translations rows
```

Layer 1 不參與優先級、相關度、claim direction 或 severity 判斷。Layer 2 不使用 Layer 1 的翻譯結果作為 evidence，避免低成本翻譯模型的錯譯影響事件判斷。

跨來源語義去重與 claim clustering 不在目前 runtime 中實作。後續設計見 [event-clustering / semantic dedupe 設計草案](./event-clustering.md)，目標是在 `event-router` 之前將不同來源對同一事件的 claim 合併為 canonical event，避免重複廣播。

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

本節描述目前本地程式契約；production 實際啟用狀態仍以部署紀錄為準。

| Layer | 選擇設定 | 預設 |
| --- | --- | --- |
| Layer 2 classification-reasoning | `CLASSIFICATION_MODEL_PROVIDER` | `openrouter`，`CLOUD_MODEL_NAME=openai/gpt-6-luna` |
| Layer 1 translation-summary | `TRANSLATION_MODEL_PROVIDER` | `openrouter`，`TRANSLATION_PRIMARY_MODEL_NAME=openai/gpt-6-luna` |
| Layer 1 fallback | `TRANSLATION_FALLBACK_PROVIDER` | 未設定則沿用 primary provider；預設停用 |

兩個 Layer 均可選 `openrouter` 或 `ollama_cloud`。早期 local LLM route 已退役；`MODEL_ROUTE` 只接受既有 `cloud_small` 標記，不負責 provider 選擇。Layer 2 不新增跨 provider fallback，失敗走既有 processing retry。

實作邊界：

- `model_contracts.py`：worker 使用的 `ModelClient` Protocol、統一錯誤與 retryable 分類。
- `openrouter_client.py`／`ollama_cloud_client.py`：獨立實作，分別處理 request 參數與 response 解析，不繼承共同 provider base class。
- `model_tasks.py`：新聞 prompt、schema、業務驗證及共同結果組裝。
- `model_transport.py`：無 provider 判斷的單次 HTTP 與日誌遮罩；`usage.py`：用量正規化與估算。
- Client 不隱藏重試或切換 provider；worker 每個 attempt 先預留請求額度，再記錄成功／失敗 usage。

Ollama Cloud 直接呼叫 `https://ollama.com/v1/chat/completions`，使用 `OLLAMA_API_KEY`；模型必須使用 Cloud catalog 的明確名稱，不經本機 daemon。官方目前[不支援 Cloud structured outputs](https://docs.ollama.com/capabilities/structured-outputs)，因此 client 將 schema 加入 system prompt，不發送 `response_format`，並以 Pydantic／業務規則驗證最終 `message.content`。空答案、reasoning-only、refusal、截斷、錯誤 JSON 與不合規內容都失敗，不自動修復。這不代表模型端保證 schema，也不代表已完成真實模型品質驗收。

Layer 1 備援只有在 `TRANSLATION_PAID_FALLBACK_ENABLED=true` 且提供 `TRANSLATION_FALLBACK_MODEL_NAME` 時啟用。兩條 route 分別取得自己的 provider URL／key／timeout／reasoning 設定；`paid` 是既有設定名稱，適用明確配置的雲端備援。Timeout／連線失敗、408／429／5xx、無效輸出可 fallback；其他 4xx（含認證／設定錯誤）停止。跨 provider daily quota 仍逐 request 預留；per-run fallback quota 沿用原設定。未呼叫的 fallback 不記成失敗 provider。

Layer 1 單次 API call 直接產生多語 `translations[]`：

```json
{
  "translations": [
    {
      "language": "zh-Hant",
      "summary": "繁體中文摘要",
      "full_translation": "繁體中文全文翻譯"
    },
    {
      "language": "en",
      "summary": "English summary",
      "full_translation": "English full translation"
    }
  ],
  "detected_language": "fa",
  "notes": null
}
```

Layer 1 僅負責翻譯文字與狀態，失敗不清除或替換 Layer 2 的 taxonomy。Layer 2 transaction 已 commit 後，usage／翻譯的儲存失敗會記錄 error log，不把已完成的分類 task 改回 failed／retry。翻譯的 API 與 storage 錯誤分開處理；DB 失敗不觸發另一個 provider，也不將成功翻譯覆寫為 failed rows。

`TRANSLATION_REQUIRE_ALL_LANGUAGES=false` 僅允許少回部分語言，不允許已提供的語言缺少摘要，或在 full policy 下缺全文。空 enabled categories 只允許 `other`；空 enabled domains 要求 primary 為 null、relevant_domains 為空。

Taxonomy 規則：

- `content_category` 是 controlled category，Layer 2 prompt 會帶入 DB 中啟用的 `content_categories`，模型必須優先從這些 keys 選擇；若都不適合，使用 `other`。
- `topic_tags` 是 semi-controlled tags，Layer 2 會看到一批 known tags，但可以輸出新的短 tag。
- normalizer 回寫前會對 tags 做 lowercase、slug normalization、alias mapping 與去重。
- normalized tags 會自動 upsert 到 `tags`，並寫入 `raw_item_tags` 關聯；`raw_items.topic_tags` 保留作為 Timeline 查詢快取。
- `mentioned_actors` V1 仍保留在 `raw_items.mentioned_actors`，不併入 tags，避免 topic 與 entity 混淆。

Layer 2 只讀 `source` metadata、`text_clean` / `text_raw` 原文、rule prefilter 結果與受控 taxonomy context。它不讀 legacy summary 或 full translation。Classification、taxonomy 關聯、processing result 與 event 建立在同一 transaction 完成。

The runtime prefilter loads enabled domains, grouped keywords, optional source priors
and active prompt modules from PostgreSQL. A source prior cannot pass an item without
a content match. It loads at most two score-ranked domain lenses into one classification
request and stores all matches plus the routing configuration hash on raw items/events.
Shared UTC daily request limits are optional until calibrated; when configured, their
PostgreSQL reservation is required before each provider request.

## 10.1 AI Usage Tracking

每次 AI API call 都應寫入 `ai_model_calls`：

| Layer | `ai_layer` | `request_kind` | 主要模型 |
| --- | --- | --- | --- |
| Layer 1 | `translation_summary` | `translate_summary` | 預設 `openai/gpt-6-luna`；可配置 Cloud model |
| Layer 2 | `classification_reasoning` | `classify_raw_item` | 預設 `openai/gpt-6-luna`；可配置 Cloud model |

Token 來源：

1. 優先使用 OpenAI-compatible response 的 `usage.prompt_tokens`、`usage.completion_tokens`、`usage.total_tokens`。
2. 若 provider 未回 usage，使用 `tiktoken` 估算 input / output token，並在 `usage_json.estimated = true` 標記。
3. 成本依 `usage.py` 的已知 provider／model 單價估算，並非帳單權威。Ollama Cloud 尚無本系統確認的單價，`estimated_cost_usd=null`；未知不等於免費。缺 input／output 時不將未知量當零推導 total 或完整成本；tokenizer／cache 失敗仍保留原始模型結果／錯誤與 usage attempt，未知 token 保持 null，`usage_json.estimation_errors` 保存估算錯誤類別。

`request_hash` 用於排查重複 call；DB usage 不保存完整 prompt。DEBUG HTTP log 會含請求與回應內容，憑證欄位有遮罩。

共同操作介面為 `classify(...) -> ModelResponse` 與 `summarize_and_translate(...) -> AuxiliaryModelResponse`。兩個 Layer 沿用既有輸出契約與禁止交易指令規則。完整拆分、驗收與提交紀錄見[實作計畫](../2026-10-21-news-model-providers-implementation-plan.md)。

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
  "summaries": [
    {"language": "zh-Hant", "summary": "Tasnim 否認伊朗將放棄濃縮鈾的說法。"},
    {"language": "en", "summary": "Tasnim denies Iran will abandon uranium enrichment."}
  ],
  "content_category": "diplomacy",
  "topic_tags": ["iran", "nuclear"],
  "primary_domain": "geopolitics",
  "relevant_domains": ["geopolitics"],
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
# Independent cloud provider selectors; existing OpenRouter settings remain defaults.
CLASSIFICATION_MODEL_PROVIDER=openrouter
TRANSLATION_MODEL_PROVIDER=openrouter
# Blank uses the primary provider. Fallback still requires its enable flag and model.
TRANSLATION_FALLBACK_PROVIDER=
# Blank OpenRouter timeouts inherit MODEL_TIMEOUT_SECONDS.
CLOUD_MODEL_TIMEOUT_SECONDS=
TRANSLATION_MODEL_TIMEOUT_SECONDS=
# Direct Ollama Cloud API only. Models must be selected explicitly from its catalog.
OLLAMA_CLOUD_BASE_URL=https://ollama.com/v1
OLLAMA_API_KEY=
OLLAMA_CLOUD_CLASSIFICATION_MODEL=
OLLAMA_CLOUD_TRANSLATION_MODEL=
OLLAMA_CLOUD_CLASSIFICATION_TIMEOUT_SECONDS=60
OLLAMA_CLOUD_TRANSLATION_TIMEOUT_SECONDS=60
# Leave unset unless supported by the selected Cloud model.
OLLAMA_CLOUD_CLASSIFICATION_REASONING_EFFORT=
OLLAMA_CLOUD_TRANSLATION_REASONING_EFFORT=
CLOUD_MODEL_BASE_URL=https://openrouter.ai/api/v1
CLOUD_MODEL_API_KEY=...
CLOUD_MODEL_NAME=openai/gpt-6-luna
CLOUD_MODEL_RESPONSE_FORMAT=json_schema
CLOUD_MODEL_REASONING_EFFORT=none
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
TRANSLATION_PRIMARY_MODEL_NAME=openai/gpt-6-luna
TRANSLATION_FALLBACK_MODEL_NAME=
TRANSLATION_PAID_FALLBACK_ENABLED=false
TRANSLATION_MODEL_RESPONSE_FORMAT=json_schema
TRANSLATION_MODEL_REASONING_EFFORT=none
TRANSLATION_HTTP_REFERER=
TRANSLATION_APP_TITLE=XAUUSD Event Radar
TRANSLATION_OUTPUT_LANGUAGES=zh-Hant,en
TRANSLATION_LANGUAGE_LABELS_JSON={"zh-Hant":"Traditional Chinese","en":"English"}
TRANSLATION_REQUIRE_ALL_LANGUAGES=true
TRANSLATION_DEFAULT_MAX_CHARS=20000
TRANSLATION_HIGH_PRIORITY_MAX_CHARS=100000
TRANSLATION_SINGLE_CALL_MAX_CHARS=100000
MAX_CLASSIFICATION_CALLS_PER_RUN=0
MAX_TRANSLATION_CALLS_PER_RUN=0
MAX_TRANSLATION_PAID_FALLBACK_CALLS_PER_RUN=0
AI_DAILY_REQUEST_LIMIT=0
AI_DAILY_CLASSIFICATION_LIMIT=0
AI_DAILY_TRANSLATION_LIMIT=0
CLAUDE_CODE_AGENT_ENABLED=false
CLAUDE_CODE_AGENT_MODEL=...
MODEL_TIMEOUT_SECONDS=30
MAX_MODEL_CALLS_PER_RUN=0
RELEVANCE_THRESHOLD_EVENT=70
RELEVANCE_THRESHOLD_PUSHOVER=85
LOG_LEVEL=INFO
```

OpenRouter 既有 `CLOUD_MODEL_*`（Layer 2）與 `TRANSLATION_MODEL_*`（Layer 1）設定保留。`CLOUD_MODEL_TIMEOUT_SECONDS`／`TRANSLATION_MODEL_TIMEOUT_SECONDS` 留空時沿用 `MODEL_TIMEOUT_SECONDS`。`OPENROUTER_MODEL_API_KEY` 仍可作翻譯 key 的既有 fallback；不會被借給 Ollama Cloud。

Ollama Cloud 各 Layer 使用 `OLLAMA_CLOUD_CLASSIFICATION_MODEL`／`OLLAMA_CLOUD_TRANSLATION_MODEL`、各自 timeout 與可選 reasoning effort。只在啟用對應 route 時檢查 key／model；預設不送 reasoning 參數。`TRANSLATION_FALLBACK_MODEL_NAME` 指定備援 provider 的 model。若 fallback provider 是 OpenRouter，使用 `TRANSLATION_MODEL_*`；若為 Ollama Cloud，使用 `OLLAMA_*` 的翻譯設定。

OpenRouter 解析會拒絕已知非正常 `finish_reason`／refusal，即使 content 是有效 JSON；缺 finish_reason 時保留既有相容行為。

OpenRouter 的 response format 可選 `none`、`json_object`、`json_schema`、`text`；reasoning effort `none` 會轉成 OpenRouter 的 `reasoning.enabled=false`。這些選項不會套用到 Ollama Cloud。OpenRouter 可設定 referer／app title headers；[舊模型測試 prompt](../model-evaluation-openrouter.md) 只供人工評估參考。

切換範例（僅為設定說明，啟用前需要真實模型驗收與額度確認）：

```text
CLASSIFICATION_MODEL_PROVIDER=openrouter
TRANSLATION_MODEL_PROVIDER=ollama_cloud
OLLAMA_API_KEY=<cloud-api-key>
OLLAMA_CLOUD_TRANSLATION_MODEL=<exact-cloud-catalog-model>
TRANSLATION_FALLBACK_PROVIDER=openrouter
TRANSLATION_PAID_FALLBACK_ENABLED=true
TRANSLATION_FALLBACK_MODEL_NAME=openai/gpt-6-luna
```

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
- Ollama Cloud API mock。
- OpenRouter API mock、跨 provider translation fallback 與逐次預算／usage。
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
- 獨立 OpenRouter／Ollama Cloud client、共同操作介面與業務驗證。
- pydantic model output validation。
- processing result 回寫。
- relevance threshold 達標時建立 `events`。
- 有 `claim_text` 時建立簡化 `event_claims`。
- model failure retry / failed state。

尚未完成：

- `LISTEN raw_item_created` wake-up，現在先使用 polling。
- 近似重複合併到既有 event。
- Claude Code Agent SDK route。
- metrics endpoint。
