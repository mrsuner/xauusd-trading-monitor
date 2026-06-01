#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-infra/.env.dev}"
MODE="${2:-}"
ENV_PATH="$ROOT_DIR/$ENV_FILE"
PID_DIR="$ROOT_DIR/var/dev/pids"

stop_pid() {
  local pid_file="$1"
  local name
  name="$(basename "$pid_file" .pid)"

  [[ -f "$pid_file" ]] || return

  local pid
  pid="$(cat "$pid_file")"
  if [[ -z "$pid" ]]; then
    rm -f "$pid_file"
    return
  fi

  if ! kill -0 "$pid" >/dev/null 2>&1; then
    rm -f "$pid_file"
    return
  fi

  local command_line
  command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  if [[ "$command_line" != *"telegram-collector"* && "$command_line" != *"rss-collector"* && "$command_line" != *"normalizer-classifier"* && "$command_line" != *"alert-dispatcher"* && "$command_line" != *"telegram-channel-publisher"* && "$command_line" != *"dashboard-api"* && "$command_line" != *"npm run dev"* && "$command_line" != *"vite"* ]]; then
    echo "Skipping $name pid=$pid; command does not look like a project dev service"
    rm -f "$pid_file"
    return
  fi

  echo "Stopping $name pid=$pid"
  kill "$pid" >/dev/null 2>&1 || true

  for _ in {1..20}; do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      rm -f "$pid_file"
      return
    fi
    sleep 0.2
  done

  echo "Force stopping $name pid=$pid"
  kill -9 "$pid" >/dev/null 2>&1 || true
  rm -f "$pid_file"
}

if [[ -d "$PID_DIR" ]]; then
  shopt -s nullglob
  for pid_file in "$PID_DIR"/*.pid; do
    stop_pid "$pid_file"
  done
fi

stop_matching_processes() {
  local name="$1"
  local pattern="$2"

  local pids
  pids="$(pgrep -f "$pattern" 2>/dev/null || true)"
  [[ -n "$pids" ]] || return 0

  while read -r pid; do
    [[ -n "$pid" ]] || continue
    [[ "$pid" == "$$" || "$pid" == "${PPID:-}" ]] && continue

    local command_line
    command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    [[ -n "$command_line" ]] || continue
    [[ "$command_line" == *"$pattern"* ]] || continue

    echo "Stopping stale $name pid=$pid"
    kill "$pid" >/dev/null 2>&1 || true
  done <<< "$pids"

  return 0
}

stop_matching_processes "telegram-collector" "telegram-collector run"
stop_matching_processes "rss-collector" "rss-collector run"
stop_matching_processes "normalizer-classifier" "normalizer-classifier run"
stop_matching_processes "alert-dispatcher" "alert-dispatcher run"
stop_matching_processes "telegram-channel-publisher" "telegram-channel-publisher run"
stop_matching_processes "dashboard-api" "dashboard-api run"

if [[ "$MODE" != "--apps-only" && -f "$ENV_PATH" ]]; then
  docker compose --env-file "$ENV_PATH" -f "$ROOT_DIR/infra/docker-compose.dev.yml" down
fi
