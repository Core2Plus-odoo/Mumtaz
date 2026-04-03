#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/opt/mumtaz/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

docker compose -f /opt/mumtaz/docker-compose.production.yml exec -T db \
  pg_dump -U "${POSTGRES_USER:-odoo}" "${POSTGRES_DB:-mumtaz}" | gzip > "$BACKUP_DIR/mumtaz_${TIMESTAMP}.sql.gz"

find "$BACKUP_DIR" -name 'mumtaz_*.sql.gz' -mtime +30 -delete
