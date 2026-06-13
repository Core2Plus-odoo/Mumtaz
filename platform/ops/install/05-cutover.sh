#!/usr/bin/env bash
# =====================================================================
#  Phase 5 — CUTOVER (the only destructive step)
#  Deploys the new stack to /opt/mumtaz, stands up the two FastAPI
#  services, and switches nginx for app/zaki/mumtaz to the new config.
#
#  SAFETY:
#   - Backs up all databases + /etc/nginx first.
#   - Requires CONFIRM=yes to run.
#   - The current Odoo (erp) is left untouched.
#   - Old configs are backed up, not deleted, so you can roll back.
#
#  Run:  CONFIRM=yes bash platform/ops/install/05-cutover.sh
# =====================================================================
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
P="$REPO/platform"
TS="$(date +%Y%m%d_%H%M%S)"
BK="/opt/mumtaz/backups/cutover_$TS"
log(){ echo "==> $*"; }
die(){ echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "Run as root."
[ "${CONFIRM:-}" = "yes" ] || die "Refusing without CONFIRM=yes (this switches the live domains)."
set -a; while IFS='=' read -r k v; do case "$k" in ''|\#*) continue;; esac; export "$k=$v"; done < /opt/mumtaz/.env; set +a

# 1. BACKUP -----------------------------------------------------------
log "Backing up to $BK ..."
mkdir -p "$BK"
export PGPASSWORD="$DB_PASS"
pg_dump -h localhost -U "$DB_USER" "$DB_NAME" | gzip > "$BK/${DB_NAME}.sql.gz" || true
for db in $(psql -h localhost -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT odoo_db FROM tenants WHERE odoo_db IS NOT NULL"); do
  pg_dump -h localhost -U "$DB_USER" "$db" 2>/dev/null | gzip > "$BK/${db}.sql.gz" || true
done
cp -a /etc/nginx "$BK/nginx" 2>/dev/null || true
unset PGPASSWORD
log "Backup complete."

# 2. DEPLOY CODE ------------------------------------------------------
log "Deploying code to /opt/mumtaz ..."
rsync -a --delete "$P/marketing/"            /opt/mumtaz/marketing/
rsync -a --delete "$P/control-panel/backend/"  /opt/mumtaz/platform/backend/
rsync -a --delete "$P/control-panel/frontend/" /opt/mumtaz/platform/frontend/
rsync -a --delete "$P/zaki/backend/"           /opt/mumtaz/zaki/backend/
rsync -a --delete "$P/zaki/frontend/"          /opt/mumtaz/zaki/frontend/

# 3. PYTHON VENVS -----------------------------------------------------
for svc in platform zaki; do
  D="/opt/mumtaz/$svc/backend"
  log "venv for $svc ..."
  [ -x "$D/venv/bin/python" ] || { rm -rf "$D/venv"; python3 -m venv "$D/venv"; }
  "$D/venv/bin/python" -m ensurepip --upgrade >/dev/null 2>&1 || true
  "$D/venv/bin/python" -m pip install -q --upgrade pip
  "$D/venv/bin/python" -m pip install -q -r "$D/requirements.txt"
done

# 4. SYSTEMD ----------------------------------------------------------
log "Installing services (stopping old zaki-server on :8002 if present)..."
systemctl stop zaki-server 2>/dev/null || true
systemctl disable zaki-server 2>/dev/null || true
cp "$P/ops/systemd/zaki.service"            /etc/systemd/system/zaki.service
cp "$P/ops/systemd/mumtaz-platform.service" /etc/systemd/system/mumtaz-platform.service
systemctl daemon-reload
systemctl enable zaki mumtaz-platform
systemctl restart zaki mumtaz-platform
sleep 3
systemctl is-active mumtaz-platform || die "mumtaz-platform failed — journalctl -u mumtaz-platform -n 30"
systemctl is-active zaki || die "zaki failed — journalctl -u zaki -n 30"

# 5. NGINX ------------------------------------------------------------
log "Switching nginx for app/zaki/mumtaz (erp untouched)..."
for d in app.mumtaz.digital zaki.mumtaz.digital mumtaz.digital; do
  # Escape dots so the server_name match is exact and NOT a suffix match.
  # (A naive ".*mumtaz.digital" pattern also matches app./zaki. and would
  #  delete the symlinks we just created on the final iteration.)
  d_re="$(printf '%s' "$d" | sed 's/[.[\*^$]/\\&/g')"
  # disable any existing enabled config whose server_name lists THIS exact
  # domain as a whole token (kept in backup). Bounded by space/semicolon so
  # "mumtaz.digital" never matches "app.mumtaz.digital".
  find /etc/nginx/sites-enabled -maxdepth 1 -type l | while read -r ln; do
    if grep -qE "server_name[^;]*[[:space:]]${d_re}[[:space:];]" "$ln" 2>/dev/null; then
      rm -f "$ln"
    fi
  done
  cp "$P/ops/nginx/$d.conf" "/etc/nginx/sites-available/$d.conf"
  ln -sf "/etc/nginx/sites-available/$d.conf" "/etc/nginx/sites-enabled/$d.conf"
  log "  enabled $d.conf"
done
# Sanity: all three must be linked before we reload.
for d in app.mumtaz.digital zaki.mumtaz.digital mumtaz.digital; do
  [ -L "/etc/nginx/sites-enabled/$d.conf" ] || die "sites-enabled/$d.conf was not created"
done
nginx -t || die "nginx config test failed — restore from $BK/nginx and re-run"
systemctl reload nginx

echo ""
log "CUTOVER COMPLETE. Verify:"
echo "   curl -s https://app.mumtaz.digital/api/v1/public/catalogue | head -c 120"
echo "   curl -s https://zaki.mumtaz.digital/health"
echo "   open https://mumtaz.digital  (new marketing)"
echo "   Login app.mumtaz.digital as $SUPER_ADMIN_EMAIL"
echo ""
echo "Rollback if needed: restore $BK/nginx → /etc/nginx, re-enable zaki-server, reload."
