# Infra

本目錄保存 XAUUSD Event Radar 的生產部署相關文件。

V1 部署目標是 HomeLab Docker Compose。所有服務 image 由開發機或 CI build 後推送到 GHCR，HomeLab 只負責 pull image 並啟動。

Compose 啟動時會先等待 PostgreSQL healthy，再執行 `db-migrate` one-shot migration job。migration 成功後，其他 application services 才會啟動。

公共發布服務預設不隨主 stack 啟動。`telegram-channel-publisher` 使用 Compose profile `public-publishing`，且 env 預設 `TELEGRAM_CHANNEL_PUBLISHER_ENABLED=false`、`TELEGRAM_CHANNEL_DRY_RUN=true`，避免未確認設定時直接向公共 Channel 發文。

## 文件

| File | 用途 |
| --- | --- |
| `docker-compose.prod.yml` | HomeLab production compose |
| `.env.example` | production env template |
| `scripts/docker-images.sh` | build / push production Docker images |

實際 secrets 放在：

```text
infra/.env
```

`infra/.env` 不應提交到 Git。

## 啟動

開發機 build 並推送 images：

```bash
IMAGE_TAG=$(git rev-parse --short HEAD) make docker-build
IMAGE_TAG=$(git rev-parse --short HEAD) make docker-push
```

Apple Silicon 開發機部署到 `linux/amd64` HomeLab 時：

```bash
IMAGE_PLATFORM=linux/amd64 IMAGE_TAG=$(git rev-parse --short HEAD) make docker-build-push
```

HomeLab server 拉取並啟動：

```bash
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml pull
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml up -d
```

若要啟動公共 Telegram Channel publisher：

```bash
docker compose --profile public-publishing --env-file infra/.env -f infra/docker-compose.prod.yml up -d telegram-channel-publisher
```

Dashboard UI 預設位於：

```text
http://<homelab-host>:5173
```

## 更新

```bash
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml pull
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml up -d
```

## 停止

```bash
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml down
```

不要在正常維護時刪除 volumes。
