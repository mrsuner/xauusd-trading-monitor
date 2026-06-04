# x-publisher 功能需求

## 1. 服務定位

`x-publisher` 是公共出口服務，負責把 HomeLab 中已判定可公開的事件發布到 X。

它與 `telegram-channel-publisher` 同屬 public publisher，但 X 的限制更嚴格：

- 字數限制更短。
- API 權限與費用更敏感。
- rate limit 與 duplicate policy 更嚴格。
- 公開擴散與截圖傳播風險更高。

因此 `x-publisher` 必須比 Telegram Channel 更保守。它只讀取 `event-router` 已寫入 `public_outbox` 的 public-safe payload，不直接把 `raw_items` 或內部 `events.summary_zh` 原樣發布出去，也不自行判斷事件是否應發布。

目標資料流：

```text
events / event_claims
  ↓
event-router
  ↓
public_outbox
  ↓
x-publisher
  ↓
X post
```

## 2. 目標

- 部署於 HomeLab。
- 讀取核心 PostgreSQL 的 `public_outbox`。
- 只處理 `approved_for_public = true` 的 public-safe event。
- 將 `public_outbox` payload 包裝成適合 X API 的短文。
- 支援中文優先，英文可選。
- 支援 source attribution，優先附一個 canonical source link。
- 支援 dedupe，避免同一事件重複發文。
- 支援 retry / backoff / rate limit。
- 記錄 X provider response、post id、sent time、status 與 error。
- 與 `alert-dispatcher`、`telegram-channel-publisher` 的策略與 delivery state 分離。

## 2.1 實作狀態

目前已完成第一版 runtime skeleton：

- `services/x-publisher` Python service。
- X API v2 `/tweets` provider。
- OAuth 1.0a user-context request signing。
- deterministic post formatter 與 260 字保守長度限制。
- `public_outbox` claim / sent / skipped / retry / failed 狀態更新。
- `X_PUBLISHER_DRY_RUN` 安全模式。
- 每小時 / 每日發布上限。
- Dockerfile、GHCR image build mapping、production Compose `public-publishing` profile。
- 單元測試。

尚未完成：

- 真實 X account production 發布驗證。
- OAuth 2.0 user token auth mode。
- Dashboard public outbox / X delivery audit UI。

## 3. 非目標

V1 不包含：

- 自動 thread 長文。
- 圖片、影片或 chart card 生成。
- 回覆、引用、轉發、刪文或編輯既有 post。
- 讀取 X timeline 或互動數據。
- 自動 hashtag growth / engagement optimization。
- 多帳號、多租戶或排程發文 UI。
- 發布未通過 public outbox 的 raw item。
- 發布完整原文或大量引用。

## 4. 技術棧

| 類別 | 選型 | 說明 |
| --- | --- | --- |
| Language | Python 3.12+ | 與後端服務一致 |
| Database | PostgreSQL 16+ | 讀 `public_outbox`，寫 delivery state |
| DB driver | psycopg 3 | row locking、JSONB、retry queue |
| HTTP client | httpx | X API |
| Config | pydantic-settings | env 管理 |
| Validation | pydantic | public payload / provider response schema |
| Logging | standard logging / structlog | structured logs |
| Packaging | uv | dependency 管理 |
| Container | Docker | HomeLab Compose 部署 |

Go 可作後續備選，但 V1 建議維持 Python。

## 5. X API 前置條件

X API 權限可能隨方案變動，實作前需要確認：

- 是否具備 write post 權限。
- 使用 OAuth 1.0a 還是 OAuth 2.0。
- App 是否綁定正確的 X account。
- rate limit 與每日 / 每月發文限制。
- 是否允許自動化發布金融/市場相關資訊。

建議設定與 Telegram Channel 分離：

```text
X_API_KEY
X_API_SECRET
X_ACCESS_TOKEN
X_ACCESS_TOKEN_SECRET
X_BEARER_TOKEN
```

實際需要哪些 secret 取決於最後採用的 X API auth flow。

## 6. 輸入與輸出

### 6.1 輸入

- `public_outbox`
- optional：`events`
- optional：`sources`
- optional：`event_claims`

V1 主要讀 `public_outbox`，不直接對 raw item 做 public copywriting。

### 6.2 輸出

- X post。
- `public_outbox.publish_status_x`。
- `public_outbox.published_x_at`。
- `public_outbox.last_error_x`。
- X `post_id`，建議保存於 delivery metadata。
- structured logs。

若後續新增 normalized delivery table，建議改寫：

```text
public_deliveries
  public_outbox_id
  platform = x
  status
  external_post_id
  attempts
  last_error
  sent_at
```

## 7. 發布條件

Route / publish eligibility 由 `event-router` 判斷。X publisher 可保留平台級最後防線，避免錯誤資料被發送。V1 建議：

```text
approved_for_public = true
publish_status_x in ('pending', 'retry')
severity in ('S', 'A')
public_summary_zh or public_summary_en exists
```

建議預設不發布：

- `severity = B`。
- 單一 aggregator / OSINT 來源且未確認。
- 缺少 public source link 的事件。
- 沒有明確 actor / topic 的 routine news。
- 內容可能引發誤解但沒有足夠上下文的事件。

允許例外：

- `severity = B` 但 `relevance_score` 很高，且來自官方 / 半官方 source。
- 已有多來源確認的 `market_squawk` 事件。

上述條件主要應在 `event-router` 實作；publisher 不應重新理解事件或呼叫 AI 做內容判斷。

## 8. Post Format

X V1 應採用一則短文，不做 thread。

建議格式：

```text
[S] 伊朗強硬派否認 Trump 的核協議說法。

市場先交易樂觀預期，但伊朗安全系統尚未確認，反轉風險升高。

Source: Tasnim
https://...
```

格式原則：

- 中文優先。
- 280 字以內。
- 若加入 URL 會消耗固定長度，formatter 必須預留空間。
- 不包含交易建議。
- 不寫「買入」、「賣出」、「做多」、「做空」。
- 不發布完整原文。
- 未確認消息必須使用清楚措辭，例如「未確認」、「單一來源」。
- hashtag 控制在 1-3 個，避免像 spam。
- V1 不使用 AI 針對 X 再次改寫內容；若後續加入 copy adapter，也只能做壓縮，不得新增事實。

建議 hashtag：

```text
#XAUUSD
#Gold
#Geopolitics
#Fed
#Iran
```

V1 可先固定最多 2 個 hashtag：一個資產主題、一個事件主題。

## 9. 長度控制

X formatter 必須 deterministic，不應依賴模型在發布時即時改寫。

建議策略：

1. 優先使用 `public_title_zh`。
2. 加入一行簡短 `public_summary_zh`。
3. 加入 source name。
4. 加入 canonical URL。
5. 若超長，依序裁剪：
   - topic tags。
   - source label。
   - summary。
   - title，最後保留 URL。

字數限制應保守設定：

```text
X_POST_MAX_CHARS=260
```

保留 20 字 buffer，避免 URL、emoji 或 CJK 計算差異造成 provider reject。

## 10. Claim 與並行控制

此服務 V1 建議單實例。若後續需要多實例，claim query 必須使用 row lock：

```text
SELECT ...
FROM public_outbox
WHERE publish_status_x IN ('pending', 'retry')
ORDER BY generated_at ASC
FOR UPDATE SKIP LOCKED
LIMIT 1
```

處理流程：

```text
claim public_outbox row
  ↓
set publish_status_x = 'sending'
  ↓
format short post
  ↓
send X API request
  ↓
success: set published_x_at, save external post id
  ↓
failure: set retry / failed, save error
```

## 11. Retry 與 Rate Limit

X rate limit 與 API 方案成本需要保守控制。

建議設定：

```text
X_PUBLISHER_MAX_PER_HOUR=10
X_PUBLISHER_MAX_PER_DAY=50
X_PUBLISHER_MAX_ATTEMPTS=4
X_PUBLISHER_RETRY_BACKOFF_SECONDS=300
X_PUBLISHER_MIN_SEVERITY=A
```

Provider error 分類：

| 錯誤 | 處理 |
| --- | --- |
| 400 validation / too long | formatter bug，標記 failed |
| 401 / 403 | auth 或權限問題，fatal |
| 409 / duplicate | 標記 skipped 或 sent_duplicate |
| 429 rate limited | 依 rate limit reset 延後 retry |
| 5xx / timeout | retry with backoff |

如果 X API 發文成本或限制過高，V1 可先保留 service 文檔與 schema，實作時將 `X_PUBLISHER_ENABLED=false`。

## 12. 設定

建議環境變數：

```text
SERVICE_NAME=x-publisher
DATABASE_URL=
X_PUBLISHER_ENABLED=false
X_API_KEY=
X_API_SECRET=
X_ACCESS_TOKEN=
X_ACCESS_TOKEN_SECRET=
X_BEARER_TOKEN=
X_POST_MAX_CHARS=260
X_PUBLISHER_MIN_SEVERITY=A
X_PUBLISHER_INCLUDE_B_EVENTS=false
X_PUBLISHER_MAX_PER_HOUR=10
X_PUBLISHER_MAX_PER_DAY=50
X_PUBLISHER_MAX_ATTEMPTS=4
X_PUBLISHER_DRY_RUN=true
PUBLISHER_POLL_INTERVAL_SECONDS=30
```

Production 初期應預設：

```text
X_PUBLISHER_ENABLED=false
X_PUBLISHER_DRY_RUN=true
```

直到確認 API 權限、費用與格式後再啟用。

## 13. 資料安全與發布風險

X 是公開擴散平台，風險高於 Telegram Channel。服務不得發布：

- `raw_items.text_raw` 完整內容。
- 大段新聞原文。
- Telegram private/internal message id。
- 私人 chat id。
- AI prompt、raw model response、AI usage cost。
- HomeLab internal URL。
- 未標記的傳聞或單源 OSINT。
- 任何看起來像交易指令的語句。

措辭原則：

- 使用「reported」、「said」、「claimed」、「unconfirmed」等來源歸屬語義。
- 對未確認事件明確標示確認狀態。
- 對市場影響使用「可能影響」、「市場正在關注」，避免斷言。

## 14. 測試策略

Unit tests：

- formatter 長度控制。
- URL / hashtag 裁剪。
- source attribution。
- severity / confirmation label。
- duplicate detection。
- provider error classification。

Integration tests：

- 使用 fake X API server。
- dry-run 不發文但寫 delivery decision。
- 429 rate limit retry。
- 400 too long 標記 failed。
- duplicate public_outbox 不重複發文。

Manual test：

- 使用測試 X account。
- 先 dry-run 生成 10 則 fixture。
- 人工確認文字無交易指令、無原文搬運、source link 正確。
- 小量實發 1-3 則低風險事件。

## 15. 驗收標準

- 只發布 `approved_for_public = true` 的資料。
- 同一 public event 不會重複發布到 X。
- post 不超過 `X_POST_MAX_CHARS`。
- post 不包含私人資料、完整原文或交易指令。
- 發布失敗可 retry，永久失敗可查 `last_error_x`。
- dry-run 可安全用於 production 首次部署。
- X 發布失敗不影響 Telegram Channel、public web sync 或私人 alert。
