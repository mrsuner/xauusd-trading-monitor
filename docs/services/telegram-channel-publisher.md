# telegram-channel-publisher 功能需求

## 1. 服務定位

`telegram-channel-publisher` 是公共出口服務，負責把 HomeLab 中已判定可公開的事件發布到公共 Telegram Channel。

它不同於 `alert-dispatcher`：

- `alert-dispatcher` 面向個人 Telegram Bot / Pushover 通知。
- `telegram-channel-publisher` 面向公共訂閱者。

此服務不做資料採集、不做 AI 判斷、不直接讀取未去敏原文來生成公共內容，也不決定事件是否應發布。它只讀取 `event-router` 已寫入 `public_outbox` 的 public-safe payload，根據 Telegram API 要求做最後一層 deterministic formatting，並寫回 delivery state。

目標資料流：

```text
events / event_claims
  ↓
event-router
  ↓
public_outbox
  ↓
telegram-channel-publisher
  ↓
Telegram Channel
```

## 2. 目標

- 部署於 HomeLab。
- 讀取核心 PostgreSQL 的 `public_outbox`。
- 只處理 `approved_for_public = true` 的 public-safe event。
- 將 `public_outbox` payload 包裝為適合 Telegram Channel API 的 message。
- 支援中文優先，英文可選的雙語內容策略。
- 支援 source attribution 與原始來源連結。
- 支援 dedupe，避免同一 public event 重複發布。
- 支援 retry / backoff。
- 記錄 Telegram provider response、message id、sent time、status 與 error。
- 與 `alert-dispatcher` 的私人通知策略完全分離。

## 2.1 實作狀態

目前已完成第一版 runtime skeleton：

- `0010_public_outbox` 增量 migration。
- `services/telegram-channel-publisher` Python service。
- Telegram Bot API `sendMessage` provider。
- HTML message formatter 與 plain text fallback。
- `public_outbox` claim / sent / skipped / retry / failed 狀態更新。
- `TELEGRAM_CHANNEL_DRY_RUN` 安全模式。
- Dockerfile、GHCR image build mapping、production Compose `public-publishing` profile。
- 單元測試。

尚未完成：

- `event-router` 尚未實作，因此尚未自動從 `events` 建立 `public_outbox`。
- Dashboard public outbox review / approve UI。
- 真實 Telegram Channel production 發布驗證。

## 3. 非目標

V1 不包含：

- 多頻道多租戶發布。
- Telegram comments / discussion group 管理。
- 自動刪除或編輯已發布消息。
- 發布未通過 public outbox 的 raw item。
- 發布完整 `text_raw` 或大段媒體原文。
- 從 Telegram Channel 回收互動數據。
- 根據 Telegram feedback 反向調整事件評分。
- 付費訂閱或使用者權限模型。

## 4. 技術棧

| 類別 | 選型 | 說明 |
| --- | --- | --- |
| Language | Python 3.12+ | 與後端服務一致 |
| Database | PostgreSQL 16+ | 讀 `public_outbox`，寫 delivery state |
| DB driver | psycopg 3 | row locking、JSONB、retry queue |
| HTTP client | httpx | Telegram Bot API |
| Config | pydantic-settings | env 管理 |
| Validation | pydantic | public payload / provider response schema |
| Logging | standard logging / structlog | structured logs |
| Packaging | uv | dependency 管理 |
| Container | Docker | HomeLab Compose 部署 |

Go 可作後續備選，但 V1 建議維持 Python。

## 5. 前置條件

Telegram Channel 發布需要：

- `TELEGRAM_CHANNEL_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID` 或 `@channel_username`
- Bot 已加入目標 Channel。
- Bot 在 Channel 中具備 post message 權限。

Channel 應與私人通知 Bot 分離。即使 token 可以共用，也建議使用獨立 bot，避免私人通知與公共發布權限混雜。

## 6. 輸入與輸出

### 6.1 輸入

- `public_outbox`
- optional：`events`
- optional：`sources`
- optional：`event_claims`

V1 主要讀 `public_outbox`，只在需要補充 source attribution 或 debug 時讀其他表。

### 6.2 輸出

- Telegram Channel message。
- `public_outbox.publish_status_telegram`。
- `public_outbox.published_telegram_at`。
- `public_outbox.last_error_telegram`。
- Telegram `message_id`，建議保存於 delivery metadata。
- structured logs。

若後續新增 normalized delivery table，建議改寫：

```text
public_deliveries
  public_outbox_id
  platform = telegram_channel
  status
  external_message_id
  attempts
  last_error
  sent_at
```

## 7. 發布條件

V1 publisher 只處理符合以下條件的資料：

```text
approved_for_public = true
publish_status_telegram in ('pending', 'retry')
public_summary_zh or public_summary_en exists
```

Route / publish eligibility 由 `event-router` 判斷。Publisher 可保留平台級保護條件，避免錯誤資料被發送：

- `severity in ('S', 'A')` 預設可發布。
- `severity = 'B'` 只有高 relevance 或重要 source group 才發布。
- `source_group in ('osint_aggregator', 'market_squawk')` 且沒有確認來源時，預設不發布或標記為「未確認」。
- `public_source_links` 至少有一個可公開連結，否則降低發布優先級。

上述條件不應成為 publisher 的主要內容判斷邏輯；它們主要是最後防線。正常情況下，publisher 只處理已由 `event-router` queue 好的資料。

## 8. Message Format

Telegram Channel 可以承載較長內容，因此格式可以比 X 更完整。V1 建議採用：

```text
<severity badge> <public_title_zh>

<public_summary_zh>

來源：
1. <source name> <url>
2. <source name> <url>

狀態：confirmed / partially confirmed / unconfirmed
Tags: #iran #trump #fed
```

格式原則：

- 中文優先。
- 若 `public_summary_zh` 不存在，fallback 到 `public_summary_en`。
- 不包含交易建議，例如「做多」、「做空」、「入場」。
- 不發布完整原文。
- 每則消息都應能獨立理解。
- 未確認消息必須明確標示。
- 不使用 AI 針對 Telegram Channel 再次改寫內容。

可選策略：

- S 級事件可使用較醒目的開頭，例如 `[S]`。
- A 級事件使用 `[A]`。
- B 級事件若發布，使用 `[Watch]` 或 `[B]`。

避免使用過多 emoji，保持資訊平台風格。

## 9. Telegram Formatting

V1 建議使用 Telegram Bot API `sendMessage`：

```text
POST https://api.telegram.org/bot<TOKEN>/sendMessage
```

建議參數：

```json
{
  "chat_id": "<channel_id>",
  "text": "...",
  "parse_mode": "HTML",
  "disable_web_page_preview": false
}
```

格式策略：

- 優先使用 `HTML` parse mode，escape user/content text。
- source link 使用 `<a href="...">source</a>`。
- 若 provider 回報 parse error，fallback 到 plain text 重試一次。
- 對 URL 做 allowlist / validation，避免發布內部網址。

## 10. Claim 與並行控制

此服務可單實例運行。若後續需要多實例，claim query 必須使用 row lock：

```text
SELECT ...
FROM public_outbox
WHERE publish_status_telegram IN ('pending', 'retry')
ORDER BY generated_at ASC
FOR UPDATE SKIP LOCKED
LIMIT 1
```

處理流程：

```text
claim public_outbox row
  ↓
set publish_status_telegram = 'sending'
  ↓
send Telegram message
  ↓
success: set published_telegram_at, save provider response
  ↓
failure: set retry / failed, save error
```

## 11. Retry 與 Rate Limit

Telegram Channel 發布量通常低於個人通知，但仍需保守：

- `TELEGRAM_CHANNEL_MAX_PER_HOUR`
- `TELEGRAM_CHANNEL_MAX_ATTEMPTS`
- `TELEGRAM_CHANNEL_RETRY_BACKOFF_SECONDS`
- `TELEGRAM_CHANNEL_MIN_SEVERITY`

Provider error 分類：

| 錯誤 | 處理 |
| --- | --- |
| 400 parse error | fallback plain text 重試一次 |
| 401 / 403 | fatal，停止服務或標記 failed |
| 429 rate limited | 讀取 `retry_after`，延後 retry |
| 5xx / timeout | retry with backoff |

## 12. 設定

建議環境變數：

```text
SERVICE_NAME=telegram-channel-publisher
DATABASE_URL=
TELEGRAM_CHANNEL_BOT_TOKEN=
TELEGRAM_CHANNEL_ID=
TELEGRAM_CHANNEL_PARSE_MODE=HTML
TELEGRAM_CHANNEL_DISABLE_WEB_PAGE_PREVIEW=false
TELEGRAM_CHANNEL_MIN_SEVERITY=A
TELEGRAM_CHANNEL_INCLUDE_B_EVENTS=false
TELEGRAM_CHANNEL_MAX_PER_HOUR=30
TELEGRAM_CHANNEL_MAX_ATTEMPTS=5
TELEGRAM_CHANNEL_DRY_RUN=true
PUBLISHER_POLL_INTERVAL_SECONDS=10
```

Production 初期應預設 `TELEGRAM_CHANNEL_DRY_RUN=true`，觀察格式與頻率後再切換。

## 13. 資料安全

服務不得發布：

- `raw_items.text_raw` 完整內容。
- Telegram private/internal message id。
- 私人 Telegram chat id。
- Pushover token / user key。
- AI prompt、raw model response、AI usage cost。
- HomeLab internal URL。
- 未審核或未標示的 OSINT 單源傳聞。

`public_outbox` 之外的資料只可作為輔助上下文，不可覆蓋 public-safe payload 邊界。

## 14. 測試策略

Unit tests：

- message formatter。
- HTML escaping。
- source link rendering。
- severity / confirmation label。
- retry decision。
- provider error classification。

Integration tests：

- 使用 fake Telegram API server。
- dry-run 不發送但寫 delivery decision。
- parse error fallback plain text。
- 429 retry_after 處理。
- duplicate public_outbox 不重複發布。

Manual test：

- 使用測試 Channel。
- 先發布 3-5 則 S/A/B fixture。
- 確認手機端與桌面端顯示可讀。
- 確認 source links 可點擊。

## 15. 驗收標準

- 只發布 `approved_for_public = true` 的資料。
- 同一 public event 不會重複發布到 Channel。
- Telegram message 不包含私人資料或完整原文。
- 發布失敗可 retry，永久失敗可查 `last_error_telegram`。
- dry-run 可安全用於 production 首次部署。
- `alert-dispatcher` 是否啟用不影響公共 Channel 發布。
