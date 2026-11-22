#!/usr/bin/env bash
#
# Nightly dump of the Jawhar staging database, and the restore drill.
#
# Acts only on the `mumtaz-jewel-staging` compose project's own Postgres
# container. It never reaches the CRM database or the shared Postgres.
#
# Usage:
#   deploy/jewel-staging/backup.sh                       # dump
#   deploy/jewel-staging/backup.sh --restore <dump.gz>   # restore drill
#   deploy/jewel-staging/backup.sh --list
#
# Cron, once approved (as the staging user, not root):
#   17 2 * * *  /path/to/checkout/deploy/jewel-staging/backup.sh >> \
#               /opt/mumtaz/logs/jewel-backup.log 2>&1
#
# The handoff asks for one restore test before the demo. --restore does it
# into a throwaway database so the live demo database is never overwritten.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="mumtaz-jewel-staging"
CONTAINER="jewel-staging-db"
DEMO_DB="${DEMO_DB:-jewel_demo}"
BACKUP_DIR="${BACKUP_DIR:-/opt/mumtaz/backups/jewel-staging}"
KEEP_DAYS="${KEEP_DAYS:-14}"

red()  { printf '\033[31m%s\033[0m\n' "$*" >&2; }
info() { printf '\033[36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[32m%s\033[0m\n' "$*"; }

if [ ! -f "$HERE/.env" ]; then red "No $HERE/.env"; exit 2; fi
# shellcheck disable=SC1091
set -a; . "$HERE/.env"; set +a
: "${POSTGRES_USER:?POSTGRES_USER not set in .env}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  red "Container $CONTAINER is not running. Start the stack first."
  exit 1
fi

case "${1:-}" in
  --list)
    ls -lh "$BACKUP_DIR" 2>/dev/null || echo "No backups in $BACKUP_DIR"
    exit 0
    ;;

  --restore)
    DUMP="${2:-}"
    if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
      red "Usage: $0 --restore <dump.sql.gz>"; exit 2
    fi
    # Restore into a throwaway name, never over the demo database. Proving the
    # dump is loadable is the point of the drill; dropping the live demo
    # database is not.
    TARGET="jewel_restore_test_$(date +%s)"
    info "Restoring $DUMP into $TARGET (the demo database is left alone)"
    docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$CONTAINER" \
      createdb -U "$POSTGRES_USER" "$TARGET"
    gunzip -c "$DUMP" | docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" \
      "$CONTAINER" psql -q -U "$POSTGRES_USER" -d "$TARGET" >/dev/null
    COUNT="$(docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$CONTAINER" \
      psql -tAq -U "$POSTGRES_USER" -d "$TARGET" \
      -c "select count(*) from jewellery_gold_rate where state = 'approved';")"
    PIECES="$(docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$CONTAINER" \
      psql -tAq -U "$POSTGRES_USER" -d "$TARGET" \
      -c "select count(*) from stock_lot;")"
    ok "Restore OK: $TARGET has $COUNT approved rate(s) and $PIECES piece(s)"
    echo "Drop it when you are done:"
    echo "  docker exec $CONTAINER dropdb -U $POSTGRES_USER $TARGET"
    exit 0
    ;;

  "")
    mkdir -p "$BACKUP_DIR"
    STAMP="$(date +%Y%m%d-%H%M%S)"
    OUT="$BACKUP_DIR/${DEMO_DB}-${STAMP}.sql.gz"
    info "Dumping $DEMO_DB to $OUT"
    docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$CONTAINER" \
      pg_dump -U "$POSTGRES_USER" --no-owner --no-privileges "$DEMO_DB" \
      | gzip -9 > "$OUT"
    if [ ! -s "$OUT" ]; then red "Dump is empty: $OUT"; exit 1; fi
    ok "Dump OK: $(du -h "$OUT" | cut -f1)  $OUT"

    info "Removing dumps older than $KEEP_DAYS days"
    find "$BACKUP_DIR" -name "${DEMO_DB}-*.sql.gz" -type f \
      -mtime "+$KEEP_DAYS" -print -delete
    exit 0
    ;;

  *)
    red "Unknown option: $1"; exit 2
    ;;
esac
