#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-infra/.env.dev}"
ENV_PATH="$ROOT_DIR/$ENV_FILE"
PID_DIR="$ROOT_DIR/var/dev/pids"

if [[ -f "$ENV_PATH" ]]; then
  docker compose --env-file "$ENV_PATH" -f "$ROOT_DIR/infra/docker-compose.dev.yml" ps
else
  echo "No $ENV_FILE found; skipping compose status"
fi

echo
echo "Local process services:"
if [[ ! -d "$PID_DIR" ]]; then
  echo "  no PID directory"
  exit 0
fi

shopt -s nullglob
pid_files=("$PID_DIR"/*.pid)
if [[ ${#pid_files[@]} -eq 0 ]]; then
  echo "  no local service PID files"
  exit 0
fi

for pid_file in "${pid_files[@]}"; do
  name="$(basename "$pid_file" .pid)"
  pid="$(cat "$pid_file")"
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    echo "  $name running pid=$pid"
  else
    echo "  $name stopped"
  fi
done
