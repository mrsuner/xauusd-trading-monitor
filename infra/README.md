# Infra

本目錄保存 XAUUSD Event Radar 的生產部署相關文件。

V1 部署目標是 HomeLab Docker Compose。所有服務 image 由開發機或 CI build 後推送到 GHCR，HomeLab 只負責 pull image 並啟動。

Compose 啟動時會先等待 PostgreSQL healthy，再執行 `db-migrate` one-shot migration job。migration 成功後，其他 application services 才會啟動。

## 文件

| File | 用途 |
| --- | --- |
| `docker-compose.prod.yml` | HomeLab production compose |
| `.env.example` | production env template |

實際 secrets 放在：

```text
infra/.env
```

`infra/.env` 不應提交到 Git。

## 啟動

```bash
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml pull
docker compose --env-file infra/.env -f infra/docker-compose.prod.yml up -d
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
