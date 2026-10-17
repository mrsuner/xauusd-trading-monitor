# XAUUSD VPS production authority

Updated:2026-10-17. Shared82 migration is deployed and accepted. This document owns
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

## Normal updates

Use `infra/scripts/shared82-release.py`; on VPS82 it lives under the canonical
infra root above and runs with `sudo python3`. Real M9 native/candidate/runtime
acceptance passed20:12:56Z. The
[operator sequence](/Users/lukesun/Projects/infra/platform/82/maintenance/README.md)
requires published infra/digests and recent full native recovery → plan → graceful
freeze → NEW frozen backup → HomeLab full native recovery plus public/notify
migrator and post-migration backup/role rehearsal → admit → explicit migrate
→ scoped four-service up → actual API/HMAC/Horizon/runtime checks → finish.
No shared engine, Tunnel, Pages, DNS or private pipeline rollout is implied.

Before pausing the HomeLab200 public syncer, create and independently restore-verify
a current private checkpoint/config custody. Pause only its exact current ID at
zero sending/inflight rows; retain image/env/restart policy and resume that same
ID after VPS acceptance. Ready/delayed queues remain in Redis state; drain active
jobs gracefully without forcing a long job to exit. Private collectors/session
data stay outside this scoped update and82 regular daily coverage.

The [central backup authority](/Users/lukesun/Projects/infra/docs/82-centralized-backup-deployment-2026-10-18.md)
now has first full source/HomeLab/FTPS acceptance. Post-window native recovery
passed20:42:05Z; five new82 timers were enabled/active20:45UTC. Regular3/14/7 retention covers shared public+notify DB/state and
files/config custody; the separate private pipeline checkpoint is protected
maintenance custody, not a claim of daily private-pipeline backup.

Operation `xauusd-20261017T192321Z-7c6c0ac6` used fresh frozen generation
`vps82-20261017T192443Z-pre-migration-c8917f44` and actual full36-dataset/seven-migrator
HomeLab acceptance before Production commands. A fresh private writer checkpoint
also passed native PG16.14 recovery (25 tables/1,106,656 rows). The original public
syncer ID was paused at zero inflight and resumed unchanged20:10:25Z. Public API,
internal account authentication200/missing-secret401, actual Horizon provider-free
job/state/role checks passed. Finish verified images/env and restored restart
policies. The private pipeline, Pages, original fenced sources and old jobs remain.

## Historical one-time migration and recovery gates

The following PG16 cold-target/namespace-transfer steps describe the completed
17Oct architecture cutover. They are not a normal update path; never restore over
the authoritative shared database or replay stale delivery queues.

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
and sequences. Run scoped ANALYZE after a logical restore and before opening
traffic; source optimizer statistics are not transferred by pg_dump. Transfer business/cache/queue keys with logical value/type and
absolute expiry checks, rejecting collisions; archive old Horizon process/metric
keys in source RDB without reviving stale process metadata. Never FLUSH shared
Redis or restore a whole RDB over it. Start only the four new services, verify
API, account contract, real Horizon/queue and retained flags, then resume the
same original syncer. Retain all six original containers/volumes stopped with
restart=no. Source-specific PostgreSQL16 and Redis volumes are rollback evidence.

After new writes, the old DB is stale. Before rollback, freeze current writers,
create and actually restore a new current point, reconcile DB/queue/provider
side effects, and explicitly select a recovery coordinate. Never blindly restart
old writers or replay old deliveries. Current normal updates use the installed
controller and fresh per-operation gate above; old dedicated shortcuts are not
a fallback update path.

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


## Accepted production evidence —2026-10-17

Frozen ciphertext `4854d6d781e9d2bfea9064561653c98042ec83576db9fb59929ce52dca680367`
is retained on Mac and HomeLab199. Logical PG16/18 and exact physical PG16 cold
recovery passed:29 tables,2,059,614 rows,3 sequences, source extension versions,
files/modes/owners and native source RDB. Same-point API/HMAC/idempotency/replay
and a measured65s Horizon job under two consumers passed; one attempt and
64.12s graceful drain, no provider calls. Source queues were all empty.

The empty permanent target restored exactly; migrations remained
`0009_digest_content_lifecycle|7`.29 target table statistics were refreshed after
observed cold query timeouts; all three public health/event/raw APIs then passed.
Real runtime roles18.6 reject DDL; Redis cache/locks and a real provider-free
Horizon job pass. TickBase account's existing notification secret returns200,
missing secret401.22 public and32 notification app/provider settings match the
original. Enabled delivery/admission/digest and dry_run=false are preserved.

All six original runtime/PG/Redis containers keep exact IDs/volumes, stopped and
restart=no.303 old Horizon keys are archived, not revived; business/cache keys
had naturally expired, so zero stale keys were copied. The existing shared
Tunnel, DNS, Pages and HomeLab200 pipeline/env/images are unchanged. The same
paused syncer resumed with its original restart policy; two pending events became
sent, with the existing failed count remaining1. No collector/model/session was
started, rebuilt or recreated.

First actual `xauusd_backup` export from permanent18.6 is independently stored:
`d32c7723520fc94387e286e270b056981e45d15d395e9c3ca823d0ad8457e619`.
Native HomeLab recovery passed29 tables/2,059,696 rows/3 sequences, both schema
roles, configuration file readback and shared-state RDB load. Its later row count
reflects resumed production writes, not a mismatch with the frozen point.
Application/provider calls are not executed from restored daily Redis payloads.
The frozen point's application proof and current runtime acceptance are separate.

The one-time central apply adapter is closed by its production acceptance marker.
Do not reuse its old recovery point for a later release. That M5 phase did not
enable schedules. M8/M9 subsequently installed the normal release gate and
central3/14/7 timers; current acceptance is above. Old backup jobs/data remain intact. HomeLab200 private pipeline is a separate
recovery scope: its native checkpoint does not imply an ongoing VPS82 schedule
covers private collectors, inference state, publishers or Telegram sessions.
