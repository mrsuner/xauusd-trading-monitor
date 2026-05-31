# Project Agent Instructions

## Language

Respond to chat output in Traditional Chinese.

For code-related content, including code, identifiers, comments, commit messages, commands, file paths, API names, error messages, and technical terms where English is conventional, use English.

## Branch Policy

- `main` is reserved for release-ready code and documentation.
- Development work must happen on `develop` or feature branches based on `develop`.
- Do not commit development changes directly to `main` unless the user explicitly requests a release commit.
- After repository initialization, keep the working branch on `develop` for follow-up implementation tasks.

## HomeLab Deployment Memory

- Production target: `luke@192.168.1.200`.
- Production directory: `/home/luke/xauusd-trading-monitor`.
- Production deployment files live under `/home/luke/xauusd-trading-monitor/infra`.
- Local production deployment files live under `/Users/lukesun/Projects/ongoing/xauusd-trading-monitor/infra`.
- Production Docker Compose file: `infra/docker-compose.prod.yml`.
- Production environment file on HomeLab: `infra/.env`.
- Do not overwrite HomeLab `infra/.env` during `rsync`; it contains runtime credentials.
- GHCR namespace: `ghcr.io/mrsuner/xauusd-trading-monitor`.
- Use the current commit short hash as `IMAGE_TAG` for deployment.
- Build and push production images from local machine:
  `IMAGE_PLATFORM=linux/amd64 IMAGE_TAG=$(git rev-parse --short HEAD) make docker-build-push`
- Sync deployment files to HomeLab:
  `rsync -az --delete --exclude '.env' infra/ luke@192.168.1.200:/home/luke/xauusd-trading-monitor/infra/`
- Update HomeLab image tag:
  `ssh luke@192.168.1.200 'cd ~/xauusd-trading-monitor && cp infra/.env infra/.env.backup.$(date +%Y%m%d%H%M%S) && sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=<tag>/" infra/.env'`
- Deploy on HomeLab:
  `ssh luke@192.168.1.200 'cd ~/xauusd-trading-monitor && docker compose --env-file infra/.env -f infra/docker-compose.prod.yml pull && docker compose --env-file infra/.env -f infra/docker-compose.prod.yml up -d --remove-orphans'`
- Verify deployment:
  `ssh luke@192.168.1.200 'cd ~/xauusd-trading-monitor && docker compose --env-file infra/.env -f infra/docker-compose.prod.yml ps'`
  `curl -fsS http://192.168.1.200:5173/api/health`
  `curl -fsS http://192.168.1.200:5173/api/stats/ai-usage`
- Dashboard URL: `http://192.168.1.200:5173`.
- Dashboard API is exposed through the dashboard web proxy under `/api/*`; direct host port is configured by `DASHBOARD_API_HOST_PORT` in HomeLab `infra/.env`.
- `ALERT_DRY_RUN=true` is safe for deployment testing. Confirm with the user before changing it to `false`.
- Telegram user session is persisted on HomeLab through `TELEGRAM_SESSION_HOST_DIR`; do not delete the session volume/directory unless re-authorization is intended.
- If Telegram authorization is needed, run the collector interactively on HomeLab and ask the user for the phone/code/password step by step.
