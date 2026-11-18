#!/usr/bin/env bash
# deploy/pharma-staging/discover.sh — READ-ONLY look at the VPS before staging
# the "pharma" tenant. Changes nothing. Prints no secrets (passwords masked).
#
#   bash deploy/pharma-staging/discover.sh
set -uo pipefail

ODOO_CONF="${ODOO_CONF:-/etc/odoo/odoo.conf}"
DB=mumtaz_pharma
DOMAIN=pharma.mumtaz.digital

hr() { printf '\n== %s ==\n' "$1"; }

hr "host"
hostname; uptime; df -h / /opt 2>/dev/null | sed 1q; df -h / /opt 2>/dev/null | tail -n +2 | sort -u
free -h | head -2

hr "odoo runtime"
if systemctl list-units --type=service 2>/dev/null | grep -qE '^\s*odoo'; then
  systemctl list-units --type=service --no-pager 2>/dev/null | grep -E 'odoo' || true
  systemctl is-active odoo 2>/dev/null && echo "systemd unit 'odoo' is active"
fi
command -v odoo && odoo --version 2>/dev/null
if command -v docker >/dev/null 2>&1; then
  echo "-- docker containers mentioning odoo/postgres:"
  docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}' 2>/dev/null | grep -Ei 'odoo|postgres' || echo "(none)"
fi
echo "-- listeners on 8069/8072 (and neighbours):"
ss -ltnp 2>/dev/null | grep -E ':80(6[0-9]|7[0-9])\b' || echo "(none)"

hr "odoo.conf ($ODOO_CONF) — passwords masked"
if [ -r "$ODOO_CONF" ]; then
  sed -E 's/^(\s*(admin_passwd|db_password)\s*=).*/\1 <masked>/' "$ODOO_CONF"
else
  echo "not readable or missing: $ODOO_CONF  (set ODOO_CONF=... and re-run)"
  ls -la /etc/odoo* 2>/dev/null || true
fi

hr "dbfilter check"
if [ -r "$ODOO_CONF" ]; then
  f=$(grep -E '^\s*dbfilter\s*=' "$ODOO_CONF" | tail -1 | sed 's/.*=\s*//')
  echo "dbfilter = ${f:-<not set>}"
  [ "$f" = '^mumtaz_%d$' ] && echo "OK: host '$DOMAIN' resolves to DB '$DB'" \
                            || echo "NOTE: not ^mumtaz_%d\$ — '$DOMAIN' would NOT auto-select '$DB' (gate: config change needs approval)"
fi

hr "addons path contents (pharma_* present?)"
if [ -r "$ODOO_CONF" ]; then
  grep -E '^\s*addons_path' "$ODOO_CONF" | sed 's/.*=\s*//' | tr ',' '\n' | while read -r p; do
    p="${p## }"; [ -z "$p" ] && continue
    printf '%s -> ' "$p"; [ -d "$p" ] && { ls -d "$p"/pharma_* 2>/dev/null | tr '\n' ' '; echo "(dir ok)"; } || echo "MISSING"
  done
fi

hr "postgres: databases (names only)"
if command -v psql >/dev/null 2>&1; then
  sudo -u postgres psql -tAc "select datname from pg_database where not datistemplate order by 1" 2>/dev/null || echo "(psql as postgres failed — Postgres may be in Docker)"
  sudo -u postgres psql -tAc "select 1 from pg_database where datname='$DB'" 2>/dev/null | grep -q 1 \
    && echo "WARNING: $DB ALREADY EXISTS" || echo "OK: $DB does not exist yet"
fi

hr "checkouts"
for d in /opt/mumtaz /opt/custom_addons/Mumtaz /opt/mumtaz-jewel-staging /opt/mumtaz-pharma-staging; do
  [ -d "$d/.git" ] && printf '%s  branch=%s  head=%s\n' "$d" "$(git -C "$d" rev-parse --abbrev-ref HEAD)" "$(git -C "$d" rev-parse --short HEAD)"
done

hr "nginx"
nginx -v 2>&1
ls -la /etc/nginx/sites-enabled/ 2>/dev/null
echo "-- server_names:"; nginx -T 2>/dev/null | grep -E '^\s*server_name' | sort -u
echo "-- $DOMAIN present in nginx?"; nginx -T 2>/dev/null | grep -c "$DOMAIN" || true

hr "certificates"
certbot certificates 2>/dev/null | grep -E 'Certificate Name|Domains|Expiry' || echo "(certbot not available)"

hr "DNS (from this host)"
getent hosts "$DOMAIN" || echo "$DOMAIN does not resolve yet (A record needed: $DOMAIN -> this VPS)"
getent hosts erp.mumtaz.digital || true
echo "-- authoritative nameservers for mumtaz.digital:"; (dig +short NS mumtaz.digital 2>/dev/null || host -t NS mumtaz.digital 2>/dev/null) || echo "(dig/host not available)"

hr "done (nothing changed)"
