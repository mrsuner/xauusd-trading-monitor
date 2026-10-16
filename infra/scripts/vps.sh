#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
shared_root="${TRADING_SYS_ROOT:-$(cd "$project_root/../.." && pwd)}"
[[ -f "$shared_root/infra/scripts/vps.py" ]] || { echo "Set TRADING_SYS_ROOT to the canonical trading-sys checkout." >&2; exit 2; }
exec python3 "$shared_root/infra/scripts/vps.py" xauusd "$@"
