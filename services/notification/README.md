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
`news-telegram-standard`. Three high-priority workers serve S events while one
reserved standard worker prevents A/B/C starvation; all workers still share the
same bot and per-chat rate limits.

## Local checks

```bash
composer validate --strict
vendor/bin/pint --test
php artisan migrate:fresh --force
php artisan test
```

The SQLite test database uses unqualified table names. PostgreSQL must create the
`notify` schema and put `notify` before `public` in `DB_SEARCH_PATH`; the public tables
remain read-only to this service.
