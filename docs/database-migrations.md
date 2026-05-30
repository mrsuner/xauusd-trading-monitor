# Database Migration 策略

## 1. 目標

V1 需要支援未來 incremental database migration。建議採用輕量、穩定、Python 生態成熟的方案：

```text
Alembic + PostgreSQL + Docker Compose one-shot migration service
```

原因：

- 專案後端主要使用 Python。
- Alembic 成熟、輕量、可讀性高。
- 支援 incremental revision。
- 支援 upgrade / downgrade。
- 可在 Docker Compose boot 時先執行 migration。
- 不需要引入 Flyway / Liquibase 這類較重工具。

## 2. 設計原則

### 2.1 Migration 是部署流程的一部分

HomeLab 啟動順序：

```text
postgres
  ↓ healthy
db-migrate
  ↓ completed successfully
application services
```

`telegram-collector`、`rss-collector`、`normalizer-classifier`、`alert-dispatcher`、`dashboard-api` 都應等待 `db-migrate` 成功完成。

### 2.2 Migration job 必須是 one-shot

`db-migrate` 不應常駐。

成功：

```text
exit 0
```

失敗：

```text
exit non-zero
```

如果 migration 失敗，其他服務不應啟動，避免新程式碼對舊 schema 寫入錯誤資料。

### 2.3 Migration 只處理 schema 與必要 seed

Migration 可以包含：

- tables
- indexes
- constraints
- triggers
- extensions
- required seed data，例如初始 `sources`

Migration 不應包含：

- 大型資料修復 job
- 長時間 backfill
- 模型處理
- 外部 API call

大型資料修復應另做 maintenance job。

## 3. 工具選型

建議：

| 類別 | 選型 |
| --- | --- |
| Migration tool | Alembic |
| DB driver | psycopg 3 |
| Config | env var `DATABASE_URL` |
| Migration command | `alembic upgrade head` |
| Version table | `alembic_version` |

不建議 V1 使用：

- 手寫 `schema_migrations` runner，容易在 rollback、並發與錯誤處理上長期變複雜。
- Flyway / Liquibase，功能完整但對目前 Python-only V1 偏重。

## 4. Repo 結構建議

未來程式碼落地後建議：

```text
db/
  alembic.ini
  migrations/
    env.py
    script.py.mako
    versions/
      0001_initial_schema.py
      0002_seed_sources.py
```

或如果採 monorepo package：

```text
services/
  db-migrate/
    Dockerfile
db/
  migrations/
```

## 5. Docker Image 策略

V1 建議建立獨立 migration image：

```text
ghcr.io/mrsuner/xauusd-trading-monitor/db-migrate:<tag>
```

優點：

- Compose 語意清楚。
- 不依賴任一 app service image 的 command。
- 可以只包含 Alembic、DB driver 與 migration files。
- 未來 migration dependency 與 app runtime 可以分離。

替代方案：

```text
dashboard-api image + command: alembic upgrade head
```

這比較少 image，但會讓 migration 依賴 dashboard-api runtime。V1 可以接受，但長期建議獨立 `db-migrate` image。

## 6. Docker Compose 設計

Compose 中加入：

```yaml
db-migrate:
  image: ${IMAGE_REGISTRY}/${IMAGE_NAMESPACE}/db-migrate:${IMAGE_TAG}
  restart: "no"
  depends_on:
    postgres:
      condition: service_healthy
  environment:
    DATABASE_URL: ${DATABASE_URL}
  command: ["alembic", "upgrade", "head"]
```

其他服務：

```yaml
depends_on:
  postgres:
    condition: service_healthy
  db-migrate:
    condition: service_completed_successfully
```

注意：`service_completed_successfully` 需要 Docker Compose plugin 支援。若 HomeLab 的 Compose 版本太舊，替代方案是：

```bash
docker compose run --rm db-migrate
docker compose up -d
```

## 7. Migration 開發流程

新增 schema 變更：

```bash
alembic revision -m "add source health metadata"
```

編輯生成的 revision：

```text
upgrade()
downgrade()
```

本地測試：

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

部署：

```text
build db-migrate image
push to GHCR
HomeLab pull
docker compose up -d
```

## 8. Seed Data 策略

初始 sources 可以用 migration 或 seed script。

V1 建議：

- 初始固定 source registry 用 migration。
- 常變動 source 設定由後續 admin script / API 管理。

Seed migration 必須 idempotent：

```sql
insert into sources (...)
values (...)
on conflict (...) do update set ...
```

這樣重跑 migration 或環境重建時不會重複插入。

## 9. Rollback 策略

HomeLab production 不建議自動 downgrade。

建議：

- 每次部署前備份 PostgreSQL。
- migration 只自動 `upgrade head`。
- downgrade 只作為人工維護操作。
- destructive migration 必須拆成多階段。

Destructive migration 範例：

```text
release A: add new column
release B: app writes new column
release C: backfill / verify
release D: drop old column
```

## 10. Locking 與並發

正常 HomeLab 只會有一個 `db-migrate` job。

仍需注意：

- 不要同時在兩台機器跑 migration。
- CI 不應連 production DB 跑 migration。
- HomeLab update script 不應並發執行。

Alembic version table 可防止重複套用 revision，但不能替代部署層面的互斥。

## 11. 驗收標準

Migration 方案完成後應滿足：

- 新環境可從空 PostgreSQL 一次 `upgrade head` 建立 V1 schema。
- 已有環境可 incremental upgrade。
- `db-migrate` 成功後 app services 才啟動。
- migration 失敗時 app services 不啟動。
- migration image 從 GHCR pull。
- migration 不需要手動進 container 執行。
- seed sources 可重複執行且不重複插入。
