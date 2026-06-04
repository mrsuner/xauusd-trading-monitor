SHELL := /bin/bash

DEV_ENV ?= infra/.env.dev
DEV_COMPOSE := docker compose --env-file $(DEV_ENV) -f infra/docker-compose.dev.yml

.PHONY: dev dev-stop dev-status dev-logs dev-db dev-migrate compose-config test web-build public-web-build docker-build docker-push docker-build-push prod-up

dev:
	@infra/scripts/dev-up.sh "$(DEV_ENV)"

dev-stop:
	@infra/scripts/dev-stop.sh "$(DEV_ENV)"

dev-status:
	@infra/scripts/dev-status.sh "$(DEV_ENV)"

dev-logs:
	@tail -n 200 -f var/dev/logs/*.log

dev-db:
	@$(DEV_COMPOSE) up -d postgres

dev-migrate:
	@set -a; source "$(DEV_ENV)"; set +a; uv run --group db alembic -c db/alembic.ini upgrade head

compose-config:
	@docker compose --env-file infra/.env.example -f infra/docker-compose.prod.yml config >/dev/null
	@docker compose --env-file infra/.env.public-api.example -f infra/docker-compose.public-api.yml config >/dev/null
	@echo "production compose config ok"

test:
	@cd services/telegram-collector && uv run --group dev pytest
	@cd services/rss-collector && uv run --group dev pytest
	@cd services/normalizer-classifier && uv run --group dev pytest
	@cd services/event-router && uv run --group dev pytest
	@cd services/alert-dispatcher && uv run --group dev pytest
	@cd services/telegram-channel-publisher && uv run --group dev pytest
	@cd services/x-publisher && uv run --group dev pytest
	@cd services/public-syncer && uv run --group dev pytest
	@cd services/public-api && uv run --group dev pytest
	@cd services/dashboard-api && uv run --group dev pytest

web-build:
	@cd apps/dashboard-web && npm run build
	@cd apps/public-web && npm run build

public-web-build:
	@cd apps/public-web && npm run build

docker-build:
	@infra/scripts/docker-images.sh build

docker-push:
	@infra/scripts/docker-images.sh push

docker-build-push:
	@infra/scripts/docker-images.sh build-push

prod-up:
	@infra/scripts/prod-up.sh infra/.env infra/docker-compose.prod.yml
