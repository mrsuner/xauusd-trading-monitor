#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-infra/.env.dev}"
ENV_PATH="$ROOT_DIR/$ENV_FILE"
PID_DIR="$ROOT_DIR/var/dev/pids"
LOG_DIR="$ROOT_DIR/var/dev/logs"

if [[ ! -f "$ENV_PATH" ]]; then
  echo "Missing $ENV_FILE"
  echo "Create it first:"
  echo "  cp infra/.env.dev.example infra/.env.dev"
  exit 1
fi

command -v docker >/dev/null || { echo "docker is required"; exit 1; }
command -v uv >/dev/null || { echo "uv is required"; exit 1; }

mkdir -p "$PID_DIR" "$LOG_DIR" "$ROOT_DIR/infra/data/telegram-sessions"

"$ROOT_DIR/infra/scripts/dev-stop.sh" "$ENV_FILE" --apps-only

echo "Starting dev PostgreSQL..."
docker compose --env-file "$ENV_PATH" -f "$ROOT_DIR/infra/docker-compose.dev.yml" up -d postgres

wait_for_postgres() {
  local container_id
  container_id="$(docker compose --env-file "$ENV_PATH" -f "$ROOT_DIR/infra/docker-compose.dev.yml" ps -q postgres)"

  if [[ -z "$container_id" ]]; then
    echo "PostgreSQL container was not created"
    exit 1
  fi

  echo "Waiting for dev PostgreSQL to become healthy..."
  for _ in {1..60}; do
    local status
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
    if [[ "$status" == "healthy" ]]; then
      return
    fi
    if [[ "$status" == "exited" || "$status" == "dead" ]]; then
      echo "PostgreSQL container stopped before becoming healthy"
      docker compose --env-file "$ENV_PATH" -f "$ROOT_DIR/infra/docker-compose.dev.yml" logs postgres
      exit 1
    fi
    sleep 1
  done

  echo "Timed out waiting for PostgreSQL healthcheck"
  docker compose --env-file "$ENV_PATH" -f "$ROOT_DIR/infra/docker-compose.dev.yml" logs postgres
  exit 1
}

wait_for_postgres

echo "Running database migrations..."
(
  cd "$ROOT_DIR"
  set -a
  # shellcheck source=/dev/null
  source "$ENV_PATH"
  set +a
  uv run --group db alembic -c db/alembic.ini upgrade head
)

start_service() {
  local name="$1"
  local project_dir="$2"
  shift 2

  if [[ ! -d "$ROOT_DIR/$project_dir" ]]; then
    echo "Skipping $name; $project_dir does not exist"
    return
  fi

  local log_file="$LOG_DIR/$name.log"
  local pid_file="$PID_DIR/$name.pid"
  : > "$log_file"

  echo "Starting $name..."
  (
    cd "$ROOT_DIR"
    set -a
    # shellcheck source=/dev/null
    source "$ENV_PATH"
    set +a
    if [[ "${TELEGRAM_SESSION_PATH:-}" == /app/sessions/* ]]; then
      export TELEGRAM_SESSION_PATH="$ROOT_DIR/infra/data/telegram-sessions/$(basename "$TELEGRAM_SESSION_PATH")"
    fi
    if [[ -n "${TELEGRAM_SESSION_PATH:-}" ]]; then
      mkdir -p "$(dirname "$TELEGRAM_SESSION_PATH")"
    fi
    exec uv run --project "$project_dir" "$@"
  ) >"$log_file" 2>&1 &

  echo "$!" > "$pid_file"
}

start_service "telegram-collector" "services/telegram-collector" telegram-collector run
start_service "rss-collector" "services/rss-collector" rss-collector run
start_service "normalizer-classifier" "services/normalizer-classifier" normalizer-classifier run
start_service "dashboard-api" "services/dashboard-api" dashboard-api run

sleep 2

echo
echo "Dev services:"
"$ROOT_DIR/infra/scripts/dev-status.sh" "$ENV_FILE"
echo
echo "Logs:"
echo "  make dev-logs"
