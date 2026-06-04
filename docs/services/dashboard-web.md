# dashboard-web 功能需求

## 1. 服務定位

`dashboard-web` 是 XAUUSD Event Radar 的前端操作介面，負責把 `dashboard-api` 提供的資料整理成可掃描、可回放、可排障的工作台。

V1 的 `dashboard-web` 不是交易下單介面，也不是行情預測介面。它的核心價值是讓使用者快速回答：

- 目前有哪些高相關消息？
- 哪些來源正在正常採集？
- 哪些 raw items 已被模型判定為事件？
- 哪些事件已觸發 Telegram / Pushover 通知？
- 是否有來源衝突、缺少確認或處理失敗？

## 2. V1 目標

- 提供新聞消息層的 read-only dashboard。
- 支援 Live Timeline 查看最新 raw items、processed items 與 events。
- 支援 S / A 級事件列表。
- 支援單一事件 detail view，包含來源、摘要、模型輸出、claim 與 alert 狀態。
- 支援 sources 與 source health 檢查。
- 支援 processing failed / pending 任務排障。
- 支援 alerts delivery 狀態檢查。
- 為後續 source 管理 UI 保留路由與元件邊界。

## 3. 非目標

V1 不包含：

- 交易建議、下單、倉位管理或風險參數。
- market chart 與 XAUUSD 行情疊加。
- MT5 / market data review。
- 多使用者、權限角色與完整登入系統。
- 複雜拖拉式 dashboard layout。
- WebSocket 強即時更新；V1 可先使用 TanStack Query polling。
- 在前端直接呼叫模型 API。

## 4. 技術棧

| 類別 | 選型 | 說明 |
| --- | --- | --- |
| Runtime | Node.js 22+ | 與 monorepo dev workflow 對齊 |
| Framework | React Router V7 | route module、loader/action boundary |
| Data fetching | TanStack Query | API cache、polling、retry、query invalidation |
| Styling | TailwindCSS V4 | utility-first styling |
| Component layer | DaisyUI V5 | table、badge、tabs、modal、dropdown、toast |
| Language | TypeScript | 型別約束 API response |
| Build tool | Vite | React Router V7 app build |
| Package manager | pnpm 或 npm | 依 monorepo 實作階段決定 |
| Container | Docker | HomeLab 部署 |

## 5. API 依賴

`dashboard-web` 只透過 `dashboard-api` 讀取資料。V1 不直接連 PostgreSQL。

目前前端已建立 API integration：

- `src/api/client.ts` 統一呼叫 `dashboard-api`。
- TanStack Query 負責 cache、polling 與 retry。
- Dev mode 讀取 `VITE_DASHBOARD_API_BASE_URL` / `VITE_DASHBOARD_API_TOKEN`。
- Production image 透過 runtime `/env.js` 讀取 `DASHBOARD_API_BASE_URL` / `DASHBOARD_API_TOKEN`，避免 image build 時綁死 HomeLab API URL。

必要 API：

```text
GET /health
GET /sources
GET /source-health
GET /raw-items
GET /raw-items/{raw_item_id}
GET /processing
GET /events
GET /events/{event_id}
GET /alerts
GET /stats/overview
```

後續 source 管理需要：

```text
POST /sources
PATCH /sources/{source_id}
POST /sources/{source_id}/test
POST /sources/{source_id}/backfill
```

## 6. V1 頁面範圍

### 6.1 Live Timeline

路由：

```text
/timeline
```

用途：

- 查看最新消息與事件。
- 快速判斷消息是否已被處理。
- 從 raw item 進入 detail。
- 從 event 進入 event detail。

主要元素：

- 頂部 filter bar：
  - keyword search
  - source type select，包含 All / Telegram / RSS / Atom / HTML polling
  - source select，選項顯示 `source_name`，查詢時使用 `source_id`
  - priority select，包含 All / P0 / P1 / P2 / P3
  - content category select，使用 `/taxonomy/categories` 的 controlled category dictionary
  - topic tag select，使用 `/taxonomy/tags` 的 semi-controlled tag dictionary
  - mentioned actor select，使用 `raw_items.mentioned_actors`
  - source group
- timeline card list：
  - published time
  - source name / source group
  - official level badge
  - priority badge
  - raw item id
  - source url / original url
  - title，若 raw item 有 `title` 則獨立顯示
  - summary block，優先使用 `summary_zh`，fallback 到 `summary_en`，再 fallback 到 `text_clean` / `text_raw`
  - full translation block，優先使用 `full_translation_zh`，fallback 到 `full_translation_en`；若兩者都沒有，顯示 `text_clean` / `text_raw`
  - translation status badge，顯示 `pending` / `completed` / `completed_truncated` / `skipped` / `failed`
  - content category badge、topic tags 與 mentioned actors，用於檢索與回看，不代表事件嚴重度
- auto-refresh toggle：
  - default enabled
  - interval 10-30 秒

### 6.2 High Impact Events

路由：

```text
/events
```

用途：

- 聚焦 S / A 級事件。
- 檢查事件摘要、來源、可信度與通知狀態。

主要元素：

- severity tabs：
  - All
  - S
  - A
  - B
- event table：
  - event time
  - severity
  - event type
  - source group
  - title
  - relevance score
  - confidence
  - confirmation state
  - alert sent status

### 6.3 Event Detail

路由：

```text
/events/:eventId
```

用途：

- 查看單一事件的完整上下文。
- 檢查模型輸出是否合理。
- 檢查相關 raw items、event claims 與 alerts。

主要區塊：

- event summary：
  - title
  - summary_zh
  - summary_en
  - full_translation_zh
  - full_translation_en
  - severity
  - confidence
  - relevance score
  - event type
  - impact channel
- source context：
  - source name
  - source group
  - official level
  - stance
  - requires confirmation
- raw items：
  - 原始文字
  - clean text
  - URL
  - published / ingested time
- model output：
  - model provider
  - model name
  - prompt/schema version
  - parsed JSON
  - error message if any
- claims：
  - claim direction
  - claim text
  - stance
  - confidence
- alerts：
  - channel
  - priority
  - delivery status
  - sent time
  - error message

### 6.4 Sources

路由：

```text
/sources
```

用途：

- 查看目前所有 Telegram / RSS / HTML sources。
- 檢查來源分類、官方程度、優先級與啟用狀態。
- 檢查近期採集量與錯誤。

主要元素：

- source card list：
  - name
  - handle_or_url
  - source_type
  - source_group
  - official_level
  - priority
  - reliability_score
  - enabled
  - archived state
  - alert policy summary
  - raw_items_24h / events_24h
  - last_raw_item_at
  - last_success_at
  - last_error
  - 1h / 24h ingest count
- filters：
  - source_type
  - source_group
  - priority
  - enabled
  - archived

V1 Source management 已包含：

- add source modal
- edit source modal
- enable / disable toggle
- archive action

Source 表單中可枚舉欄位必須使用 dropdown，不讓使用者自由輸入，例如：

- `source_type`
- `source_group`
- `official_level`
- `priority`
- `language`
- `translation_policy`
- `translation_priority`
- `telegram_min_severity`
- `pushover_min_severity`

V1 不提供 hard delete，archive 只會讓 source 退出 active registry，歷史資料仍保留外鍵關聯。

後續版本加入：

- test source action
- backfill source action
- collector registry auto-reload 狀態提示

### 6.5 Processing

路由：

```text
/processing
```

用途：

- 排查 `normalizer-classifier` 的 pending / running / failed 任務。
- 檢查模型結果與低相關消息過濾情況。
- 查看 AI Layer 1 / Layer 2 的 24h token usage、估算成本與 latency。

主要元素：

- AI usage summary cards：
  - 24h call count / failure count
  - input / output / total tokens
  - estimated cost
  - top model
- AI usage by layer：
  - `translation_summary`
  - `classification_reasoning`
  - call count
  - tokens
  - estimated cost
  - average latency
- processing table：
  - raw item id
  - source
  - stage
  - status
  - is_relevant
  - relevance_score
  - model provider
  - attempt_count
  - locked_at
  - completed_at
  - error_message

後續可加入：

- retry failed item
- mark ignored
- reprocess with another model route

### 6.6 Alerts

路由：

```text
/alerts
```

用途：

- 檢查通知是否已發送。
- 排查 Telegram Bot / Pushover delivery error。

主要元素：

- alerts table：
  - event
  - channel
  - priority
  - delivery_status
  - sent_at
  - error_message

### 6.7 Overview

路由：

```text
/
```

用途：

- 顯示系統總覽與快捷入口。

主要卡片：

- API health。
- Active sources count。
- Raw items in last 1h / 24h。
- Events in last 1h / 24h。
- S / A events count。
- Failed processing count。
- Failed alerts count。

## 7. Navigation

V1 使用左側或頂部 navigation，保持操作工具感，不做 landing page。

建議主選單：

```text
Overview
Timeline
Events
Sources
Processing
Alerts
```

後續加入行情層後再加入：

```text
Market Move Review
Claim Groups
Settings
```

## 8. 狀態與互動設計

### 8.1 Loading

- 使用 skeleton row，不用整頁 spinner。
- Table loading 不應造成 layout shift。

### 8.2 Empty State

Empty state 應直接說明目前沒有資料，例如：

```text
No events in selected range.
```

不在介面中加入冗長教學文案。

### 8.3 Error State

- API error 顯示 compact alert。
- 保留 retry button。
- 對 401 / 403 顯示 authentication / token issue。
- 對 5xx 顯示 backend unavailable。

### 8.4 Polling

V1 建議：

| View | Polling |
| --- | --- |
| Overview | 30 秒 |
| Timeline | 10-15 秒 |
| Events | 15-30 秒 |
| Sources | 30-60 秒 |
| Processing | 10-15 秒 |
| Alerts | 30 秒 |

## 9. UI 規範

Dashboard 是操作工具，不是 marketing site。

要求：

- 資訊密度要高，但保持可掃描。
- 使用 table、tabs、badge、drawer、modal、dropdown 等常見操作元件。
- 不使用 hero section。
- 不使用裝飾性 gradient / orb。
- 不使用卡片包卡片。
- 事件 severity 使用清楚 badge：
  - S：error / high contrast
  - A：warning
  - B：info
  - C：neutral
- source official level 使用 badge：
  - official
  - semi_official
  - unofficial
  - aggregator
- 長文字需要 truncation，detail view 再完整展示。
- 文字不能依 viewport width 動態縮放。

## 10. 安全需求

V1 HomeLab 內網部署可先使用簡單 API token。

前端需求：

- 透過 `DASHBOARD_API_BASE_URL` 指向 `dashboard-api`。
- 透過 `DASHBOARD_API_TOKEN` 或 reverse proxy 注入 auth header。
- 不在 repo 中保存 production token。
- 不在 browser local storage 保存高權限 secret；若 V1 只做 read-only，可接受短期 token。

後續公開網路或 Tailscale 外部存取時，應加入：

- Caddy / reverse proxy auth。
- HTTPS。
- session-based login 或 OAuth。
- CSRF strategy for write endpoints。

## 11. Docker 與部署

Image：

```text
ghcr.io/mrsuner/xauusd-trading-monitor/dashboard-web:<tag>
```

Production deployment：

- `dashboard-web` 由 Docker Compose 啟動。
- 對外暴露 HTTP port，或由 Caddy reverse proxy。
- 透過 environment variable 指向 `dashboard-api`。

必要 env：

```text
DASHBOARD_API_BASE_URL=/api
DASHBOARD_API_TOKEN=
```

Production image 會由 nginx 將 `/api/*` proxy 到 Compose network 內的 `dashboard-api:8080`。若前端部署在獨立主機或其他 reverse proxy 後面，也可以把 `DASHBOARD_API_BASE_URL` 改成外部可訪問的 API URL。

本機開發：

```text
cd apps/dashboard-web
npm install
npm run dev
```

或使用整體開發啟動：

```text
make dev
```

## 12. 驗收標準

V1 `dashboard-web` 完成時應滿足：

- 可以啟動並連到 `dashboard-api`。
- `/` 顯示 overview stats 與 API health。
- `/timeline` 可查詢 raw items / events。
- `/events` 可按 severity 查看事件。
- `/events/:eventId` 可查看事件 detail。
- `/sources` 可查看與管理 source registry、health、scoring、translation policy、alert policy。
- `/processing` 可查看 pending / failed processing。
- `/alerts` 可查看 delivery status。
- 所有列表支援基本 pagination。
- 所有主要查詢支援 loading / empty / error state。
- Docker image 可 build 並由 production compose 啟動。

## 13. 後續版本

V1 之後可逐步加入：

- Source test / backfill action。
- Claim Groups 專用頁面。
- Market Move Review。
- XAUUSD / DXY / US10Y / oil chart overlay。
- WebSocket / server-sent events。
- Replay mode。
- User preferences。
- Alert rule editor。
