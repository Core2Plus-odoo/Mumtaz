#!/usr/bin/env bash
# Phase 6 — install ops automation (backups, healthcheck, cert renew).
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
install -m 755 "$REPO/platform/ops/scripts/backup.sh"      /opt/mumtaz/scripts/backup.sh
install -m 755 "$REPO/platform/ops/scripts/healthcheck.sh" /opt/mumtaz/scripts/healthcheck.sh
CRON=/etc/cron.d/mumtaz
cat > "$CRON" <<CRONEOF
*/5 * * * * root /opt/mumtaz/scripts/healthcheck.sh >> /opt/mumtaz/logs/health.log 2>&1
0 3 * * *   root /opt/mumtaz/scripts/backup.sh      >> /opt/mumtaz/logs/backup.log 2>&1
0 12 * * *  root certbot renew --quiet
CRONEOF
chmod 644 "$CRON"
echo "ops cron installed at $CRON"
