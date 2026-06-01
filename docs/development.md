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
   - `event-router`，後續實作後加入
   - `alert-dispatcher`
   - `dashboard-api`
5. 用 `npm run dev` 背景啟動：
   - `dashboard-web`

`alert-dispatcher` 已加入 `make dev`。本機預設 `ALERT_DRY_RUN=true` 與 `DISPATCH_EXISTING_EVENTS_ON_START=false`，避免開發資料庫已有歷史事件時直接大量推送。`event-router` 實作後，歷史事件 route / backfill 保護應移到 `event-router`。

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

## 6. Cloud Model 成本保護

DB reset 後，Telegram collector 會依 `BACKFILL_HOURS` 與 `BACKFILL_LIMIT_PER_SOURCE` 回補歷史消息。這些消息會建立 `raw_item_processing` task，如果 `normalizer-classifier` 使用 `cloud_small`，可能產生大量 paid API call。

開發環境建議：

- 將 `infra/.env.dev` 的 `MAX_MODEL_CALLS_PER_RUN` 設為小數字，例如 `10` 或 `20`。
- 若只測 collector 入庫，暫時執行 `make dev-stop` 後單獨啟動 collector，或把 `MODEL_ROUTE` 切到 local endpoint。
- 測試新 channel 時把 `BACKFILL_LIMIT_PER_SOURCE` 降到 `20` 到 `50`。
- 若要完整測 workflow，先用少量 source / 少量 backfill 跑通，再調高上限。

`make dev` 會在 `infra/.env.dev` 未設定 `MAX_MODEL_CALLS_PER_RUN` 時預設套用 `20`，避免忘記設定後直接大量呼叫 cloud model。`MAX_MODEL_CALLS_PER_RUN=0` 代表不限制，較適合 production 或已確認成本可控的測試。
