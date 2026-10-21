#!/usr/bin/env bash
set -euo pipefail
infra_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$infra_root/scripts/shared82.py" "$@"
