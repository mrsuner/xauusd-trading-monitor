# XAUUSD VPS production authority

Updated:2026-10-17. Shared82 migration is prepared; installation and final
acceptance remain gated by fresh frozen source recovery. This document owns
VPS public API/notification only. HomeLab200 pipeline and Pages are separate.
The [dedicated82 runbook](vps-deployment-dedicated82-historical.md) is historical.

## Deployment coordinates

- Local authority: `infra/docker-compose.shared82.yml`, `infra/scripts/shared82.py`.
- VPS: `ubuntu@51.79.161.82:/home/ubuntu/thetickbase-infra/xauusd-trading-monitor/infra`.
- New project: `xauusd-shared82`, four runtime services: public-api,
  notification-api, notification-horizon, notification-scheduler.
- Shared PostgreSQL18.6: `shared-postgres:5432/xauusd_public` over
  `platform82_xauusd_data`. Public and notify have separate NOLOGIN owners,
  explicit migrators and DML-only runtime roles. Notification can SELECT public
  tables but cannot modify public or CREATE there. Backup can SELECT both schemas.
- Redis8.10.2 state: `shared-redis-state:6379`, ACL `xauusd_state`, DB0,
  namespace `xauusd:*`; Horizon prefix `xauusd:horizon:`. The application's cache
  includes access/dedup/locks, so it also uses authoritative state/noeviction.
  No independent Redis is installed and no peer namespace/global flush is granted.
- Existing shared trading Tunnel on `thetickbase-edge` continues to resolve
  `xauusd-public-api:8080`; public URL `https://news-api.thetickbase.com`.
- TickBase account continues using `xauusd-notification:8080` on
  `tickbase_internal`. Horizon/scheduler retain their existing account route.
- No host HTTP ports, new Tunnel, DNS or Pages change. Frontend stays
  `https://news.thetickbase.com`.

## Canonical private inputs

Owner-only, ignored files under local/server `infra/`:

| File | Scope |
| --- | --- |
| `.env.shared82.compose` | Separate immutable public/notification images |
| `.env.shared82.public` | Public runtime and original HMAC identity |
| `.env.shared82.public-migrator` | Public DDL identity, no ingest secret |
| `.env.shared82.notification` | Notify runtime, original APP_KEY/provider/internal secrets and production gates |
| `.env.shared82.notification-migrator` | Notify DDL identity; providers absent, delivery/admission/digest disabled, dry-run enabled |

`env_file: format: raw` preserves literal credential bytes. The original
`.env.vps` and `.env.notification.prod` are retained as legacy seed/rollback
inputs; they do not configure new runtime. Never regenerate identities, expose
`compose config` output or copy development envs over these files.

```bash
infra/scripts/vps.sh config
infra/scripts/vps.sh images
```

These are read-only validation; neither deploys. Each runtime's entrypoint
rejects the wrong DB identity/command. Migrations run explicitly in data-only
services, never automatically on app start. Per-container config cache is
cleared before the original entrypoint; no migrator cache is shared with runtime.
All runtime containers use init; notification HTTP stops with SIGINT, while
Horizon/scheduler use SIGTERM. Horizon retry_after and stop grace are240s,
above the existing180s job timeout.

## Migration and recovery gates

The central operation `20261017t101521z` owns the one-time apply and receipts in
`/Users/lukesun/Projects/infra/docs/82-shared-rollout-execution-plan-2026-10-17.md`.
Before source mutation, native isolated recovery must pass for both current VPS
and HomeLab200 private DB backups. Do not restore production plaintext on Mac.
Pause only the exact HomeLab200 public-syncer at a zero-inflight boundary; retain
its container/catalog revision, env, image and original restart policy. Do not
recreate collectors, classifiers, local inference, publishers or Telegram sessions.

Stop VPS producers/HTTP, drain all six delivery queues and stop Horizon. The old
PID1 scheduler is suspended first; only its empty parent can be terminated after
proving no children remain. Capture a new logical/public+notify backup, native
Redis RDB, exact configuration and cold PG16 volume. Copy ciphertext independently
and restore PG16 physical/logical, PG18, roles, files and Redis on HomeLab199.
Use the exact frozen point for API/HMAC/idempotency and a synthetic65s Horizon
job with a competing consumer and graceful drain; no provider calls.

Only restore the empty shared target. Preserve schema ownership/default grants
and sequences. Transfer business/cache/queue keys with logical value/type and
absolute expiry checks, rejecting collisions; archive old Horizon process/metric
keys in source RDB without reviving stale process metadata. Never FLUSH shared
Redis or restore a whole RDB over it. Start only the four new services, verify
API, account contract, real Horizon/queue and retained flags, then resume the
same original syncer. Retain all six original containers/volumes stopped with
restart=no. Source-specific PostgreSQL16 and Redis volumes are rollback evidence.

After new writes, the old DB is stale. Before rollback, freeze current writers,
create and actually restore a new current point, reconcile DB/queue/provider
side effects, and explicitly select a recovery coordinate. Never blindly restart
old writers or replay old deliveries. Normal future release/backup adapters and
central3/14/7 scheduling are completed by the cross-project closure milestones;
old dedicated shortcuts are not a fallback update path.

## Image and source boundaries

This migration reuses exact running images; it does not include unpublished
account-deletion, content-withdrawal, timezone or frontend work:

- public-api: `sha256:ae1fef09a507cc4c1e6b916f0793c9ee066757fe44305170aee5daaaea6d800e`
- notification: `sha256:8e5fdc31e2b6f72bc7935d55b9a293a4f51f83383c46377affcfbd404c82bff7`

The image components match the current remote develop component trees. Do not
claim OCI revision labels absent from these historical images. No build, image
tag reuse, main merge, HomeLab full deployment or Pages release is required.
Local development and HomeLab `docker-compose.prod.yml`/image build commands
remain valid for their own scope.
