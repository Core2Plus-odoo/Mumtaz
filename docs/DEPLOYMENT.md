# Deployment Guide (Hostinger VPS + GitHub)

1. Run `scripts/setup-vps.sh` on a fresh Ubuntu VPS.
2. Clone repository to `/opt/mumtaz`.
3. Fill `.env.production` secrets.
4. Run `docker compose -f docker-compose.production.yml --env-file .env.production up -d --build`.
5. Configure GitHub repository secrets and enable workflows in `.github/workflows`.
