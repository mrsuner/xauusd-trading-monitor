#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-infra/.env}"
COMPOSE_FILE="${2:-infra/docker-compose.prod.yml}"
NORMALIZER_REPLICAS="${NORMALIZER_REPLICAS:-}"

if [[ -z "$NORMALIZER_REPLICAS" && -f "$ENV_FILE" ]]; then
  NORMALIZER_REPLICAS="$(grep -E '^NORMALIZER_REPLICAS=' "$ENV_FILE" | tail -n 1 | cut -d '=' -f 2- | tr -d '\"' || true)"
fi

NORMALIZER_REPLICAS="${NORMALIZER_REPLICAS:-2}"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --remove-orphans \
  --scale "normalizer-classifier=${NORMALIZER_REPLICAS}"
