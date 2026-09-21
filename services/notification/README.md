# Notification service

Laravel service that owns paid per-user news preferences and Telegram delivery state.
It uses the public product PostgreSQL database through a restricted role, stores its
tables in the `notify` schema, and uses a dedicated Redis instance for Laravel Horizon.

## Safety defaults

- `NOTIFICATION_ENABLED=false`
- `NOTIFICATION_DRY_RUN=true`
- no public settings routes; Tickbase Account calls the private API
- Horizon is limited to configured operator IP addresses
- News checkout remains disabled until the capacity phase passes

Live jobs use `news-match`, `news-telegram-high`, and
`news-telegram-standard`. Shared digests use isolated `news-digest-generate` and
`news-digest-deliver` workers with lower process priority. Three high-priority
workers serve S events while one reserved standard worker prevents A/B/C
starvation; all Telegram workers still share the same bot and per-chat limits.

The production Compose file keeps every notification container behind the explicit
`notifications` profile. Provision the `notify` schema and restricted role with
`infra/postgres/notification-role.sql`, then supply a root-owned `notification.env`.
The role owns `notify` and receives read-only access to `public`; it does not own or
write public event tables. Enabling the profile does not enable delivery:
`NOTIFICATION_ENABLED` and `DIGEST_ENABLED` remain separate closed-by-default gates.

## Local checks

```bash
composer validate --strict
vendor/bin/pint --test
php artisan migrate:fresh --force
php artisan test
```

## Local digest QA

The local SQLite setup includes database cache and queue tables so Artisan's
scheduler and database queue driver work without Redis. Production continues to
use the dedicated Redis and Horizon services from Compose.

Inspect a UTC day without writing data or calling a model:

```bash
php artisan digest:generate --date=2026-09-20 --topic=energy --dry-run
```

For a real synchronous generation, configure `DIGEST_MODEL_API_KEY` and
`DIGEST_MODEL_NAME`, then omit `--dry-run`. The command does not require a queue
worker and reports edition status, selected event count, total model tokens,
latency, and the final error code. It will not regenerate an existing terminal
edition; use a disposable local database when repeating QA for the same date.

The scheduled pipeline remains closed by default. Enable `DIGEST_ENABLED=true`
only when the scheduler, queue workers, model credentials, public event tables,
and account access service are all available.

The SQLite test database uses unqualified table names. PostgreSQL must create the
`notify` schema and put `notify` before `public` in `DB_SEARCH_PATH`; the public tables
remain read-only to this service.
