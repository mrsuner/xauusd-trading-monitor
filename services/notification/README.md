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

The SQLite test database uses unqualified table names. PostgreSQL must create the
`notify` schema and put `notify` before `public` in `DB_SEARCH_PATH`; the public tables
remain read-only to this service.
