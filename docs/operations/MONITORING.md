# Monitoring

- Service status: `docker compose -f docker-compose.production.yml ps`
- Odoo logs: `docker compose -f docker-compose.production.yml logs -f odoo`
- Health check: `bash scripts/health-check.sh`
- Backups path: `/opt/mumtaz/backups`
