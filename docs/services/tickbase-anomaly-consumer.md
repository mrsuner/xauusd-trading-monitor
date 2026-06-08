# tickbase-anomaly-consumer 功能需求

## 1. 服務定位

`tickbase-anomaly-consumer` 是 XAUUSD Event Radar 的**外部行情異常事件接入服務**。它訂閱 [tickbase](../../../tickbase) 的 anomaly feed，把「指標異常」(例如黃金 60 秒內波動 > 10 USD、某匯率 5 分鐘變動 > X%)轉成 xauusd domain 的 `events`,並決定該送到哪些通知出口。

它與既有 collector 不同:

- 既有 collector(`telegram-collector` / `rss-collector`)採集**新聞文本**,寫 `raw_items`,交給 `normalizer-classifier` 做 AI 分類。
- `tickbase-anomaly-consumer` 接入的是**已被 tickbase 偵測、去重、cooldown 過的數值事實**,不需要 AI 判斷,不寫 `raw_items`,不經過 `normalizer-classifier`。

它與既有 `event-router` 也不同:

- `event-router` 是**新聞**事件的路由器,套用 source authority / aggregator / confirmation 等新聞向政策。
- `tickbase-anomaly-consumer` 對 anomaly 做**自有的確定性路由**(severity → channel),不借用新聞政策,也不被新聞政策影響。

目標資料流:

```text
tickbase api-go  (SSE /v1/anomaly-events/stream  +  REST /v1/anomaly-events?since=)
  ↓
tickbase-anomaly-consumer   (ingest + idempotency + 自有路由)
  ↓
events  +  alerts / public_outbox        (一個 transaction 寫入)
  ↓
alert-dispatcher / telegram-channel-publisher   (僅投遞,服務本身不改)
  ↓
私人 Telegram/Pushover   /   公共 Telegram Channel
```

## 2. 設計原則:職責隔離

本服務的核心設計取捨是**「reuse 投遞層,但隔離路由政策」**。

- **共用** `events`(append-only 事件記錄,以 `event_type` 區分新聞 vs anomaly)、`alerts` / `public_outbox`(兩張投遞隊列表)、`alert-dispatcher` / `telegram-channel-publisher`(投遞 worker,**完全不改**)。
- **隔離** anomaly 的路由決策:由本服務自己把 severity 映射成頻道並直接寫入隊列表,**不交給** `event-router` 的新聞向 `policy.py`。

理由(為什麼不讓 `event-router` 路由 anomaly):

1. `event-router` 的 `route_score()` 由 `source.priority / official_level / alert_weight / confirmation_state` 計算 —— 這些對「一筆數值波動」沒有意義,得偽造一個 `sources` row 去湊分數。
2. 公共頻道 route 有硬性 gate `has_public_source_url()`,要求 `event.raw_item.url`。anomaly 沒有 `raw_item`,得再偽造一筆 `raw_items` 假 URL。
3. 一旦借用,anomaly 的投遞行為就被新聞評分政策綁死 —— 未來調整新聞評分可能無聲地改變 anomaly 路由,違反單一變更理由原則。

職責切分:

| 元件 | 職責 | 本次改動 |
| --- | --- | --- |
| tickbase | 偵測、去重 / cooldown、append-only event log、feed API | 無(已完成) |
| **tickbase-anomaly-consumer** | 傳輸(SSE/REST)、idempotency / cursor、anomaly→events 映射、anomaly→channel 路由 | **新增** |
| `alert-dispatcher` / `telegram-channel-publisher` | 投遞 + retry / backoff | 無 |
| `event-router` | 新聞事件路由 | **+1 行**:`unrouted_event_ids` 排除 `event_type = 'market_anomaly'` |

唯一動到既有 service 的地方,是 `event-router` 的一行排除(見 §6)。這是 consumer 與 event-router 之間**唯一、顯式、自我說明**的接縫。

## 2.1 實作狀態

第一版 runtime 已實作並驗證:

- migration `0016_tickbase_anomaly_ingest`:`tickbase_anomaly_ingest` mirror 表 + seed `TickBase Anomaly Feed` source(`source_group='market_anomaly'`)。
- `services/tickbase-anomaly-consumer` Python service:`feed_client`(SSE + REST)、`mapping`(severity / summary / 路由)、`db`(單 tx idempotent ingest)、`worker`(catch-up + stream 重連)。
- `event-router.unrouted_event_ids` 加入 `event_type <> 'market_anomaly'` 排除。
- 測試:`mapping` / `settings` / `feed_client`(SSE 解析、auth、錯誤)單元測試;`test_db_integration`(gate 在 `TEST_DATABASE_URL`)對真實 migrated Postgres 驗證 idempotency 與 severity→頻道寫入。`make compose-config` 通過。
- dev / prod 整合:`make dev`(gate `ANOMALY_CONSUMER_ENABLED=true`)、`docker-compose.prod.yml`(profile `anomaly-consumer`)、`docker-images.sh`、`.env.example` / `.env.dev.example`。

預設 `ANOMALY_CONSUMER_ENABLED=false`,需設定 `TICKBASE_API_KEY` 並啟用後才連線。

## 3. 目標

- 部署於 HomeLab,與其他 worker 並列。
- 以 SSE 長連線即時接收 tickbase anomaly,REST `?since=` 作為 catch-up / fallback。
- 以 tickbase 事件的 `id` 作為 idempotency key,reconnect / replay 安全(at-least-once)。
- 持久化 cursor(已處理的最大 `id`),crash 後可從中斷處續接。
- 把每筆 anomaly 確定性地映射成一筆 `events`(`event_type='market_anomaly'`)。
- 確定性路由:依 severity 寫入 `alerts`(私人)與 / 或 `public_outbox`(公共頻道)。
- 與新聞 pipeline 的路由政策完全分離。
- 支援 dev 安全旗標(沿用既有 `ALERT_DRY_RUN` / `TELEGRAM_CHANNEL_DRY_RUN`,本服務不直接送訊息,故安全模式由下游 worker 既有機制承接)。

## 4. tickbase feed 契約(上游)

| 項目 | 內容 |
| --- | --- |
| SSE | `GET /v1/anomaly-events/stream`(優先,低延遲;reconnect 帶 `Last-Event-ID`) |
| REST | `GET /v1/anomaly-events?since=<id>`(catch-up / fallback;cursor 分頁) |
| Auth | header `Authorization: Bearer tb_live_…` 或 `X-API-Key: …`(server-to-server) |
| Idempotency | 每筆事件有單調遞增 `id`;**以 `id` 作為冪等鍵** |
| Event JSON | `id, rule_id, asset_class, base, quote, direction (up\|down), metric (abs\|pct), window_secs, threshold, change_abs, change_pct, value_start, value_end, obs_count, window_start, triggered_at`(RFC3339 UTC) |
| Instrument 慣例 | gold = `asset_class=metal, base=XAU, quote=USD`;FX = `asset_class=fx, base=USD, quote=EUR`。**沒有「base 永遠 USD」捷徑** |
| SSE ops | server 送 `: ping` heartbeat(~25s)與 `X-Accel-Buffering: no`;每 key 併發串流上限(超過回 `429 too_many_streams`) |

完整上游設計見 `tickbase/docs/features/anomaly-monitoring.md`。

## 5. 服務結構(沿用 repo 慣例)

`services/tickbase-anomaly-consumer/src/tickbase_anomaly_consumer/`

| 檔案 | 職責 |
| --- | --- |
| `__main__.py` | `run`(常駐) / `once`(單輪 catch-up,測試用)子命令 |
| `settings.py` | pydantic-settings,env-aliased:tickbase base URL / API key、enable flag、severity 映射門檻、SSE reconnect / backoff、start mode |
| `feed_client.py` | httpx:SSE 長連線(`Last-Event-ID` 續傳)+ REST `?since=` catch-up / fallback;解析 SSE frame |
| `mapping.py` | **純函式**:anomaly JSON → `severity` / `summary_zh` / `title` / 頻道集合 / `alerts.message`。anomaly 專屬,不碰 `event-router/message.py` |
| `db.py` | psycopg3 async;cursor 讀寫;一個 transaction 內 idempotent 寫入 `tickbase_anomaly_ingest` + `events` + `alerts` + `public_outbox` |
| `worker.py` | 主迴圈:啟動 catch-up → SSE 長連線 → 逐筆 ingest;斷線重連與 backoff |
| `models.py` | dataclass / pydantic:`AnomalyEvent`、`MappedEvent` 等 |
| `Dockerfile` / `pyproject.toml` / `tests/` | 標準化打包與測試 |

## 6. 資料流與寫入細節

### 6.1 每筆 anomaly 的 transaction

對每一筆新 anomaly,在**單一 transaction**內:

1. `insert into tickbase_anomaly_ingest (tickbase_id, ...) values (...) on conflict (tickbase_id) do nothing`
   - `rowcount = 0` → 該筆已處理過,整筆 **skip**(replay 安全),不再往下寫。
2. `insert into events (...)` → 取得 `event_id`。
3. 依 `mapping.py` 的路由結果,寫入:
   - `alerts`(若命中私人 Telegram):`channel='telegram'`、`delivery_status='pending'`、`dedupe_key='anomaly:{tickbase_id}:telegram'`、`message`=映射文字。
   - `public_outbox`(若命中公共頻道):`approved_for_public=true`、`publish_status_telegram='pending'`、`publish_status_web='skipped'`、`publish_status_x='skipped'`、`event_id`=上面取得的值。
4. 回填 `tickbase_anomaly_ingest.event_id`。

整筆原子化 → 不會留下 orphan `events` 或重複投遞。

### 6.2 events row 映射

| 欄位 | 值 |
| --- | --- |
| `event_type` | `'market_anomaly'`(路由與查詢的判別鍵) |
| `severity` | 由 §7 映射 |
| `confirmation_state` | `'confirmed'`(量測事實,非傳聞) |
| `relevance_score` | 確定性值(anomaly 為高訊號) |
| `event_time` | `triggered_at` |
| `detected_at` | `now()` |
| `summary_zh` | 格式化字串,例:「黃金 XAU/USD 60 秒內上漲 15.0 USD(+0.6%),2400 → 2415」 |
| `source_id` | 指向 seed 的 tickbase source(§8),讓 dashboard / syncer 的 join 正常 |
| `raw_item_ids` | `'{}'`(無 raw_item) |

### 6.3 event-router 的一行排除

`event-router` 的 `unrouted_event_ids`(`db.py`)目前**不依 `event_type` 過濾**,會撈走每一筆未路由 event。為避免它把 anomaly 也跑一次新聞路由(並可能與我們直接寫入的 `public_outbox` 在 `unique(event_id)` 上衝突),在其 WHERE 子句加入:

```sql
and e.event_type <> 'market_anomaly'
```

這比「預先塞 5 筆 `event_route_decisions` 騙過 `< 5` 判斷」更穩定、顯式、可讀。它是 consumer 與 event-router 之間唯一的耦合點,需在兩邊文件標註。

## 7. severity 映射(確定性、可配置)

依 `change_abs`(`metric=abs`)或 `change_pct`(`metric=pct`)相對 `threshold` 的倍率分級,env 可調:

- 倍率越高 → severity 越高(S / A / B / C)。
- **公共頻道僅 S / A 級**(大波動才公開);B / C 級只走私人告警。
- 私人 Telegram 告警:預設所有 severity 皆上(anomaly 本身已是高訊號,且 tickbase 端已做 cooldown 去重)。

路由結果矩陣:

| severity | 私人 Telegram(`alerts`) | 公共頻道(`public_outbox`) |
| --- | --- | --- |
| S | ✅ | ✅ |
| A | ✅ | ✅ |
| B | ✅ | ✖ |
| C | ✅ | ✖ |

(門檻倍率以 env 設定,預設值於實作時定稿。)

## 8. 資料模型(新 Alembic migration)

1. **`tickbase_anomaly_ingest`**(mirror / idempotency / cursor 來源):

   | 欄位 | 型別 / 約束 |
   | --- | --- |
   | `tickbase_id` | `bigint primary key`(= idempotency key) |
   | `event_id` | `uuid not null references events(id)` |
   | `rule_id` | `text` |
   | `asset_class` / `base` / `quote` | `text` |
   | `direction` / `metric` | `text` |
   | `triggered_at` | `timestamptz` |
   | `raw` | `jsonb`(完整上游 payload,供追溯) |
   | `ingested_at` | `timestamptz default now()` |

   - cursor = `select max(tickbase_id) from tickbase_anomaly_ingest`,免額外 cursor 表。

2. **seed `sources`**(`INSERT ... ON CONFLICT DO UPDATE`,符合 migration 慣例):
   - 一筆代表 tickbase 的 source,`source_group='market_anomaly'`(**須避開 `AGGREGATOR_GROUPS` = `{osint_aggregator, market_squawk}`**)。
   - 即使 consumer 自路由,`events.source_id` 仍指向真實 source,`public-syncer` / `dashboard-api` 對 `events` 的 inner join 才正常。

migration 維持 schema + idempotent seed,無 backfill / 外部呼叫,符合 `docs/database-migrations.md`。

## 9. Idempotency / cursor / 續接 / backfill

- **Idempotency**:`tickbase_anomaly_ingest.tickbase_id` 唯一 + `on conflict do nothing`;`alerts.dedupe_key` 唯一 + `public_outbox.unique(event_id)` 為雙重防重。
- **Cursor 續接**:cursor = 已處理 max `id` → 啟動先 REST catch-up,再開 SSE 並帶 `Last-Event-ID`。
- **首次部署 start mode**:`ANOMALY_CONSUMER_START=tail`(預設)—— 從 tickbase 當下最大 `id` 起算,**不回灌歷史**,避免首啟洪泛。可選 `earliest` / 指定 `<id>`。
- **斷線**:SSE 斷線以指數 backoff 重連,期間若需要可用 REST 補洞。

## 10. 設定(env)

| Key | 用途 | 預設 |
| --- | --- | --- |
| `TICKBASE_API_BASE_URL` | tickbase api-go base(如 `https://api.thetickbase.com`) | — |
| `TICKBASE_API_KEY` | `Authorization: Bearer` / `X-API-Key` | — |
| `ANOMALY_CONSUMER_ENABLED` | 服務開關 | `true` |
| `ANOMALY_CONSUMER_START` | `tail` / `earliest` / `<id>` | `tail` |
| `ANOMALY_SSE_RECONNECT_BACKOFF_SECONDS` | 重連 backoff 上限 | 待定 |
| `ANOMALY_SEVERITY_*_MULTIPLIER` | severity 分級倍率門檻 | 待定 |
| `DATABASE_URL` | 核心 PostgreSQL | — |

## 11. 部署

- `Dockerfile` 同其他 service;`infra/docker-compose.prod.yml` 新增一個 service(image from GHCR `ghcr.io/mrsuner/xauusd-trading-monitor/tickbase-anomaly-consumer`)。
- `Makefile` 的 `make dev` 背景啟動清單加入本服務。
- DB 變更走既有一次性 `db-migrate`(`alembic upgrade head`)。
- 本服務只寫隊列表、不直接送訊息;實際投遞的 dry-run 由 `alert-dispatcher` / `telegram-channel-publisher` 既有安全旗標承接。

## 12. 測試與驗收

- `mapping.py` 純函式單元測試:各 metric / direction / 倍率 → 正確 severity 與頻道集合、`summary_zh` 文字。
- `db.py` idempotency 測試:同一 `tickbase_id` 重放兩次只產生一筆 `events` / `alerts` / `public_outbox`。
- catch-up / SSE 解析測試:REST 分頁推進 cursor;SSE frame 解析與 `Last-Event-ID` 續傳。
- 端到端(可 gate 在真實 DB):seed 一筆 anomaly → 確認產生對應 `events` + 依 severity 的 `alerts` / `public_outbox`,且 `event-router` 不會重複路由(驗證 §6.3 排除生效)。

## 13. 與 V1 範圍的關係

V1 明確將 market-data 反查排除在外(`docs/final-target-and-v1-scope.md`)。本服務消費的是 tickbase 已成形的**異常事件**(非原始行情序列),是 xauusd 在新聞層之外的 V2 擴充:把外部行情異常接入既有 `events → 投遞` 管線,而偵測 / 去重 / cooldown 全留在 tickbase。
