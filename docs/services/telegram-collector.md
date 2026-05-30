# telegram-collector 功能需求

## 1. 服務定位

`telegram-collector` 是 XAUUSD Event Radar MVP 的 Telegram 採集服務，負責透過 Telethon / MTProto 監聽指定 Telegram channels，將新消息與啟動回補消息寫入 PostgreSQL 的 `raw_items` 表。

此服務只負責「可靠採集與原始入庫」，不負責事件判斷、AI 摘要、交易方向推論或告警發送。

## 2. MVP 目標

第一版目標：

- 使用單一 Telegram user session 監聽 MVP channel 清單。
- 即時接收 `NewMessage`。
- 啟動時回補最近 N 小時歷史消息。
- 將原始消息標準化寫入 `raw_items`。
- 保留 Telegram message id、channel id、時間、原文、連結、media metadata 與 raw JSON。
- 支援去重，避免重啟或回補造成重複資料。
- 維護每個 Telegram source 的採集狀態與錯誤狀態。
- 透過 PostgreSQL `NOTIFY` 或 database trigger 通知後續 normalizer。

## 3. 非目標

第一版不包含：

- 多 Telegram user session 水平擴展。
- 多節點同時跑同一 session。
- 對 Telegram 消息做 AI 分析。
- 翻譯波斯語、希伯來語或阿拉伯語。
- 直接推送 Telegram / Pushover alert。
- 建立交易訊號或交易建議。
- 抓取完整網頁內容。
- 自動加入 Telegram channel。

## 4. 技術棧

### 4.1 後端主要技術

| 類別 | 選型 | 說明 |
| --- | --- | --- |
| Language | Python 3.12+ | MVP 主語言 |
| Telegram client | Telethon | 使用 MTProto 監聽 Telegram updates |
| Database | PostgreSQL 16+ | 寫入 `raw_items`、讀取 `sources` |
| DB driver | psycopg 3 / asyncpg | 依服務是否採 async-first 實作決定 |
| Config | pydantic-settings | 管理 env 與設定檔 |
| Logging | structlog / standard logging | 輸出 JSON-friendly structured logs |
| Scheduling | asyncio task | 啟動回補與週期性 health update |
| Packaging | uv | Python dependency 與 script 管理 |
| Container | Docker | HomeLab 部署 |

### 4.2 備選技術

Go 可作為後續高併發或單 binary 部署的備選，但 MVP 不優先使用。

Go 備選方向：

| 類別 | 選型 |
| --- | --- |
| Language | Go 1.23+ |
| Telegram client | gotd/td |
| Database | pgx |
| Config | envconfig / koanf |

除非 Python Telethon 在穩定性或部署上出現明確瓶頸，否則第一版不切換到 Go。

### 4.3 前端關聯

`telegram-collector` 本身沒有前端 UI。它需要提供可被 Dashboard API 讀取的狀態資料，Dashboard Web 後續統一使用：

- React Router V7
- TanStack Query
- TailwindCSS V4
- DaisyUI V5

Dashboard 需要能展示：

- Telegram source 是否啟用。
- 最近一筆消息時間。
- 最近錯誤。
- 回補狀態。
- session 連線狀態。
- 每個 source 的 1h / 24h 採集數量。

## 5. Source Registry

服務不得在程式碼中寫死 channel 清單，必須從 `sources` 表讀取啟用的 Telegram sources。

必要欄位：

```text
id
name
handle_or_url
source_type
source_group
official_level
stance
language
priority
reliability_score
latency_score
requires_confirmation
enabled
created_at
updated_at
```

查詢條件：

```sql
source_type = 'telegram'
and enabled = true
```

`handle_or_url` 支援格式：

```text
@Irna_en
https://t.me/Irna_en
Irna_en
```

服務啟動時應正規化為 Telethon 可解析的 entity identifier。

## 6. MVP Telegram Sources

第一版建議採集：

| Priority | Channel | Source Group | 用途 |
| --- | --- | --- | --- |
| P0 | `@TrumpTruthSocial_Alert` | `us_trump` | Trump Truth Social 第三方鏡像 |
| P0 | `@Irna_en` | `iran_government` | 伊朗政府官方英文口徑 |
| P0 | `@Tasnimnews` | `iran_irgc_adjacent` | IRGC / 強硬派附近風向 |
| P0/P1 | `@Khamenei_en` | `iran_supreme_leader` | 最高領袖戰略紅線 |
| P0 | `@idfofficial` | `israel_military` | 以色列軍方官方消息 |
| P1 | `@presstv` | `iran_external_media` | 伊朗對外英文敘事 |
| P1 | `@enmehrnews` | `iran_conservative` | 伊朗保守派 / 半官方風向 |
| P1 | `@israelmfa` | `israel_diplomacy` | 以色列外交官方口徑 |
| P1/P2 | `@FinancialJuice` 或 `@firstsquaw` | `market_squawk` | 市場 squawk |
| P2 | `@Middle_East_Spectator` | `osint_aggregator` | 中東早期提示 |
| P2 | `@OSINTdefender` | `osint_aggregator` | OSINT 衝突補充 |

注意：`@sepah_pasdaran` 這類個人或支持者頻道不得定義為 IRGC 官方源。

## 7. 資料流

```text
sources
  ↓ load enabled telegram sources
Telethon session
  ↓ resolve channel entities
NewMessage event
  ↓ normalize telegram message
raw_items
  ↓ Postgres trigger or explicit NOTIFY
normalizer-classifier
```

啟動流程：

1. 載入設定。
2. 連線 PostgreSQL。
3. 讀取 enabled Telegram sources。
4. 初始化 Telethon client 與 session。
5. resolve channel entities。
6. 對每個 source 執行歷史回補。
7. 註冊 `NewMessage` handler。
8. 進入長連線監聽。
9. 週期性更新 service health。

## 8. Raw Item 寫入需求

所有 Telegram 消息先寫入 `raw_items`。

建議欄位對應：

| `raw_items` 欄位 | Telegram 來源 |
| --- | --- |
| `source_id` | `sources.id` |
| `external_id` | Telegram `message.id` |
| `published_at` | Telegram `message.date` |
| `ingested_at` | collector 寫入時間 |
| `edited_at` | Telegram `message.edit_date` |
| `title` | 通常為 `null`，可後續由 normalizer 生成 |
| `text_raw` | 原始 message text |
| `text_clean` | collector 只做最低限度清洗，可等於 `text_raw` |
| `language` | 來源預設語言或 `null` |
| `url` | Telegram message public URL，如果可生成 |
| `media_type` | `none` / `photo` / `video` / `document` / `webpage` |
| `raw_json` | Telegram message serialization |
| `content_hash` | 內容 hash |
| `dedupe_key` | `telegram:{channel_id}:{message_id}` |

去重約束：

```text
unique(source_id, external_id)
unique(dedupe_key)
```

如果消息已存在：

- 不新增重複 row。
- 若 `edited_at` 變更新，允許更新 `text_raw`、`text_clean`、`edited_at`、`raw_json`。
- 不覆蓋 `ingested_at`，必要時使用 `updated_at` 記錄更新。

## 9. Message URL 規則

公開 channel 可生成：

```text
https://t.me/{public_username}/{message_id}
```

私有或不可公開 channel：

```text
url = null
```

MVP channel 應盡量使用公開 channel，方便 Dashboard 和人工驗證。

## 10. 歷史回補需求

服務啟動時應對每個 enabled source 回補最近 N 小時消息。

預設：

```text
BACKFILL_HOURS=6
BACKFILL_LIMIT_PER_SOURCE=500
```

要求：

- 回補與即時監聽使用同一套 normalize / upsert 邏輯。
- 回補必須可重入。
- 回補不得阻塞所有即時消息處理太久。
- source 回補失敗時應記錄錯誤，但不應讓整個服務退出。

優先策略：

- 啟動後先建立即時 handler。
- 再以 background task 執行回補。
- 回補過程依 source priority 排序，P0 優先。

## 11. Edited Message 處理

MVP 至少需要處理 Telegram edited message。

要求：

- 如果收到已存在 `external_id` 的消息，且 `edit_date` 更新，更新原始內容。
- `raw_items.edited_at` 保存 Telegram edit time。
- 若已生成事件，後續版本需要通知 normalizer 重新評估；MVP 可先只更新 raw item。

可選：

- 新增 `raw_item_versions` 保存歷史版本。

MVP 不強制做版本表，但 schema 設計不應阻礙後續加入。

## 12. Media 處理

MVP 不下載 media 檔案，只保存 metadata。

需保存：

- media type
- caption text
- Telegram file id / media id，如果可取得
- webpage preview URL，如果存在
- raw JSON

原因：

- 下載 media 會增加儲存、頻寬與權限複雜度。
- 第一版事件偵測主要依文字內容。

後續可新增 `media_fetcher` 或在 normalizer 需要 OCR 時再補。

## 13. 錯誤處理

服務需分類處理以下錯誤：

| 類型 | 處理方式 |
| --- | --- |
| Telegram auth error | 記錄 fatal error，服務退出，等待人工重新登入 |
| Flood wait | 遵守 Telethon 回傳等待時間，暫停相關操作 |
| Channel resolve failed | 標記 source health error，其他 source 繼續 |
| DB connection failed | retry with backoff |
| Insert conflict | 視為正常去重，不記 error |
| Serialization failed | 保存可用欄位，raw_json 可降級為 partial payload |
| Permission denied / private channel | 標記 source disabled candidate，不自動修改 `sources.enabled` |

重試策略：

```text
initial_backoff = 1s
max_backoff = 60s
jitter = true
```

## 14. Health 與 Observability

建議新增 `source_health` 或等價資料表。

必要資訊：

```text
source_id
service_name
status                  healthy / degraded / failed
last_seen_at
last_message_at
last_success_at
last_error_at
last_error_message
messages_ingested_1h
messages_ingested_24h
backfill_status          pending / running / completed / failed
backfill_started_at
backfill_completed_at
updated_at
```

服務層 metrics：

- Telegram connection status
- active source count
- resolved source count
- unresolved source count
- messages received per minute
- messages inserted per minute
- duplicate count
- DB insert latency
- backfill duration per source
- latest Telegram update lag

日誌要求：

- 使用 structured logs。
- 每筆新消息不必完整印出原文，避免 log 過大。
- error log 需包含 `source_id`、`handle_or_url`、`external_id`、`error_type`。

## 15. 設定項

環境變數建議：

```text
APP_ENV=development
SERVICE_NAME=telegram-collector
DATABASE_URL=postgresql://...
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
TELEGRAM_SESSION_PATH=/app/sessions/xauusd-event-radar.session
BACKFILL_HOURS=6
BACKFILL_LIMIT_PER_SOURCE=500
SOURCE_REFRESH_INTERVAL_SECONDS=300
HEALTH_UPDATE_INTERVAL_SECONDS=30
LOG_LEVEL=INFO
```

Secret 管理：

- `TELEGRAM_API_ID`、`TELEGRAM_API_HASH`、DB password 不得提交到 repo。
- local dev 可用 `.env.local`。
- HomeLab Docker 部署應使用 Docker secrets、env file 或外部 secret manager。

## 16. Session 管理

Telethon session 必須持久化。

Docker volume 建議：

```text
./data/telegram-sessions:/app/sessions
```

限制：

- 同一 session 不得在多台機器或多個 container 同時使用。
- `telegram-collector` replicas 固定為 1。
- session 檔案應定期備份，但不可提交到 Git。

第一次登入流程：

1. 在本地或部署環境啟動 login command。
2. 輸入 Telegram phone number、login code、2FA password。
3. 產生 session 檔案。
4. 正式服務使用該 session 檔案啟動。

目前實作的 container command：

```bash
telegram-collector login
telegram-collector run
```

HomeLab 第一次建立 session 時，建議先用與正式服務相同的 session volume 執行一次 `login`，確認 `/app/sessions` 內已產生 session 檔後，再啟動常駐 `run`。

## 17. Source Refresh

服務應支援定期重新讀取 `sources` 表。

預設：

```text
SOURCE_REFRESH_INTERVAL_SECONDS=300
```

要求：

- 新增 enabled Telegram source 後，服務可在下一次 refresh 嘗試 resolve 並開始監聽。
- source 被停用後，服務應停止處理該 source 的新消息。
- 若 Telethon event handler 不方便逐 source 動態移除，MVP 可在 handler 內檢查 source allowlist。

## 18. 安全需求

- 不在 log 中輸出 session path 的敏感內容。
- 不在 log 中輸出 Telegram auth code。
- 不在 raw text 之外額外解析個人身份資料。
- DB user 應只具備必要權限：
  - read `sources`
  - insert / update `raw_items`
  - insert / update `source_health`
  - execute `NOTIFY`，如果採應用層通知
- Telegram session volume 權限限制為服務使用者可讀寫。

## 19. 與 PostgreSQL LISTEN/NOTIFY 的關係

建議由 DB trigger 在 `raw_items` insert 後發送：

```text
NOTIFY raw_item_created, payload = raw_item_id
```

替代方案是由 `telegram-collector` insert 成功後主動發送 `NOTIFY`。

MVP 建議：

- 若 schema migration 已包含 trigger，採 DB trigger。
- 若尚未建立 trigger，collector 可先主動 `NOTIFY`。
- 無論哪種方式，payload 只傳 ID。

## 20. 測試需求

單元測試：

- handle 正規化。
- dedupe key 生成。
- message URL 生成。
- Telegram message to raw item mapping。
- edited message upsert。
- source refresh allowlist 行為。

整合測試：

- 使用測試資料模擬 `NewMessage`。
- 寫入 PostgreSQL test database。
- 驗證 unique constraint 去重。
- 驗證回補重跑不產生重複 row。

手動驗收：

- 能成功登入 Telethon session。
- 能 resolve MVP channels。
- 能收到新消息並寫入 `raw_items`。
- 重啟後能回補最近 6 小時。
- 同一消息不重複寫入。
- source health 顯示最新消息時間與錯誤狀態。

## 21. 驗收標準

MVP `telegram-collector` 完成標準：

- 服務可在 Docker 中長時間運行。
- 單一 session 可穩定監聽 MVP channel 清單。
- 新 Telegram 消息在 5 秒內寫入 `raw_items`，不包含 Telegram 自身延遲。
- 重啟後回補不產生重複資料。
- 每個 source 有可查詢的 health 狀態。
- DB 暫時中斷後可自動重試恢復。
- Telethon session 不會因多實例啟動造成衝突。
- 服務不做 AI 判斷、不做告警發送、不輸出交易建議。

## 22. 後續增強

後續版本可加入：

- `raw_item_versions` 保存 edited message 歷史。
- media download / OCR。
- 多 Telegram account sharding。
- per-source rate control。
- 自動偵測 channel handle 變更。
- Telegram source onboarding 管理 UI。
- 重要 source 掉線時告警。
- 與 normalizer 的 edited item reprocess 流程。
