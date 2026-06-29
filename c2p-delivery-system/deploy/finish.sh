#!/usr/bin/env bash
# C2P finish: verify service, wait for DNS, issue HTTPS. Safe to re-run.
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a
IP="187.77.128.199"; DOMAIN="delivery.mumtaz.digital"; EMAIL="muhammad.umer@logitive.de"

echo "== 1) service =="
systemctl is-active delivery-api || { echo "service not active:"; journalctl -u delivery-api -n 20 --no-pager; exit 1; }

echo "== 2) backend health =="
curl -s http://127.0.0.1:8800/health; echo

echo "== 3) DNS: waiting for $DOMAIN -> $IP =="
echo "   (add an A record 'delivery' -> $IP in Hostinger if you haven't)"
ok=""
for i in $(seq 1 40); do
  got="$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1)"
  if [ "$got" = "$IP" ]; then echo "   DNS OK: $got"; ok=1; break; fi
  echo "   not yet (got '${got:-none}') - retry in 15s [$i/40]"; sleep 15
done
[ -n "$ok" ] || { echo "   DNS still not pointing here. Add the A record, then re-run this script."; exit 1; }

echo "== 4) certbot: install + issue TLS =="
apt-get install -y -qq certbot python3-certbot-nginx >/dev/null
certbot --nginx -d "$DOMAIN" --agree-tos -m "$EMAIL" --redirect -n

echo "== 5) HTTPS check (401 = TLS works and login gate is on) =="
curl -s -o /dev/null -w "   https://%{host} -> HTTP %{http_code}\n" "https://$DOMAIN/api/health" || true

echo
echo "Done. Open https://$DOMAIN and log in. Odoo wiring (bot key) is the only step left."
