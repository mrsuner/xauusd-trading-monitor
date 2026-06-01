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

參考站點 `/Users/lukesun/Projects/ongoing/tickbase/apps/website` 目前使用 Astro 6 + TailwindCSS V4 + DaisyUI V5。`public-web` 可維持本專案既定的 React Router V7 技術棧，但應移植 TickBase website 的 design tokens、layout rhythm 與品牌語氣。若後續更重視 SEO / static rendering，也可重新評估是否改用 Astro；V1 先不因 UI 對齊而改變技術棧。

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

### 8.1 TickBase 品牌對齊

`news.thetickbase.com` 應看起來像 TickBase ecosystem 的一部分，而不是獨立產品。參考來源：

```text
/Users/lukesun/Projects/ongoing/tickbase/apps/website
```

可直接沿用的設計方向：

- Theme：DaisyUI custom themes `tickbase-dark` / `tickbase-light`。
- Dark default：near-black page background + gold primary。
- Brand colors：
  - dark `base-100 #0a0a0b`
  - dark `base-200 #141416`
  - dark `base-300 #1f1f23`
  - dark `base-content #fafaf9`
  - dark `primary #f5b301`
  - light `primary #c08a00`
  - success green for positive / fresh status
  - error red for negative / stale status
- Font：
  - sans：`Inter`
  - mono：`JetBrains Mono`
- Global texture：
  - subtle `bg-grid`
  - optional low-intensity `bg-gold-glow`
- Radius：
  - `rounded-field` about `0.5rem`
  - `rounded-box` about `0.75rem`
- Layout：
  - sticky top nav
  - `bg-base-100/80 backdrop-blur-md`
  - `border-base-300/60`
  - content max width `max-w-7xl`
  - horizontal padding `px-4 sm:px-6 lg:px-8`

不建議直接複製的部分：

- TickBase marketing homepage 的 large hero / pricing / API-key CTA。
- Dashboard-style dense tables。
- 任何「Get API key」或 billing 相關 CTA。

Public news site 的 first viewport 應直接展示事件流：

```text
sticky TickBase-style nav
  ↓
compact product header: TickBase News / Event Radar
  ↓
live public event feed
```

### 8.2 Navigation

Nav 應借鑑 TickBase website：

- 左側使用 TickBase wordmark 或 `TickBase News` variant。
- 桌面 nav 使用小字重、低對比連結。
- 手機使用 dropdown menu。
- 保留 theme toggle，localStorage key 可使用 `tickbase-theme`，與主站體驗一致。

建議 nav links：

```text
Latest
High Impact
Tags
About
Status
```

若需要回主站：

```text
TickBase → https://thetickbase.com
```

避免把 `news.thetickbase.com` 設計成產品轉換頁；它的任務是資訊可信度與可讀性。

### 8.3 Event Card Pattern

Event cards 應沿用 TickBase 的克制卡片語言：

```text
rounded-box border border-base-300 bg-base-200/40
hover:border-primary/40
```

Card 內容建議：

- top row：severity badge、confirmation state、event time。
- title：`text-lg font-semibold`，中文優先。
- summary：`text-sm text-base-content/70`。
- source links：小字、低對比、hover primary。
- tags：`font-mono text-xs` 或 DaisyUI badge。
- relevance：不要直接強調精確分數，可顯示 `High` / `Watch` / `Info`。

Severity visual mapping：

```text
S: primary / warning emphasis
A: primary outline
B: base-content/60 watch badge
C: muted info only
```

Confirmation state visual mapping：

```text
confirmed: success
partially_confirmed: warning
unconfirmed: neutral / base-content/50
contradicted: error
```

### 8.4 Page Structure

Public timeline page：

```text
Navbar
  compact header band with bg-grid
  filter toolbar
  event card list
  pagination / load more
Footer
```

Event detail page：

```text
Navbar
  event title + metadata
  summary panel
  source attribution list
  tags / actors
  related public events, optional
Footer
```

About page 應以 TickBase legal/docs pages 的排版語氣呈現：

- narrow readable content width。
- clear headings。
- muted explanatory copy。
- 明確寫出不是交易建議。

### 8.5 Implementation Notes

可以從 TickBase website 移植的檔案概念：

- `src/styles/global.css` 中的 DaisyUI theme tokens。
- `Layout` 的 metadata / OG pattern。
- `Navbar` 的 sticky / backdrop blur pattern。
- `Footer` 的 multi-column structure。
- `Logo` 的 wordmark / gold tick glyph 概念。
- `ThemeToggle` 的 light/dark persistence pattern。

實作時不要直接依賴另一個 repo 的 runtime path；應把需要的 token 與 component pattern 複製到本專案 `apps/public-web`，並保留來源說明。

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
