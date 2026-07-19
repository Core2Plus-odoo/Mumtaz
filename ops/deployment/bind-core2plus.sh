#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# bind-core2plus.sh — serve core2plus.com from a dedicated Odoo instance that is
# locked to ONLY the Mumtaz_C2P database.
#
# Run as root ON THE VPS, from the repo root (/opt/Mumtaz):
#   sudo bash ops/deployment/bind-core2plus.sh
#
# It derives db_password / addons_path / the longpolling option name from your
# LIVE /etc/odoo/odoo.conf so the new instance matches your install exactly.
# It does NOT run certbot (DNS must resolve first) — it prints the command.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SRC_CONF="${SRC_CONF:-/etc/odoo/odoo.conf}"
NEW_CONF="/etc/odoo-c2p.conf"
DB="${DB:-Mumtaz_C2P}"
DOMAIN="${DOMAIN:-core2plus.com}"
HTTP_PORT="${HTTP_PORT:-8071}"
LP_PORT="${LP_PORT:-8074}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"

echo "==> Source Odoo config : $SRC_CONF"
echo "==> New (C2P) config    : $NEW_CONF  (db=$DB, http=$HTTP_PORT, lp=$LP_PORT)"
echo "==> Domain              : $DOMAIN"

[[ -f "$SRC_CONF" ]] || { echo "✗ $SRC_CONF not found — set SRC_CONF=/path/to/odoo.conf" >&2; exit 1; }

# ── derive install-specific values from the live config ──────────────────────
get(){ grep -E "^[[:space:]]*$1[[:space:]]*=" "$SRC_CONF" | head -1 | sed -E "s/^[^=]*=[[:space:]]*//"; }
DB_PASSWORD="$(get db_password)"; DB_USER="$(get db_user)"; DB_HOST="$(get db_host)"
DB_PORT="$(get db_port)"; ADDONS="$(get addons_path)"
[[ -n "$ADDONS" ]] || { echo "✗ Could not read addons_path from $SRC_CONF" >&2; exit 1; }

# ── longpolling option name changed to gevent_port in Odoo 16 ────────────────
LP_OPT="gevent_port"
if odoo --version 2>/dev/null | grep -qE ' 1[0-5]\.'; then LP_OPT="longpolling_port"; fi
echo "==> Using '$LP_OPT = $LP_PORT' (per Odoo version)"

# ── free-port guard ──────────────────────────────────────────────────────────
for p in "$HTTP_PORT" "$LP_PORT"; do
  if ss -ltn "( sport = :$p )" 2>/dev/null | grep -q ":$p"; then
    echo "✗ Port $p is already in use — set HTTP_PORT/LP_PORT to free ports." >&2; exit 1
  fi
done

# ── write the dedicated config ───────────────────────────────────────────────
echo "==> Writing $NEW_CONF"
cat > "$NEW_CONF" <<EOF
[options]
db_host     = ${DB_HOST:-localhost}
db_port     = ${DB_PORT:-5432}
db_user     = ${DB_USER:-odoo}
db_password = ${DB_PASSWORD}
dbfilter    = ^${DB}\$
db_name     = ${DB}
http_port   = ${HTTP_PORT}
${LP_OPT} = ${LP_PORT}
proxy_mode  = True
workers     = 2
addons_path = ${ADDONS}
list_db     = False
logfile     = /var/log/odoo/odoo-c2p.log
log_level   = info
limit_memory_hard  = 2684354560
limit_memory_soft  = 2147483648
limit_time_cpu     = 120
limit_time_real    = 240
EOF
chown odoo:odoo "$NEW_CONF" 2>/dev/null || true
chmod 640 "$NEW_CONF"

# ── systemd service ──────────────────────────────────────────────────────────
echo "==> Installing systemd service odoo-c2p.service"
install -m 644 "$REPO/ops/deployment/odoo-c2p.service" /etc/systemd/system/odoo-c2p.service
systemctl daemon-reload
systemctl enable --now odoo-c2p.service
sleep 3
systemctl --no-pager --lines=0 status odoo-c2p.service || true

# ── nginx vhost ──────────────────────────────────────────────────────────────
echo "==> Installing nginx vhost for $DOMAIN"
if [[ -d /etc/nginx/sites-available ]]; then
  install -m 644 "$REPO/ops/deployment/nginx-core2plus.conf" "/etc/nginx/sites-available/$DOMAIN"
  ln -sfn "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
else
  install -m 644 "$REPO/ops/deployment/nginx-core2plus.conf" "/etc/nginx/conf.d/$DOMAIN.conf"
fi
nginx -t
systemctl reload nginx

echo ""
echo "✓ Dedicated Odoo instance is live on 127.0.0.1:$HTTP_PORT (Mumtaz_C2P only)."
echo "  Test locally:  curl -sI http://127.0.0.1:$HTTP_PORT/web/login | head -1"
echo ""
echo "Next — once DNS for $DOMAIN points to this server (A record → $(hostname -I | awk '{print $1}')):"
echo "  sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo ""
echo "Then open https://$DOMAIN — it will serve ONLY Mumtaz_C2P (no DB selector)."
