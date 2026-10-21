#!/bin/sh
set -eu
fail() { echo "Shared82 notification entrypoint rejected: $1" >&2; exit 64; }
case "${XAUUSD_SHARED82_ROLE:-}" in
    notify-runtime)
        expected=xauusd_notify_runtime
        [ "${REDIS_HOST:-}" = shared-redis-state ] || fail "state host"
        [ "${REDIS_USERNAME:-}" = xauusd_state ] || fail "state ACL"
        [ "${REDIS_DB:-}" = 0 ] && [ "${REDIS_CACHE_DB:-}" = 0 ] || fail "logical database"
        [ "${REDIS_PREFIX:-}" = xauusd: ] && [ "${HORIZON_PREFIX:-}" = xauusd:horizon: ] || fail "namespace"
        [ -z "${REDIS_URL:-}" ] || fail "Redis URL override"
        [ "${CACHE_STORE:-}" = redis ] || fail "state cache store"
        [ "${REDIS_QUEUE_RETRY_AFTER:-}" = 240 ] || fail "retry safety"
        case "$*" in
            "php -S 0.0.0.0:8080 -t public public/index.php"|"php artisan horizon"|"php artisan schedule:work") ;;
            *) fail "runtime command" ;;
        esac
        ;;
    notify-migrator)
        expected=xauusd_notify_migrator
        [ "${NOTIFICATION_ENABLED:-}" = false ] && [ "${NOTIFICATION_DRY_RUN:-}" = true ] && [ "${DIGEST_ENABLED:-}" = false ] || fail "migration provider isolation"
        case "$*" in
            "php artisan migrate --force"|"php artisan migrate:status --no-ansi") ;;
            *) fail "migration command" ;;
        esac
        ;;
    *) fail "role" ;;
esac
[ "${DB_SEARCH_PATH:-}" = notify,public ] || fail "schema search path"
[ "${DB_CONNECTION:-}" = pgsql ] || fail "database driver"
EXPECTED_DB_ROLE="$expected" php -r '
$u=parse_url(getenv("DB_URL"));
$ok=is_array($u) && in_array($u["scheme"]??"",["postgres","postgresql","pgsql"],true)
    && ($u["host"]??"")==="shared-postgres" && ($u["port"]??0)===5432 && ($u["path"]??"")==="/xauusd_public"
    && ($u["user"]??"")===getenv("EXPECTED_DB_ROLE") && !empty($u["pass"]) && !isset($u["query"]) && !isset($u["fragment"]);
exit($ok?0:64);' || fail "database identity"
# The image stays unchanged. Drop only this container's possibly baked config;
# migration credentials never enter a cache shared with a runtime container.
rm -f bootstrap/cache/config.php
exec ./docker-entrypoint.sh "$@"
