SHELL := /bin/bash

DEV_ENV ?= infra/.env.dev
DEV_COMPOSE := docker compose --env-file $(DEV_ENV) -f infra/docker-compose.dev.yml

.PHONY: dev dev-stop dev-status dev-logs dev-db dev-migrate compose-config test

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
	@echo "production compose config ok"

test:
	@cd services/telegram-collector && uv run --group dev pytest
	@cd services/rss-collector && uv run --group dev pytest
	@cd services/normalizer-classifier && uv run --group dev pytest
