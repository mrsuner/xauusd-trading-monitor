> Superseded for VPS82 shared infrastructure on2026-10-17. Historical evidence only.
> Do not execute the dedicated PostgreSQL/Redis deployment or old update procedure.
> Current authority: [VPS deployment](vps-deployment.md).

# XAUUSD VPS production authority

Updated:2026-10-16. Scope: VPS public news and notifications only.
The new canonical local inputs and final overlay are prepared and statically
validated; they have **not** been installed on82. HomeLab and Pages are unchanged.

## Coordinates and service boundaries

- Local infra: `/Users/lukesun/Projects/trading-sys/repos/xauusd-trading-monitor/infra`.
- Server: `ubuntu@51.79.161.82`,
  `/home/ubuntu/thetickbase-infra/xauusd-trading-monitor/infra`.
- Compose project: `xauusd-public-api`.
- Six running services: public-postgres, public-api, notification-redis,
  notification-api, notification-horizon, notification-scheduler.
- **`notifications` profile is active in production.** Two migration services
  are available in the model but are not long-running applications.
- Existing shared Tunnel → `xauusd-public-api:8080` → public PostgreSQL.
  TickBase account → `xauusd-notification:8080` over `tickbase_internal`.
  No backend host HTTP port is published.
- Public API: `https://news-api.thetickbase.com`; Pages frontend:
  `https://news.thetickbase.com`. No DNS/Tunnel/Pages changes are prepared here.

## Canonical inputs

| Local canonical file | Captured current server source |
| --- | --- |
| `infra/.env.vps` | `/home/ubuntu/thetickbase-infra/infra/xauusd-public-api.env` |
| `infra/.env.notification.prod` | `/home/ubuntu/thetickbase-infra/infra/notification.env` |

Both are exact original copies (21/38 parsed assignments), mode0600 and ignored
by Git. Preserve HMAC ingest identity, notification internal secret, APP_KEY,
Firebase settings, delivery gates and DB/Redis settings. This phase did not
disable live notification delivery or replace any identity.

Compose order: this project's `docker-compose.public-api.yml`, shared
`overrides/xauusd-public-api.edge.yml`, then this project's
`docker-compose.vps.yml`. Shared env is loaded first, then `.env.vps`;
`NOTIFICATION_ENV_FILE` points to `.env.notification.prod`. The wrapper always
selects the active `notifications` profile and isolates Compose from ambient
development environment variables.

## Static checks and future releases

```bash
infra/scripts/vps.sh config
infra/scripts/vps.sh images
```

These delegate to the umbrella's read-only `vps.py`; they do not start containers,
query production databases, pull images or send notifications. `ps` queries the
local default Docker context, not an implicit SSH target; use it on the intended
host only after a separately authorized bundle installation.

Current public-api tag is `c8dbf85`; notification tag is `6473202`. Both are now
captured by their actual registry digests in the final overlay, including their
corresponding migration services. Do not assume one `IMAGE_TAG` selects both.
Changing only an env tag does not override the final image pins.

Follow the [shared release procedure](/Users/lukesun/Projects/trading-sys/infra/README.md#future-production-update-procedure)
for future updates. Keep the public and `notify` schemas/default grants, durable
Redis queues and account-to-notification secret contract. Horizon keeps its
current180s stop grace; a real notification release needs drain/external-effect
review. Never replay queues during static acceptance.

HomeLab's private collectors/public-syncer use `docker-compose.prod.yml`, with
their own env/session volumes. Their local build and development commands remain
unchanged; do not sync source trees or start that full model on82. The existing
image build script covers public-api but not the Laravel notification image;
for a future notification release build `services/notification/Dockerfile` from
the project root, for `linux/amd64`, under a new approved GHCR tag/digest. No
build, registry push, HomeLab update or Pages release occurred here.

For that separately authorized future notification build (not executed here):

```bash
docker buildx build --platform linux/amd64 \
  -f services/notification/Dockerfile \
  -t "ghcr.io/mrsuner/xauusd-trading-monitor/notification:${RELEASE_TAG:?Set a new approved immutable source tag}" \
  --push .
```
