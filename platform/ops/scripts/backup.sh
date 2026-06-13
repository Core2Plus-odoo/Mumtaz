#!/usr/bin/env bash
# Nightly backups of the platform DB + every tenant Odoo DB. 30-day retention.
set -euo pipefail
set -a; while IFS='=' read -r k v; do case "$k" in ''|\#*) continue;; esac; export "$k=$v"; done < /opt/mumtaz/.env; set +a
TS=$(date +%Y%m%d_%H%M); OUT=/opt/mumtaz/backups; mkdir -p "$OUT"
export PGPASSWORD="$DB_PASS"
pg_dump -h localhost -U "$DB_USER" "$DB_NAME" | gzip > "$OUT/platform_$TS.sql.gz"
for db in $(psql -h localhost -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT odoo_db FROM tenants WHERE odoo_db IS NOT NULL"); do
  pg_dump -h localhost -U "$DB_USER" "$db" 2>/dev/null | gzip > "$OUT/${db}_$TS.sql.gz" || true
done
unset PGPASSWORD
find "$OUT" -name '*.sql.gz' -mtime +30 -delete
echo "backup $TS done"
