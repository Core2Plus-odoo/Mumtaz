#!/usr/bin/env bash
#
# Make jewel.mumtaz.digital live, once the DNS A record exists.
#
# Mirrors c2p-delivery-system/deploy/finish.sh, the script that put
# delivery.mumtaz.digital on this VPS, so it follows a path that has already
# worked here. Safe to re-run.
#
# RUN THIS ON THE VPS, AS ROOT, AND ONLY WITH A NAMED APPROVAL: it installs an
# nginx server block and issues a certificate, which are production
# infrastructure (docs/mumtaz-jewel/CLAUDE_CODE_HANDOFF.md, section 3).
#
# What it does NOT do: touch any other site's nginx config, touch
# docker-compose.production.yml or the shared Postgres, or call
# c2p-delivery-system/deploy/update.sh.
#
# Before it will work, YOU must first add the DNS record in Hostinger:
#   hPanel -> Domains -> mumtaz.digital -> DNS / Name Servers -> Manage DNS
#   Type A   Name jewel   Points to 187.77.128.199   TTL default
# That is the same way the `delivery` record was added. Nothing here can do
# it for you.
#
# Usage:
#   LETSENCRYPT_EMAIL=you@example.com deploy/jewel-staging/finish.sh
#   SKIP_DEMO=1 ... # landing page only, do not expect the Odoo demo to be up
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a

IP="${JEWEL_IP:-187.77.128.199}"
DOMAIN="jewel.mumtaz.digital"
EMAIL="${LETSENCRYPT_EMAIL:?set LETSENCRYPT_EMAIL to the address for certificate expiry notices}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
LANDING_SRC="$REPO_ROOT/website/jewel"
LANDING_DIR="/opt/mumtaz/jewel-landing"
CONF_SRC="$HERE/nginx/jewel.mumtaz.digital.conf"
CONF_DST="/etc/nginx/sites-available/jewel.mumtaz.digital.conf"
HTPASSWD="/etc/nginx/.htpasswd-jewel"

[ "$(id -u)" = "0" ] || { echo "Run as root."; exit 1; }
[ -f "$LANDING_SRC/index.html" ] || { echo "Missing $LANDING_SRC/index.html"; exit 1; }
[ -f "$CONF_SRC" ] || { echo "Missing $CONF_SRC"; exit 1; }

echo "== 1) landing page =="
mkdir -p "$LANDING_DIR" /opt/mumtaz/logs
cp -r "$LANDING_SRC/." "$LANDING_DIR/"
if grep -q "REPLACE-WITH-YOUR-EMAIL" "$LANDING_DIR/index.html"; then
  echo "   WARNING: the landing page still has REPLACE-WITH-YOUR-EMAIL in it."
  echo "   The demo buttons will not work until that is set."
fi
echo "   copied to $LANDING_DIR"

echo "== 2) demo password file =="
if [ -f "$HTPASSWD" ]; then
  echo "   $HTPASSWD exists, leaving it alone"
else
  echo "   $HTPASSWD is missing. The demo system is behind it, so create it:"
  echo "     apt-get install -y apache2-utils && htpasswd -c $HTPASSWD demo"
  echo "   Continuing: the landing page is public and does not need it."
fi

echo "== 3) DNS: waiting for $DOMAIN -> $IP =="
echo "   (add an A record 'jewel' -> $IP in Hostinger if you haven't)"
ok=""
for i in $(seq 1 40); do
  got="$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1)"
  if [ "$got" = "$IP" ]; then echo "   DNS OK: $got"; ok=1; break; fi
  echo "   not yet (got '${got:-none}') - retry in 15s [$i/40]"; sleep 15
done
[ -n "$ok" ] || { echo "   DNS still not pointing here. Add the A record, then re-run."; exit 1; }

echo "== 4) temporary HTTP block, so certbot can validate =="
# The real config references a certificate that does not exist yet, so nginx
# would refuse to start with it in place. Serve plain HTTP first.
mkdir -p /var/www/html
cat > /etc/nginx/sites-available/jewel-bootstrap.conf <<BOOTSTRAP
server {
    listen 80;
    server_name $DOMAIN;
    root $LANDING_DIR;
    index index.html;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { try_files \$uri \$uri/ /index.html; }
}
BOOTSTRAP
ln -sf /etc/nginx/sites-available/jewel-bootstrap.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/jewel.mumtaz.digital.conf
nginx -t || { echo "nginx config test failed"; exit 1; }
systemctl reload nginx

echo "== 5) certbot: issue the certificate =="
apt-get install -y -qq certbot >/dev/null
certbot certonly --webroot -w /var/www/html -d "$DOMAIN" \
  --agree-tos -m "$EMAIL" -n || { echo "certbot failed"; exit 1; }

echo "== 6) install the real server block =="
cp "$CONF_SRC" "$CONF_DST"
rm -f /etc/nginx/sites-enabled/jewel-bootstrap.conf
ln -sf "$CONF_DST" /etc/nginx/sites-enabled/
nginx -t || {
  echo "nginx rejected the real config; putting the bootstrap block back"
  rm -f /etc/nginx/sites-enabled/jewel.mumtaz.digital.conf
  ln -sf /etc/nginx/sites-available/jewel-bootstrap.conf /etc/nginx/sites-enabled/
  nginx -t && systemctl reload nginx
  exit 1
}
systemctl reload nginx

echo "== 7) checks =="
curl -s -o /dev/null -w "   https://$DOMAIN/            -> HTTP %{http_code}  (expect 200, the landing page)\n" "https://$DOMAIN/"
if [ "${SKIP_DEMO:-0}" = "1" ]; then
  echo "   SKIP_DEMO=1, not checking the demo system"
else
  curl -s -o /dev/null -w "   https://$DOMAIN/odoo        -> HTTP %{http_code}  (expect 401, the demo is password-gated)\n" "https://$DOMAIN/odoo"
  echo "   If that was 502, the Odoo stack is not running: ./deploy.sh --install --seed"
fi

echo
echo "Done. The landing page is live at https://$DOMAIN"
echo "The demo system is at https://$DOMAIN/odoo, behind the allow-list and password."
