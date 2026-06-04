#!/usr/bin/env sh
set -eu

cat > /usr/share/nginx/html/env.js <<EOF
window.__XAUUSD_DASHBOARD_CONFIG__ = {
  DASHBOARD_API_BASE_URL: "${DASHBOARD_API_BASE_URL:-/api}",
  DASHBOARD_API_TOKEN: "${DASHBOARD_API_TOKEN:-}"
};
EOF

exec nginx -g "daemon off;"
