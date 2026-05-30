# 本機開發流程

本機開發使用 `Makefile` 作為入口。Production / HomeLab 仍使用 `infra/.env.example` 與 `infra/docker-compose.prod.yml`。

## 1. 首次設定

```bash
cp infra/.env.dev.example infra/.env.dev
```

編輯 `infra/.env.dev`，填入 Telegram、model endpoint 與 API key。

## 2. 啟動全部本機服務

```bash
make dev
```

`make dev` 會執行：

1. 讀取既有 PID files，停止上一輪本機啟動的 application services。
2. 啟動 dev PostgreSQL。
3. 執行 Alembic migration。
4. 用 `uv run --project` 背景啟動：
   - `telegram-collector`
   - `rss-collector`
   - `normalizer-classifier`

目前 `alert-dispatcher` 與 `dashboard-api` 尚未有 runtime code，後續實作後會加入 `make dev`。

## 3. 查看狀態與 logs

```bash
make dev-status
make dev-logs
```

logs 會寫到：

```text
var/dev/logs/
```

PID files 會寫到：

```text
var/dev/pids/
```

## 4. 停止本機服務

```bash
make dev-stop
```

這會停止本機 application service processes，並停止 dev PostgreSQL container。PostgreSQL volume 不會被刪除。

## 5. 單獨操作 DB

```bash
make dev-db
make dev-migrate
```
