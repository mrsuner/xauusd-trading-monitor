# rss-collector 功能需求

## 1. 服務定位

`rss-collector` 是 XAUUSD Event Radar V1 的 RSS 與官方頁面採集服務，負責定時輪詢 RSS feeds、Atom feeds 與少量 HTML polling 來源，將新消息標準化寫入 PostgreSQL 的 `raw_items` 表。

此服務只負責「穩定輪詢、解析、去重、原始入庫與 source health」，不負責 AI 分析、事件判斷、相關度評分或告警發送。

## 2. V1 目標

- 從 `sources` 表讀取 enabled RSS / HTML polling sources。
- 依 source priority 與 polling interval 定時輪詢。
- 支援 RSS / Atom feed parsing。
- 支援少量官方頁面的 HTML polling，例如 OFAC Recent Actions。
- 支援 `ETag` / `Last-Modified`，降低重複請求。
- 將新 item 寫入 `raw_items`。
- 使用 `dedupe_key` 與 unique constraint 避免重複入庫。
- 更新 `source_health`。
- 建立 processing task 或觸發 `raw_item_created` notification。

## 3. 非目標

V1 不包含：

- 大規模全文爬蟲。
- JavaScript rendering。
- 自動繞過反爬限制。
- 付費新聞 API 整合。
- Reuters / AP 商業新聞流。
- AI 摘要與翻譯。
- 告警發送。
- 行情資料採集。

## 4. 技術棧

| 類別 | 選型 | 說明 |
| --- | --- | --- |
| Language | Python 3.12+ | V1 主語言 |
| HTTP client | httpx | async HTTP polling |
| Feed parser | feedparser | RSS / Atom parsing |
| HTML parser | selectolax / BeautifulSoup | HTML polling fallback |
| Database | PostgreSQL 16+ | 寫入 `raw_items`、讀取 `sources` |
| DB driver | psycopg 3 / asyncpg | 依 async 實作決定 |
| Config | pydantic-settings | env 與設定管理 |
| Scheduling | asyncio task / APScheduler | source polling loop |
| Logging | structlog / standard logging | structured logs |
| Packaging | uv | dependency 管理 |
| Container | Docker | HomeLab 部署 |

Go 可作為後續備選，常見組合為 `net/http`、`gofeed`、`pgx`。

## 5. Source Registry

`rss-collector` 不應寫死 feed 清單，必須從 `sources` 讀取：

```sql
source_type in ('rss', 'atom', 'html_polling')
and enabled = true
```

建議 `sources` 增加或透過 `raw_json` 保存以下設定：

```text
poll_interval_seconds
request_timeout_seconds
user_agent
etag
last_modified
last_polled_at
html_selector
timezone_hint
```

若 V1 schema 尚未包含這些欄位，可先放在 `sources.raw_json` 或 `source_config` JSON 欄位。

## 6. V1 RSS / 官方頁面來源

建議 V1 優先來源：

| Priority | Source | Source Group | Mode | 用途 |
| --- | --- | --- | --- | --- |
| P0 | Fed RSS | `us_fed` | RSS | Fed 政策、講話與聲明 |
| P0 | CENTCOM Press Releases | `us_military` | RSS / HTML | 中東軍事官方消息 |
| P0 | State Department RSS | `us_diplomacy` | RSS | 談判、制裁、外交聲明 |
| P0 | Tasnim RSS | `iran_irgc_adjacent` | RSS | 伊朗強硬派 / IRGC-adjacent 風向 |
| P0 | SepahNews RSS | `iran_irgc_official` | RSS | IRGC 官方消息 |
| P1 | Mehr RSS | `iran_conservative` | RSS | 保守派 / 半官方風向 |
| P1 | Press TV RSS / page | `iran_external_media` | RSS / HTML | 伊朗英文對外敘事 |
| P1 | Treasury Press Releases | `us_sanctions` | RSS / HTML | 財政與制裁相關消息 |
| P2 | OFAC Recent Actions | `us_sanctions` | HTML polling | 制裁更新 |
| P2 | Jerusalem Post Iran / Middle East | `israel_media` | RSS | 以色列媒體視角 |

V1 可先選較穩定的 5-8 個來源上線，再逐步擴充。

## 7. 資料流

```text
sources
  ↓ load enabled rss/html sources
poll scheduler
  ↓ fetch feed or page
parser
  ↓ normalize feed item
raw_items
  ↓ processing table or NOTIFY
normalizer-classifier
```

輪詢流程：

1. 載入設定。
2. 連線 PostgreSQL。
3. 讀取 enabled RSS / HTML sources。
4. 為每個 source 建立 polling schedule。
5. 發送 HTTP request，帶上 `ETag` / `Last-Modified`。
6. 解析 response。
7. 對 item 生成 `dedupe_key`。
8. upsert `raw_items`。
9. 更新 `source_health` 與 source polling metadata。
10. 建立 processing task 或發送 notification。

## 8. Raw Item 寫入需求

建議欄位對應：

| `raw_items` 欄位 | RSS / HTML 來源 |
| --- | --- |
| `source_id` | `sources.id` |
| `external_id` | RSS `guid`，缺失時使用 link hash |
| `published_at` | feed item published / updated |
| `ingested_at` | collector 寫入時間 |
| `edited_at` | feed item updated，如果存在 |
| `title` | feed item title |
| `text_raw` | summary / content / extracted page text |
| `text_clean` | 最低限度清洗後文字 |
| `language` | source language 或 feed metadata |
| `url` | item link |
| `media_type` | 通常為 `none` / `webpage` |
| `raw_json` | feed item 原始結構與 HTTP metadata |
| `content_hash` | title + text + url hash |
| `dedupe_key` | `rss:{feed_url_hash}:{guid_or_url_hash}` |

去重策略：

- 優先使用 `guid`。
- 沒有 `guid` 時使用 canonical URL。
- URL 也缺失時使用 `title + published_at + source_id` hash。
- 若 feed 更新同一 item，允許更新 `title`、`text_raw`、`edited_at`、`raw_json`。

## 9. Polling Frequency

V1 建議：

| Source 類型 | Polling |
| --- | --- |
| Fed / CENTCOM / State | 60-120 秒 |
| Tasnim / Press TV / Mehr | 60-120 秒 |
| SepahNews | 60-120 秒 |
| Treasury / OFAC | 120-300 秒 |
| Jerusalem Post | 120-300 秒 |

要求：

- 每個 source 可獨立設定 polling interval。
- 失敗後使用 backoff，不應讓單一 source 阻塞其他 source。
- HTTP 304 視為成功輪詢，但不產生 item。

## 10. HTML Polling

HTML polling 只用於沒有穩定 RSS 的官方頁面。

V1 支援：

- 設定 list item selector。
- 解析 title、url、published_at，如果可取得。
- 不做 JavaScript rendering。
- 不做深度全文爬取。

OFAC Recent Actions 屬於 HTML polling 來源，因為它不應被假設為穩定 RSS feed。

## 11. 錯誤處理

| 類型 | 處理方式 |
| --- | --- |
| HTTP timeout | retry with backoff |
| HTTP 304 | 更新 `last_success_at`，不寫 item |
| HTTP 403 / 429 | 延長 backoff，記錄 source degraded |
| feed parse failed | 保存錯誤，source degraded |
| item missing guid | 使用 URL hash fallback |
| DB connection failed | retry with backoff |
| duplicate item | 視為正常，不記 error |

Backoff 建議：

```text
initial_backoff = 5s
max_backoff = 300s
jitter = true
```

## 12. Health 與 Observability

`source_health` 至少記錄：

```text
source_id
service_name
status
last_polled_at
last_success_at
last_item_published_at
last_item_ingested_at
last_error_at
last_error_message
items_ingested_1h
items_ingested_24h
updated_at
```

Metrics：

- active source count
- poll duration
- HTTP status count
- items parsed per poll
- items inserted per poll
- duplicate count
- parse error count
- DB insert latency

## 13. 設定項

```text
APP_ENV=development
SERVICE_NAME=rss-collector
DATABASE_URL=postgresql://...
DEFAULT_POLL_INTERVAL_SECONDS=120
DEFAULT_REQUEST_TIMEOUT_SECONDS=15
SOURCE_REFRESH_INTERVAL_SECONDS=300
HEALTH_UPDATE_INTERVAL_SECONDS=30
USER_AGENT=XAUUSD-Event-Radar/1.0
LOG_LEVEL=INFO
```

目前實作的 container command：

```bash
rss-collector run
```

V1 實作會從 `sources.source_config` 讀取 `poll_interval_seconds`、`request_timeout_seconds`、`etag`、`last_modified`。輪詢成功後會把新的 `etag` / `last_modified` 回寫到同一個 `source_config`，下次 request 會帶上 `If-None-Match` / `If-Modified-Since`。

HTML polling 需要明確 selector 設定：

```json
{
  "list_selector": ".item",
  "title_selector": "a",
  "url_selector": "a",
  "published_selector": "time"
}
```

若 HTML source 尚未設定 selector，服務會把該 source 標記為 degraded，不會影響其他 source 輪詢。

## 14. 安全需求

- 不將付費 feed token 提交到 repo。
- HTTP request 不攜帶不必要 cookie。
- HTML polling 只針對明確登錄的官方頁面。
- 遵守合理 polling interval，避免對來源造成壓力。
- DB user 只需 read `sources`、insert/update `raw_items`、insert/update `source_health`。

## 15. 測試需求

單元測試：

- RSS item mapping。
- Atom item mapping。
- `dedupe_key` 生成。
- URL fallback。
- `ETag` / `Last-Modified` header 行為。
- HTML selector parsing。

整合測試：

- 使用 fixture feeds 寫入 test database。
- 驗證重複輪詢不重複入庫。
- 驗證 HTTP 304 不產生 item。
- 驗證 parse error 不影響其他 sources。

## 16. 驗收標準

- 能從 `sources` 動態讀取 RSS / HTML sources。
- 能穩定輪詢 V1 source 清單。
- 新 item 能寫入 `raw_items`。
- 重複 item 不重複入庫。
- `ETag` / `Last-Modified` 可正常使用。
- source health 可查詢最近輪詢與錯誤狀態。
- 單一 source 失敗不影響其他 source。
- 服務不做 AI 判斷、不做通知、不輸出交易建議。
