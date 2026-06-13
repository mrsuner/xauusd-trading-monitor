# Public Website 架構規劃

## 1. 定位

Public Website 是 XAUUSD Event Radar 的公共資訊出口，用於展示已由 HomeLab 處理、去敏、分級並核准公開的事件流。

它不是 SaaS 多租戶產品，也不提供交易訊號、下單、私人通知設定或內部工作台能力。它的目標是讓外部讀者以低摩擦方式追蹤高價值事件：

- Trump / Iran / IRGC / Fed / CENTCOM / Israel 等關鍵事件。
- 事件確認狀態與來源歸屬。
- 公共安全摘要。
- source links。
- tags / categories。
- 後續可加入 conflict / claim group 的公共版本。

## 2. 部署邊界

公共網站採用 HomeLab 產生內容、VPS 承載 public API、Cloudflare Pages 承載前端網站的模式。

```text
HomeLab:
  collectors
  normalizer-classifier
  event-router
  public_outbox
  public-syncer
  telegram-channel-publisher
  x-publisher

VPS:
  public-api
  public-postgres
  Cloudflare Tunnel

Cloudflare Pages:
  public-web
```

關鍵原則：

- HomeLab 不對公網開 inbound port。
- HomeLab 與 VPS 不建立內部網路。
- HomeLab 只透過 outbound HTTPS 把 public-safe payload 推送到 VPS。
- VPS 不讀 HomeLab DB。
- VPS 不保存 raw item、prompt、AI raw response、私人通知設定、Telegram session 或內部 debug 資料。
- Cloudflare Tunnel 只部署在 VPS 側，用於保護 public API，不作為 HomeLab 與 VPS 的內網通道。`public-web` 由 Cloudflare Pages 部署到 `news.thetickbase.com`。

## 3. 目標資料流

```text
raw_items
  ↓
normalizer-classifier
  ↓
events / event_claims
  ↓
event-router
  ↓
public_outbox
  ↓
public-syncer
  ↓ HTTPS ingest
public-api
  ↓
public-postgres
  ↓
public-web on Cloudflare Pages
```

公共 Telegram Channel 與 X publisher 仍部署在 HomeLab：

```text
public_outbox
  ├── telegram-channel-publisher → Telegram Channel
  ├── x-publisher                → X
  └── public-syncer              → VPS public-api
```

原因：

- publisher 可以直接讀 HomeLab 中央 DB 與 `public_outbox`。
- 不需要讓 VPS 回調 HomeLab。
- 不需要在 VPS 複製內部 API。
- 不同平台的格式、rate limit、retry 與錯誤處理可以各自獨立。

## 4. Public Payload Contract

Public Website 不應直接依賴 HomeLab 的完整 `events` schema。V1 建議建立版本化 payload contract：

```json
{
  "schema_version": "public_event.v1",
  "idempotency_key": "event:<event_id>:v1",
  "upstream_event_id": "uuid",
  "event_time": "2026-06-01T10:00:00Z",
  "generated_at": "2026-06-01T10:00:05Z",
  "severity": "A",
  "relevance_score": 88,
  "confirmation_state": "partially_confirmed",
  "public_title_zh": "...",
  "public_summary_zh": "...",
  "public_title_en": "...",
  "public_summary_en": "...",
  "translations": [
    {
      "language": "en",
      "title": "...",
      "summary": "..."
    },
    {
      "language": "zh-Hant",
      "title": "...",
      "summary": "..."
    }
  ],
  "public_source_links": [
    {
      "source_name": "Tasnim",
      "url": "https://..."
    }
  ],
  "topic_tags": ["iran", "trump", "xauusd"],
  "content_category": "geopolitics",
  "mentioned_actors": ["Iran", "Trump"],
  "route_metadata": {
    "public_route_score": 88,
    "generated_by": "event-router"
  }
}
```

V1 可以直接由 `public_outbox` 映射出 payload。後續若 public website 需要更多欄位，應新增 `schema_version`，避免破壞已部署的 VPS API。

### 4.1 Raw Items Feed Contract, Planned

`public_event.v1` 只承載事件級 public summary。若公共網站需要像 HomeLab Event Radar Timeline 一樣展示「原始資料源」feed，應新增獨立 contract，而不是把 raw item 內容混入 event payload。

具體實施方案：見 [Public Raw Items Feed Implementation Plan](public-raw-items-feed-implementation-plan.md)。

Planned contract:

- `schema_version`: `public_raw_item.v1`
- ingest endpoint: `POST /ingest/raw-items`
- read endpoints: `GET /raw-items`, `GET /raw-items/{public_raw_item_id}`
- idempotency key: `raw_item:<raw_item_id>:v1`
- VPS tables: `public_raw_items`, `public_raw_item_translations`; extend existing `public_ingest_requests` with raw item ingest metadata so HMAC nonce replay protection remains global.

Allowed public-safe fields:

- upstream raw item id, source name/type/group, public source URL.
- published / ingested / edited timestamps.
- title, cleaned original content, summary, full translation.
- translation rows by language.
- content category, topic tags, mentioned actors.
- source text / translation character counts and truncation flags.

Required protections:

- Keep this feed separate from `public_events` so event summary sync remains stable.
- Scrub Telegram private channel/chat/message metadata before ingest.
- Do not sync `raw_json`, AI prompt, AI raw response, token usage, private notification state, internal HomeLab URLs, API keys, or collector credentials.
- Enforce payload size limits and deterministic truncation for long source text/full translations.

### 4.2 Translation Compatibility Contract

Public translations are display-only public copy. They are separate from raw UI translations and must not be used as AI Layer 2 reasoning input.

Compatibility rules:

- `schema_version` stays `public_event.v1` while adding optional `translations: [{ language, title, summary }]`.
- Legacy fields `public_title_zh`, `public_summary_zh`, `public_title_en`, and `public_summary_en` remain in the payload and response for backward compatibility.
- `idempotency_key` stays `event:<event_id>:v1`; do not switch to a v2 key without a separate canonical upstream identity/upsert plan.
- Public read requests use `lang=<BCP-47 language-code>`.
- Read fallback order is requested language, then English (`en`), then the first available public language.
- Response `language` must identify the language actually used after fallback.
- `available_languages` is derived from translation rows. Legacy fields are only a fallback/backfill source.
- `raw_item_translations` is not synced to the public database and is not exposed through the public API.
- `public_outbox_translations` and `public_events_translations` store public-safe copy that can differ from raw UI translations.

## 5. Public Data Boundary

允許同步：

- public title / summary。
- severity。
- relevance score。
- confirmation state。
- source name。
- public source URL。
- topic tags。
- content category。
- mentioned actors。
- upstream event id。
- generated / event time。

禁止同步：

- `raw_items.text_raw` 完整內容。
- 大段新聞原文或完整翻譯。
- Telegram internal id、channel id、private chat id。
- Telethon session、bot token、API key。
- AI prompt、AI raw response、AI usage cost。
- HomeLab internal URL。
- 私人通知策略與 delivery record。

若需要展示更完整上下文，應由 `event-router` 或後續 public content adapter 先生成 public-safe summary，不應讓 public-api 直接讀內部資料。

Planned `public_raw_item.v1` 是此邊界的受控例外：只能同步 scrub 後且有字數上限的 `raw_items.text_clean`、summary 與 full translation display copy；仍不得同步 `text_raw`、`raw_json`、AI prompt/raw response 或任何私有 collector metadata。

## 6. VPS Public Database

VPS public database 應簡化，不複製 HomeLab 完整 schema。

V1 建議表：

```text
public_events
  id
  upstream_event_id
  idempotency_key
  schema_version
  event_time
  generated_at
  received_at
  severity
  relevance_score
  confirmation_state
  public_title_zh
  public_summary_zh
  public_title_en
  public_summary_en
  public_source_links
  topic_tags
  content_category
  mentioned_actors
  route_metadata
  is_visible
  created_at
  updated_at

public_ingest_requests
  id
  idempotency_key
  upstream_event_id
  request_hash
  status
  error_message
  received_at
```

後續若要展示 claim group，可新增：

```text
public_event_claims
  id
  public_event_id
  source_name
  claim_direction
  claim_text_zh
  claim_text_en
  confidence
  created_at
```

## 7. Security Model

`public-api` ingest endpoint 應採用：

- HTTPS only。
- HMAC signature 或 API key。
- timestamp header。
- nonce 或 idempotency key replay protection。
- payload size limit。
- rate limit。
- request hash audit。
- constant-time signature compare。

建議 headers：

```text
X-XER-Key-Id
X-XER-Timestamp
X-XER-Nonce
X-XER-Signature
Idempotency-Key
```

簽名內容：

```text
timestamp + "\n" + nonce + "\n" + idempotency_key + "\n" + sha256(body)
```

V1 若要降低實作成本，可以先支援單一 `PUBLIC_INGEST_API_KEY`，但應保留 HMAC 設計位置。

## 8. Public Website UI

Public Website 的第一版應是資訊流，而不是 dashboard。

Public Website 將部署於：

```text
news.thetickbase.com
```

它需要與 TheTickBase 主站保持一致的品牌語言。主站參考程式碼：

```text
/Users/lukesun/Projects/ongoing/tickbase/apps/website
```

建議頁面：

- `/`：最新公共事件流。
- `/events/:id`：事件詳情。
- `/tags/:tag`：tag filtered timeline。
- `/about`：資料來源與免責說明。

第一版 UI 重點：

- mobile-first。
- card list。
- severity / confirmation state badge。
- source attribution。
- compact source links。
- tags filter。
- 不顯示內部 scores 過多細節，但可顯示 relevance band。

品牌對齊重點：

- 沿用 TickBase 的 near-black + gold visual language。
- 使用 DaisyUI custom themes `tickbase-dark` / `tickbase-light`。
- 預設 dark theme。
- 使用 `Inter` 作為 sans font、`JetBrains Mono` 作為 numeric / tag / source metadata font。
- navbar 採用 sticky + translucent background + backdrop blur。
- cards 使用 `rounded-box border border-base-300 bg-base-200/40` 的克制資訊平台樣式。
- 可使用 subtle `bg-grid` 作為 header / filter band 背景。
- 不使用主站 marketing homepage 的 large hero / pricing CTA；新聞站首屏直接展示事件流。
- footer 可沿用 TickBase 主站的 column layout，但文案改為 news / event radar / disclaimer。

Public Website 設計細節詳見 [public-web 功能需求](./services/public-web.md)。

## 9. 實作順序

建議順序：

1. `public-api` ingest + public database migration。
2. `public-syncer` dry-run + ingest integration。
3. `public-web` event list + detail，部署到 Cloudflare Pages。
4. VPS Compose + Cloudflare Tunnel deployment docs for `public-api`。
5. 加入 public claim group。
6. 加入 dashboard 中的 public sync status review。

## 10. 驗收標準

- HomeLab 不開 inbound port 也能同步 public event。
- Cloudflare Pages public website 只展示 public-safe payload。
- 同一 `idempotency_key` 重複送達不會產生重複事件。
- public-api 錯誤不影響 HomeLab 採集、AI 處理與私人通知。
- Cloudflare Tunnel 可對外提供 public-api；public-web 由 Cloudflare Pages 對外提供。
- public-web 不包含 raw item、prompt、token usage、私人通知或內部 URL。
