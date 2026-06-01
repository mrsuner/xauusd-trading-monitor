# public-web 功能需求

## 1. 服務定位

`public-web` 是部署在 VPS 的公共網站前端，用於展示 `public-api` 提供的 public-safe event stream。

它不同於 HomeLab `dashboard-web`：

- `dashboard-web` 是私人工作台，包含 debug、processing、source management、AI usage。
- `public-web` 是公開資訊頁，只展示去敏後事件。

## 2. 目標

- 提供 public timeline。
- 提供 event detail page。
- 支援 severity、tag、category、confirmation state filter。
- 顯示 source attribution 與 source links。
- mobile-first。
- 不暴露內部資料。
- 可由 Cloudflare Tunnel 對外提供。

## 3. 非目標

V1 不包含：

- 登入、多租戶、付費訂閱。
- source 管理。
- processing / AI usage / alert delivery debug。
- raw item 全文閱讀。
- 交易建議或下單功能。
- 即時 WebSocket。
- 複雜 chart 或行情疊加。

## 4. 技術棧

| 類別 | 選型 | 說明 |
| --- | --- | --- |
| Runtime | Node.js 22+ | 與現有 frontend 對齊 |
| Framework | React Router V7 | public routes |
| Data fetching | TanStack Query | API cache / polling |
| Styling | TailwindCSS V4 | utility-first styling |
| Component layer | DaisyUI V5 | badge、card、dropdown、pagination |
| Language | TypeScript | API response typing |
| Build tool | Vite | app build |
| Container | Docker | VPS Compose 部署 |

## 5. API 依賴

`public-web` 只呼叫 `public-api`：

```text
GET /health
GET /events
GET /events/{public_event_id}
GET /tags
GET /categories
GET /stats/overview
```

不得呼叫 HomeLab `dashboard-api`，不得直接連 PostgreSQL。

## 6. 頁面範圍

### 6.1 Public Timeline

路由：

```text
/
/events
```

主要內容：

- event card list。
- severity badge。
- confirmation state badge。
- event time。
- public title。
- public summary。
- source links。
- topic tags。
- category。
- pagination 或 load more。

Filters：

```text
severity
confirmation_state
tag
category
q
from
to
```

UI 原則：

- card list，不使用 dense debug table。
- 中文優先，英文 fallback。
- 來源連結清晰，但不堆疊過多 metadata。
- relevance score 可轉為 band，例如 `High` / `Watch`，避免讓 public user 過度解讀精確數字。

### 6.2 Event Detail

路由：

```text
/events/:eventId
```

主要內容：

- public title。
- public summary。
- severity。
- confirmation state。
- event time。
- source links。
- topic tags。
- category。
- mentioned actors。
- route metadata 的 public-safe subset。

後續可加入：

- public claim group。
- related events。
- timeline around event。

### 6.3 Tag Page

路由：

```text
/tags/:tag
```

用途：

- 展示單一 topic tag 的事件流。
- 例如 `iran`、`trump`、`fed`、`xauusd`。

### 6.4 About Page

路由：

```text
/about
```

內容：

- 系統定位。
- 資料來源說明。
- 事件分級說明。
- 確認狀態說明。
- 免責聲明。
- 不提供交易建議。

## 7. Content Policy

Public Web 應避免：

- 「買入」、「賣出」、「做多」、「做空」等交易指令語句。
- 未標記的傳聞。
- 大段原文引用。
- 任何內部 ID 或 private delivery 狀態。

未確認事件應清楚標示：

```text
unconfirmed
partially confirmed
confirmed
contradicted
```

## 8. Design Direction

公共網站應是資訊平台，不是內部工具。

建議風格：

- 清晰、克制、資訊密度適中。
- 首屏直接展示事件流，不做 marketing hero。
- 不使用過重的裝飾圖形。
- mobile card 先行。
- desktop 使用 constrained content width。
- 重要事件使用 severity badge，而不是誇張視覺警報。

## 9. 設定

```text
PUBLIC_API_BASE_URL=https://api.example.com
PUBLIC_WEB_DEFAULT_LOCALE=zh
PUBLIC_WEB_REFRESH_SECONDS=60
PUBLIC_WEB_SITE_NAME=XAUUSD Event Radar
PUBLIC_WEB_CANONICAL_URL=https://example.com
```

若 public-web 與 public-api 在同一 VPS Compose network，可由 nginx / Caddy 反向代理：

```text
/api → public-api
/    → public-web
```

## 10. SEO 與分享

V1 可先支援基本 metadata：

- page title。
- description。
- Open Graph title / description。
- canonical URL。

後續若需要更好的分享卡片，可以加入 SSR / prerender，但 V1 不強制。

## 11. 測試策略

Unit tests：

- API client。
- formatter fallback。
- filter state。
- event card rendering。

Browser tests：

- mobile timeline。
- desktop timeline。
- event detail。
- filter behavior。
- empty state。
- API error state。

## 12. 驗收標準

- public-web 可只透過 public-api 展示事件列表。
- mobile 與 desktop layout 不重疊、不溢出。
- 不顯示 raw item、prompt、AI usage、private alert、Telegram session 或 HomeLab URL。
- source links 可點擊。
- filters 可用。
- About page 清楚說明非交易建議。
