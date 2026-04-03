# Deployment Guide (Hostinger VPS + GitHub)

## Prerequisites
- Hostinger VPS (Ubuntu 22.04+)
- Domain pointed to VPS IP
- GitHub secrets configured (`PROD_*`, `STAGING_*`, optional `SLACK_WEBHOOK`)

## First-time setup
1. Run `bash scripts/setup-vps.sh` as root on VPS.
2. Clone repository to `/opt/mumtaz`.
3. Fill `.env.production` with real secrets.
4. Run `python3 scripts/validate-deployment.py`.
5. Start stack: `docker compose -f docker-compose.production.yml --env-file .env.production up -d --build`.

## GitHub workflows
- CI: `.github/workflows/test.yml`
- Staging deploy: `.github/workflows/deploy-staging.yml`
- Production deploy (manual): `.github/workflows/deploy-production.yml`
- Nightly backup: `.github/workflows/backup.yml`

## Operations
- Health check: `bash scripts/health-check.sh`
- Backup now: `bash scripts/backup.sh`
- Rollback: `bash scripts/rollback.sh`
- Odoo migration: `python3 scripts/migrate.py --db mumtaz --modules base`
