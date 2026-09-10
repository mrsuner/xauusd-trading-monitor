#!/bin/sh
set -eu

required="APP_KEY DB_URL REDIS_HOST NOTIFICATION_INTERNAL_SECRET NEWS_INTERNAL_SECRET NOTIFICATION_CHANNEL_FINGERPRINT_KEY"
for name in $required; do
    eval "value=\${$name:-}"
    if [ -z "$value" ]; then
        echo "Missing required notification environment variable: $name" >&2
        exit 1
    fi
done

exec "$@"
