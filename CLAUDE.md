# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

XAUUSD Event Radar — an event-radar system for gold (XAUUSD) trading. It does **not** predict direction or give trade advice. It ingests geopolitical / macro news from many sources, layers them by source authority and stance, scores relevance, and surfaces **conflicts between power systems** (e.g. Trump claims a deal vs. Iran's IRGC denies it). V1 scope is the news layer only: collection → raw storage → preprocessing → model relevance judgement → notification. Market-data reverse lookup (`mt5-collector`, `market_snapshots`) is explicitly out of V1.

The authoritative product spec is `docs/overview.md`; scope boundaries are in `docs/final-target-and-v1-scope.md`. Read these before changing classification, severity, or source-layering logic.

## Language & branch conventions (from AGENTS.md)

- Chat/explanation output: **Traditional Chinese**. Code, identifiers, comments, commit messages, commands, paths, API names, error messages: **English**.
- Work on `develop` or feature branches off `develop`. **Never** commit to `main` unless the user explicitly asks for a release commit.

## Architecture

Monorepo of independent Python backend services + one React frontend, coordinated through a single PostgreSQL database. **PostgreSQL is the source of truth**; there is no message broker. Services communicate by writing rows and polling a work queue.

Data flow (V1):
```
telegram-collector / rss-collector
  → raw_items (+ raw_item_processing pending row)
  → normalizer-classifier  (polls the queue)
  → events / event_claims  (+ translation/summary fields on raw_items)
  → dashboard-api → dashboard-web
```
`alert-dispatcher` is specified but has **no runtime code yet** (not in `make dev`).

Key architectural facts:
- **Work queue, not pub/sub.** `normalizer-classifier` claims tasks from `raw_item_processing` using `SELECT ... FOR UPDATE SKIP LOCKED`, so multiple workers/concurrency are safe. Each task carries `status / attempt_count / next_retry_at / locked_by / locked_at / error_message` for crash recovery. See `services/normalizer-classifier/src/normalizer_classifier/worker.py` and `db.py`.
- **Collectors don't judge.** Collectors only write `raw_items` / `source_health` and enqueue processing rows. All classification, relevance scoring, summarization, and claim direction is done by `normalizer-classifier`.
- **Rules-first, AI-assist.** Relevance/severity start from an explainable prefilter (keyword/actor/source-priority scoring in `normalization.py`); only items passing the prefilter are sent to a model. Severity is S/A/B/C.
- **No shared code yet.** Despite `packages/py-shared/` and `docs/project-structure.md`, that package is currently empty (`.gitkeep` only). **Each service vendors its own `models.py`, `db.py`, `settings.py`.** When editing shared-looking concepts (e.g. `SourceMetadata`, `RawItem`), changes do **not** propagate across services automatically — update each service that needs it.

### Model routing & cost guards (normalizer-classifier)

`settings.py` defines multiple OpenAI-style endpoints selected by route: `local`, `cloud_small`/cloud, `openrouter`, plus a separate **translation/summary** model chain (primary → fallback → paid fallback). The client is `model_client.OpenAIStyleModelClient` (plain `httpx`, OpenAI chat-completions shape).

Because a DB reset triggers Telegram backfill that can enqueue many items, there are **hard budget caps** to prevent runaway paid API calls, enforced in `worker.py`:
- `MAX_MODEL_CALLS_PER_RUN` (umbrella), `MAX_CLASSIFICATION_CALLS_PER_RUN`, `MAX_TRANSLATION_CALLS_PER_RUN`, `MAX_TRANSLATION_PAID_FALLBACK_CALLS_PER_RUN`. `0` = unlimited.
- `make dev` injects defaults (`20`) when unset. Keep these low in dev. See `docs/development.md` §6.

## Common commands

Local dev is driven by the `Makefile`. Tooling: **`uv`** for Python (per-service projects), **`npm`** for the web app, **Docker** for PostgreSQL.

```bash
make dev          # stop old app processes → start dev Postgres → alembic upgrade head
                  #   → background-run collectors + normalizer + dashboard-api (uv) + web (npm)
make dev-status   # show running dev services
make dev-logs     # tail var/dev/logs/*.log   (PIDs in var/dev/pids/)
make dev-stop     # stop app processes + dev Postgres container (volume preserved)
make dev-db       # just start dev Postgres
make dev-migrate  # alembic upgrade head against dev env
make test         # run pytest for all four services
make web-build    # tsc -b && vite build
make compose-config  # validate prod compose file
```

First-time setup: `cp infra/.env.dev.example infra/.env.dev` then fill in Telegram + model endpoint + API keys.

### Tests

There is **no linter/formatter configured** (no ruff/black/mypy). `pytest` with `asyncio_mode = "auto"` per service.

```bash
# all services
make test
# one service
cd services/normalizer-classifier && uv run --group dev pytest
# one test
cd services/normalizer-classifier && uv run --group dev pytest tests/test_normalization.py::test_name
```

### Database migrations (Alembic)

Migrations live in `db/migrations/versions/` (config `db/alembic.ini`), and are a **deploy step**: in prod the one-shot `db-migrate` service runs `alembic upgrade head` and must succeed before app services start. Migrations are schema + idempotent seed only (no backfills / model calls / external APIs). Seed `sources` with `INSERT ... ON CONFLICT DO UPDATE`.

```bash
uv run --group db alembic -c db/alembic.ini revision -m "describe change"
uv run --group db alembic -c db/alembic.ini upgrade head
uv run --group db alembic -c db/alembic.ini downgrade -1   # local testing only
```
Destructive changes must be split across releases (add → write → backfill → drop). See `docs/database-migrations.md` and `docs/database-schema.md`.

## Frontend (apps/dashboard-web)

Read-only operator dashboard. Stack is fixed: **React 19, React Router 7, TanStack Query, TailwindCSS v4, DaisyUI v5, Vite, TypeScript**. Pages: Overview, Timeline, Events, EventDetail, Sources, Processing, Alerts. API access via `src/api/client.ts` using `VITE_DASHBOARD_API_BASE_URL` + `VITE_DASHBOARD_API_TOKEN` (derived from `DASHBOARD_API_BASE_URL` / `DASHBOARD_API_TOKEN` in dev).

```bash
cd apps/dashboard-web
npm run dev        # vite dev server (also started by `make dev`)
npm run build      # tsc -b && vite build
npm run typecheck  # tsc -b
```

## Deployment

HomeLab via Docker Compose pulling images from GHCR: `ghcr.io/mrsuner/xauusd-trading-monitor/<service>:<tag>`. Boot order: `postgres` (healthy) → `db-migrate` (completed) → app services. Prod config: `infra/docker-compose.prod.yml` + `infra/.env.example`. Constraint: only **one** `telegram-collector` instance per Telegram user session (session file needs a persistent volume). See `docs/deployment.md`.

## Where things are

- `services/<name>/src/<name>/` — each service: `__main__.py` (entry, `<name> run`), `settings.py` (pydantic-settings, env-aliased), `db.py`, `models.py`. Collectors add `collector.py` + mapping modules; normalizer adds `worker.py`, `normalization.py`, `model_client.py`.
- `docs/` — product + design docs; `docs/services/` has per-service specs.
- `infra/` — compose files, env examples, `scripts/dev-*.sh`.
- `db/migrations/versions/` — Alembic revisions.
