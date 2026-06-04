# Project Structure

## 1. 目標

本專案採用 monorepo 結構。V1 會包含多個 Python 後端服務、共用 Python package、Alembic migration、HomeLab production infra，以及文件。

目前已逐步補上服務程式碼與前端 app。目錄仍維持每個 service / app 可獨立 build、測試與部署的 monorepo 邊界。

## 2. 根目錄

```text
xauusd-trading-monitor/
  apps/
  db/
  docs/
  infra/
  packages/
  services/
```

## 3. Services

每個 service 都是獨立 build / deploy unit，未來各自擁有：

- `Dockerfile`
- `pyproject.toml`
- `src/<package_name>/`
- `tests/`

目前與後續已規劃 services：

```text
services/
  telegram-collector/
    src/telegram_collector/
    tests/

  rss-collector/
    src/rss_collector/
    tests/

  normalizer-classifier/
    src/normalizer_classifier/
    tests/

  event-router/
    src/event_router/
    tests/

  alert-dispatcher/
    src/alert_dispatcher/
    tests/

  telegram-channel-publisher/
    src/telegram_channel_publisher/
    tests/

  x-publisher/
    src/x_publisher/
    tests/

  public-syncer/
    src/public_syncer/
    tests/

  public-api/
    src/public_api/
    tests/

  dashboard-api/
    src/dashboard_api/
    tests/

  db-migrate/
```

### 3.1 telegram-collector

負責 Telethon / MTProto 採集 Telegram channels，寫入 `raw_items`。

### 3.2 rss-collector

負責 RSS / Atom / HTML polling，寫入 `raw_items`。

### 3.3 normalizer-classifier

負責預處理、模型路由、相關度判斷、事件建立與結果回寫。

### 3.4 event-router

負責讀取 `events`，集中決定事件應送往哪些出口，並寫入 `alerts`、`public_outbox` 與 `event_route_decisions`。

### 3.5 alert-dispatcher

負責 claim `alerts`，發送私人 Telegram Bot / Pushover 通知，並寫回 delivery tracking。

### 3.6 telegram-channel-publisher

後續公共出口服務，負責讀取 `public_outbox`，將 public-safe event 發布到公共 Telegram Channel。

### 3.7 x-publisher

公共出口服務，負責讀取 `public_outbox`，將 public-safe event 發布到 X。

### 3.8 public-syncer

HomeLab 公共網站同步服務，負責讀取 `public_outbox` 並透過 outbound HTTPS 把 public-safe payload 推送到 VPS `public-api`。

### 3.9 public-api

VPS 公共 API，負責接收 `public-syncer` ingest、寫入 public database，並提供 public website read API。

### 3.10 dashboard-api

V1 可選的 read-only debug API，供後續 Dashboard Web 與人工排障使用。

### 3.11 dashboard-web

V1 可選的前端操作台，供人工查看 timeline、events、sources、processing 與 alerts。

### 3.12 public-web

Cloudflare Pages 公共網站前端，負責展示 public-safe event stream，不包含內部 debug 與管理功能。

### 3.13 db-migrate

負責打包 Alembic migration，Docker Compose boot 時執行：

```text
alembic upgrade head
```

## 4. Shared Package

```text
packages/
  py-shared/
    src/xauusd_shared/
    tests/
```

`py-shared` 用於保存跨服務共用能力：

- settings / env parsing
- database helpers
- logging setup
- pydantic schemas
- dedupe key helpers
- model output schema
- retry / worker utility
- source metadata helpers

服務透過 path dependency 引用 `packages/py-shared`。

## 5. Database

```text
db/
  alembic.ini
  migrations/
    env.py
    script.py.mako
    versions/
```

目前只建立 `versions/` 目錄。實作階段再加入 Alembic 設定與 migration files。

Database 設計詳見：

- [Database Schema 設計](./database-schema.md)
- [Database Migration 策略](./database-migrations.md)

## 6. Apps

```text
apps/
  dashboard-web/
  public-web/
```

`dashboard-web` 是 HomeLab 私人前端操作台應用位置，用於查看 timeline、events、sources、processing 與 alerts。

`public-web` 是 Cloudflare Pages 公共網站前端應用位置，只展示 public-safe event stream。VPS Compose 不部署此 frontend。

前端技術棧固定為：

- React Router V7
- TanStack Query
- TailwindCSS V4
- DaisyUI V5

## 7. Infra

```text
infra/
  docker-compose.prod.yml
  docker-compose.public-api.yml
  .env.example
  .env.public-api.example
  README.md
  caddy/
  postgres/
  scripts/
  systemd/
```

`infra` 保存生產部署相關文件。HomeLab 使用 `docker-compose.prod.yml` 從 GHCR pull image 並啟動核心服務；VPS 使用 `docker-compose.public-api.yml` 啟動 public API 與 public database；public website frontend 由 Cloudflare Pages 部署。

GHCR namespace：

```text
ghcr.io/mrsuner/xauusd-trading-monitor/<service>:<tag>
```

## 8. Image Mapping

| Service | Image |
| --- | --- |
| `db-migrate` | `ghcr.io/mrsuner/xauusd-trading-monitor/db-migrate:<tag>` |
| `telegram-collector` | `ghcr.io/mrsuner/xauusd-trading-monitor/telegram-collector:<tag>` |
| `rss-collector` | `ghcr.io/mrsuner/xauusd-trading-monitor/rss-collector:<tag>` |
| `normalizer-classifier` | `ghcr.io/mrsuner/xauusd-trading-monitor/normalizer-classifier:<tag>` |
| `event-router` | `ghcr.io/mrsuner/xauusd-trading-monitor/event-router:<tag>` |
| `alert-dispatcher` | `ghcr.io/mrsuner/xauusd-trading-monitor/alert-dispatcher:<tag>` |
| `telegram-channel-publisher` | `ghcr.io/mrsuner/xauusd-trading-monitor/telegram-channel-publisher:<tag>` |
| `x-publisher` | `ghcr.io/mrsuner/xauusd-trading-monitor/x-publisher:<tag>` |
| `public-syncer` | `ghcr.io/mrsuner/xauusd-trading-monitor/public-syncer:<tag>` |
| `public-api` | `ghcr.io/mrsuner/xauusd-trading-monitor/public-api:<tag>` |
| `dashboard-api` | `ghcr.io/mrsuner/xauusd-trading-monitor/dashboard-api:<tag>` |
| `dashboard-web` | `ghcr.io/mrsuner/xauusd-trading-monitor/dashboard-web:<tag>` |
| `public-web` | Cloudflare Pages build artifact，V1 不需要 Docker image |

## 9. 仍待補強的內容

目前仍待補強：

- CI workflow。
- `public-web` Cloudflare Pages 實際部署設定。
- `public-web` browser tests。
- public claim group / related events。

這些會在後續實作階段逐步加入。
