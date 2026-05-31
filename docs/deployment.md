# 部署與使用方式

## 1. 部署目標

XAUUSD Event Radar V1 將部署在 HomeLab 上，以 Docker Compose 啟動所有服務。

部署模式：

```text
development machine
  ↓ build docker images
GHCR
  ↓ pull images
HomeLab server
  ↓ docker compose up
V1 services
```

V1 只部署新聞消息層：

- PostgreSQL
- `db-migrate`
- `telegram-collector`
- `rss-collector`
- `normalizer-classifier`
- `alert-dispatcher`
- `dashboard-api`，可選但建議保留作為 debug API

V1 不部署：

- `mt5-collector`
- market data collector
- full dashboard web
- RabbitMQ / Kafka

## 2. 目錄約定

所有生產部署相關文件放在專案根目錄的 `infra` 目錄。

```text
infra/
  README.md
  docker-compose.prod.yml
  .env.example
```

未來可擴充：

```text
infra/
  caddy/
  postgres/
  systemd/
  scripts/
```

## 3. Image 發佈流程

所有服務以 Docker image 發佈到 GHCR。

建議 image 命名：

```text
ghcr.io/mrsuner/xauusd-trading-monitor/telegram-collector:<tag>
ghcr.io/mrsuner/xauusd-trading-monitor/db-migrate:<tag>
ghcr.io/mrsuner/xauusd-trading-monitor/rss-collector:<tag>
ghcr.io/mrsuner/xauusd-trading-monitor/normalizer-classifier:<tag>
ghcr.io/mrsuner/xauusd-trading-monitor/alert-dispatcher:<tag>
ghcr.io/mrsuner/xauusd-trading-monitor/dashboard-api:<tag>
```

Tag 策略：

| Tag | 用途 |
| --- | --- |
| `main` | main branch 最新 build |
| git SHA | 可回滾的 immutable build |
| semver | 手動 release，例如 `v0.1.0` |

HomeLab 部署建議使用 git SHA 或 semver，不建議長期使用 `latest`。

開發機或 CI 的典型流程：

```bash
docker build -t ghcr.io/mrsuner/xauusd-trading-monitor/telegram-collector:<tag> -f services/telegram-collector/Dockerfile .
docker push ghcr.io/mrsuner/xauusd-trading-monitor/telegram-collector:<tag>
```

其他服務同理：

```text
rss-collector
normalizer-classifier
alert-dispatcher
dashboard-api
db-migrate
```

實際 Dockerfile 路徑會在程式碼結構確定後固定。部署文件先約定 image 命名與發佈方式。

## 4. HomeLab Runtime

HomeLab server 需要：

- Docker Engine
- Docker Compose plugin
- GHCR pull 權限
- 對 Local LLM server 的內網連線能力，如果使用 local model route
- 對 Telegram / RSS / Pushover / OpenAI-compatible API 的 outbound network

Local LLM 由本地網路另一台 server 提供，不放在 V1 compose 內。

示例：

```text
normalizer-classifier
  ↓ HTTP
http://192.168.1.50:11434
  ↓
Local LLM server
```

V1 預設使用 cloud small model 做事件分類；Local LLM 保留給摘要、翻譯與低風險輔助處理。如果 Local LLM 後續品質足夠，仍可透過相同 OpenAI-compatible 介面切換或作 fallback。

## 5. Secret 管理

生產 secrets 不提交到 repo。

需要配置：

```text
POSTGRES_PASSWORD
TELEGRAM_API_ID
TELEGRAM_API_HASH
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
PUSHOVER_APP_TOKEN
PUSHOVER_USER_KEY
CLOUD_MODEL_API_KEY
API_TOKEN
```

V1 可使用 HomeLab 本地 `.env` 檔案：

```text
infra/.env
```

repo 只保留：

```text
infra/.env.example
```

## 6. Persistent Volumes

需要持久化：

| Path | 用途 |
| --- | --- |
| `postgres-data` | PostgreSQL data |
| `${TELEGRAM_SESSION_HOST_DIR}` | Telethon user session |

Telethon session 特別重要：

- 同一 session 不可多實例同時使用。
- `telegram-collector` replicas 必須固定為 1。
- session file 不提交到 Git。

## 7. Compose 啟動順序

建議啟動順序：

1. `postgres`
2. `db-migrate`，執行 `alembic upgrade head`
3. `telegram-collector`
4. `rss-collector`
5. `normalizer-classifier`
6. `alert-dispatcher`
7. `dashboard-api`

Docker Compose 使用 `depends_on.condition` 控制順序：application services 等待 PostgreSQL healthy，並等待 `db-migrate` `service_completed_successfully`。服務本身仍需實作 DB retry，不能只依賴 Compose 順序。

Migration 策略詳見 [Database Migration 策略](./database-migrations.md)。

## 8. 使用方式

### 8.1 首次部署

在 HomeLab server：

```bash
cd /opt/xauusd-trading-monitor
cp infra/.env.example infra/.env
mkdir -p infra/data/telegram-sessions
```

編輯 `infra/.env`，填入 secrets 與 image tag。

登入 GHCR：

```bash
docker login ghcr.io
```

拉取並啟動：

```bash
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml pull
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml up -d
```

### 8.2 更新部署

```bash
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml pull
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml up -d
```

### 8.3 查看狀態

```bash
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml ps
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml logs -f normalizer-classifier
```

### 8.4 停止服務

```bash
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml down
```

不要在正常維護時刪除 volumes。

## 9. normalizer-classifier 模型路由

`normalizer-classifier` 需要支援可切換模型路由。

V1 支援：

```text
MODEL_ROUTE=local_8b
MODEL_ROUTE=cloud_small
MODEL_ROUTE=claude_code_agent
```

### 9.1 Local LLM

Local LLM 適合：

- 低成本批量摘要。
- 翻譯波斯語、希伯來語、阿拉伯語等非英文內容。
- 低風險預處理與輔助資訊抽取。
- HomeLab 內網可用時。

V1 不建議 Local LLM 單獨負責最終事件分類、相關度分數、claim direction 或 severity input。這些欄位預設由 `cloud_small` 產生。

必要設定：

```text
LOCAL_MODEL_BASE_URL=http://192.168.1.50:11434
LOCAL_MODEL_NAME=...
```

### 9.2 Cloud Small Model

Cloud small model 適合：

- V1 預設事件分類。
- 高優先級來源。
- 相關度、claim direction、impact channel 與 confidence。
- Local LLM / nano summary 後的最終判斷。

必要設定：

```text
CLOUD_MODEL_BASE_URL=https://api.openai.com/v1
CLOUD_MODEL_API_KEY=...
CLOUD_MODEL_NAME=gpt-5.4-mini
CLOUD_MODEL_RESPONSE_FORMAT=json_object
```

`gpt-5.4-nano` 可作 summary / translation 輔助，但 V1 不作主分類模型。

### 9.3 Claude Code Agent SDK，備選

Claude Code Agent SDK 可作為高階模型能力備選，適合後續需要更複雜分析、工具調用或多步判斷的場景。

V1 對它的定位：

- 備選 route。
- 不作為必需依賴。
- 不阻塞 V1 核心閉環。
- 仍必須輸出相同的 JSON schema。
- 仍不得輸出交易指令。

## 10. 網路與 Port

建議只有必要服務對 HomeLab 內網暴露 port。

| Service | Port | Exposure |
| --- | --- | --- |
| PostgreSQL | 5432 | Docker network only，除非需要管理 |
| dashboard-api | 8080 | HomeLab / Tailscale only |
| collectors | none | 不暴露 |
| alert-dispatcher | none | 不暴露 |
| normalizer-classifier | none | 不暴露 |

若需要外部訪問 Dashboard API，建議後續使用：

- Tailscale
- Caddy reverse proxy
- HTTPS
- API token

## 11. 備份

V1 最低備份：

- PostgreSQL dump
- Telegram session files
- `infra/.env`

注意：

- `infra/.env` 與 Telegram session files 包含敏感資訊。
- 備份應加密保存。

## 12. 驗收標準

部署方式完成後應能達成：

- HomeLab 使用 `docker-compose.prod.yml` 一鍵啟動 V1 services。
- 所有 service image 從 GHCR pull。
- PostgreSQL data 持久化。
- Telethon session 持久化。
- `telegram-collector` 能連線並寫入 `raw_items`。
- `rss-collector` 能輪詢並寫入 `raw_items`。
- `normalizer-classifier` 能連到 Local LLM 或 cloud model。
- `alert-dispatcher` 能發送 Telegram / Pushover。
- `dashboard-api` 能查詢 health、events、alerts。
