#!/usr/bin/env bash
#
# Faizy — put the instance on a real domain with TLS.
#
#   sudo CERTBOT_EMAIL=you@example.com bash faizy/odoo/deploy/setup-domain.sh myfaizy.com
#
# Safe to re-run. Everything it does is idempotent: the nginx site is rewritten
# from scratch, certbot skips a certificate that is still valid, and the Odoo
# settings are writes of the same values.
#
# It does not disturb the other sites on this box — C2P/Mumtaz and IG2 share
# ports 80 and 443 through name-based virtual hosting, and the block written
# here carries an explicit server_name and is never `default_server`.
#
# It does not ask you to take that on trust. Before touching anything it
# records how every other vhost on the box answers, backs up /etc/nginx, and
# re-checks all of them at the end — reporting a difference and pointing at the
# backup rather than leaving you to find out from their users. It also refuses
# outright if the domain you asked for is already served by another site.
#
# Run it only once DNS is pointing here — there is a preflight check below that
# refuses otherwise, because a certbot failure at that point leaves a
# half-configured vhost and a rate-limit counter that is easy to exhaust.

set -euo pipefail

DOMAIN="${1:-${FAIZY_DOMAIN:-}}"
FAIZY_DB="${FAIZY_DB:-faizy_prod}"
FAIZY_USER="${FAIZY_USER:-faizy}"
FAIZY_HOME="${FAIZY_HOME:-/opt/faizy}"
FAIZY_ODOO_PORT="${FAIZY_ODOO_PORT:-8079}"
FAIZY_LONGPOLL_PORT="${FAIZY_LONGPOLL_PORT:-8078}"
FAIZY_PUBLIC_PORT="${FAIZY_PUBLIC_PORT:-8080}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"
WITH_WWW="${WITH_WWW:-1}"
CONF="$FAIZY_HOME/odoo.conf"

log()  { printf '\n\033[1;33m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;31m!!\033[0m %s\n' "$*"; }

[[ $EUID -eq 0 ]] || { warn "Run with sudo: sudo bash $0 <domain>"; exit 1; }
[[ -n "$DOMAIN" ]] || { warn "Usage: sudo bash $0 myfaizy.com"; exit 1; }
[[ -f "$CONF" ]] || { warn "$CONF not found — run install.sh first."; exit 1; }

# ── 1. Preflight: is DNS actually pointing here? ────────────────────────────
#
# This is the check worth having. certbot proves control of the domain by
# answering an HTTP request Let's Encrypt sends to whatever IP the A record
# names. If that is still Hostinger's shared hosting, the challenge lands on
# the wrong server and fails — and five failures an hour trips a rate limit
# that locks the domain out for the rest of the hour.

log "Checking DNS for $DOMAIN"
command -v dig >/dev/null || apt-get install -y --no-install-recommends dnsutils >/dev/null

SERVER_IP="$(curl -fsS --max-time 10 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')"
DOMAIN_IP="$(dig +short A "$DOMAIN" | tail -1)"

echo "    this server : ${SERVER_IP:-unknown}"
echo "    $DOMAIN : ${DOMAIN_IP:-<no A record>}"

if [[ -z "$DOMAIN_IP" ]]; then
  warn "$DOMAIN has no A record yet."
  cat <<TXT

  In Hostinger hPanel:
    Domains -> $DOMAIN -> DNS / Nameservers -> DNS records

  The apex must be an A record pointing here:

    Type  Name   Content          TTL
    A     @      $SERVER_IP    300

  For www, either is fine — keep whichever already exists rather than adding
  a second one, because two records for the same name is the failure that
  looks like a propagation delay:

    CNAME www    $DOMAIN        (follows the apex; nothing to update later)
    A     www    $SERVER_IP    (independent; must be changed alongside @)

  Check the nameservers on the same page first. Hostinger's own are
  *.dns-parking.com — if they say anything else, the DNS records page here
  does nothing and the change belongs wherever those nameservers are managed.

  Then wait for it to propagate and re-run this script. Check with:
    dig +short A $DOMAIN

TXT
  exit 1
fi

if [[ "$DOMAIN_IP" != "$SERVER_IP" ]]; then
  warn "$DOMAIN points at $DOMAIN_IP, but this server is $SERVER_IP."
  echo "    Point the A record here and wait for the old TTL to expire."
  echo "    Refusing to run certbot — a failed challenge burns rate limit."
  exit 1
fi

# www is optional: if it does not resolve here, ask for a certificate without
# it rather than failing the whole run over a name nobody has set up.
CERT_DOMAINS=(-d "$DOMAIN")
if [[ "$WITH_WWW" == "1" ]]; then
  WWW_IP="$(dig +short A "www.$DOMAIN" | tail -1)"
  if [[ "$WWW_IP" == "$SERVER_IP" ]]; then
    CERT_DOMAINS+=(-d "www.$DOMAIN")
    SERVER_NAMES="$DOMAIN www.$DOMAIN"
  else
    warn "www.$DOMAIN does not point here (${WWW_IP:-<none>}) — continuing without it."
    SERVER_NAMES="$DOMAIN"
    WITH_WWW=0
  fi
else
  SERVER_NAMES="$DOMAIN"
fi

# ── 2. Protect the neighbours ───────────────────────────────────────────────
#
# This box also serves C2P/Mumtaz and IG2. nginx routes by hostname, so a new
# named vhost cannot steal their traffic — but "cannot" is a claim, and the
# whole point of a deploy script is to not need claims. So: record how every
# other site answers right now, and check the same answers again at the end.
#
# The probes go to 127.0.0.1 with an explicit Host header, which tests nginx's
# own routing without depending on DNS or leaving the machine.

NEIGHBOUR_NAMES=()
for site in /etc/nginx/sites-enabled/*; do
  [[ -e "$site" ]] || continue
  [[ "$(basename "$site")" == "faizy" ]] && continue
  while read -r name; do
    [[ "$name" == "_" || -z "$name" ]] && continue
    [[ "$name" == "$DOMAIN" || "$name" == "www.$DOMAIN" ]] && {
      warn "$name is already served by $(basename "$site") — refusing to fight over it."
      exit 1
    }
    NEIGHBOUR_NAMES+=("$name")
  done < <(grep -hoP '^\s*server_name\s+\K[^;]+' "$site" 2>/dev/null | tr ' ' '\n' | sort -u)
done

probe() {  # probe <hostname> -> "http_code/https_code"
  local host="$1" http https
  http="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 \
          -H "Host: $host" http://127.0.0.1/ 2>/dev/null || echo 000)"
  https="$(curl -ksS -o /dev/null -w '%{http_code}' --max-time 10 \
           -H "Host: $host" https://127.0.0.1/ 2>/dev/null || echo 000)"
  echo "$http/$https"
}

declare -A BEFORE=()
if [[ ${#NEIGHBOUR_NAMES[@]} -gt 0 ]]; then
  log "Recording how the other sites answer, so we can prove we did not break them"
  for name in "${NEIGHBOUR_NAMES[@]}"; do
    BEFORE["$name"]="$(probe "$name")"
    echo "    $name -> ${BEFORE[$name]}"
  done
fi

# certbot edits nginx config in place. A dated copy costs nothing and is the
# difference between "restore it" and "reconstruct it from memory".
BACKUP="/root/nginx-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
tar czf "$BACKUP" -C /etc nginx 2>/dev/null && log "nginx config backed up to $BACKUP"

# ── 3. nginx ────────────────────────────────────────────────────────────────
log "Writing the nginx site for $SERVER_NAMES"

cat > /etc/nginx/sites-available/faizy <<EOF
# Generated by faizy/odoo/deploy/setup-domain.sh — re-run it rather than
# editing here, or the next run will overwrite your changes.

# A websocket handshake needs the Upgrade and Connection headers passed
# through, and nginx only forwards them over HTTP/1.1. Without this the
# handshake is answered with 400 and Odoo's realtime bus never connects —
# chatter stops updating live and nothing says why.
#
# Deliberately a Faizy-specific variable name: this box serves C2P, IG2 and
# the mumtaz.digital sites from the same nginx, and a second `map` defining
# \$connection_upgrade would be a duplicate-directive error that takes every
# vhost down at reload.
map \$http_upgrade \$faizy_connection_upgrade {
    default upgrade;
    ''      close;
}

upstream faizy_odoo     { server 127.0.0.1:$FAIZY_ODOO_PORT; }
upstream faizy_longpoll { server 127.0.0.1:$FAIZY_LONGPOLL_PORT; }

server {
    listen 80;
    listen [::]:80;
    server_name $SERVER_NAMES;

    access_log /var/log/nginx/faizy.access.log;
    error_log  /var/log/nginx/faizy.error.log;

    client_max_body_size 25M;   # CNIC scans and proof-of-delivery photos

    proxy_set_header Host              \$host;
    proxy_set_header X-Real-IP         \$remote_addr;
    proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_read_timeout 720s;

    # Long-polling and websockets need their own upstream or realtime updates
    # stall — the chatter stops refreshing and nobody knows why.
    location /longpolling { proxy_pass http://faizy_longpoll; }
    location /websocket {
        proxy_pass http://faizy_longpoll;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    \$http_upgrade;
        proxy_set_header Connection \$faizy_connection_upgrade;
    }

    location / {
        proxy_pass http://faizy_odoo;
        proxy_redirect off;
    }

    location ~* /web/static/ {
        proxy_cache_valid 200 90m;
        proxy_pass http://faizy_odoo;
        expires 864000;
    }

    gzip on;
    gzip_types text/css text/plain application/javascript application/json image/svg+xml;
}

# The IP:$FAIZY_PUBLIC_PORT preview served the login form over plain HTTP. Now
# that a real hostname exists it redirects instead of serving, so a bookmarked
# preview URL cannot quietly go on sending passwords in the clear.
server {
    listen $FAIZY_PUBLIC_PORT;
    listen [::]:$FAIZY_PUBLIC_PORT;
    server_name _;
    return 301 https://$DOMAIN\$request_uri;
}
EOF

ln -sf /etc/nginx/sites-available/faizy /etc/nginx/sites-enabled/faizy
nginx -t
systemctl reload nginx

if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
  log "Opening 80 and 443 in ufw"
  ufw allow 80/tcp  >/dev/null || true
  ufw allow 443/tcp >/dev/null || true
fi

# ── 4. TLS ──────────────────────────────────────────────────────────────────
log "Requesting a certificate"
if ! command -v certbot >/dev/null; then
  apt-get install -y --no-install-recommends certbot python3-certbot-nginx
fi

# --keep-until-expiring matters for re-runs: this script rewrites the nginx
# site from scratch each time, wiping certbot's own edits, so certbot has to
# run again to put them back. Without the flag it would prompt about the
# existing certificate and then fail, because --non-interactive cannot answer.
CERTBOT_ARGS=(
  --nginx "${CERT_DOMAINS[@]}"
  --redirect --non-interactive --agree-tos --keep-until-expiring
)
if [[ -n "$CERTBOT_EMAIL" ]]; then
  CERTBOT_ARGS+=(-m "$CERTBOT_EMAIL")
else
  # No address means no expiry warnings. Renewal is automatic, but when it
  # breaks — and eventually it does — silence is how you find out via a
  # customer instead of an email.
  warn "No CERTBOT_EMAIL set; registering without expiry notifications."
  CERTBOT_ARGS+=(--register-unsafely-without-email)
fi

if certbot "${CERTBOT_ARGS[@]}"; then
  log "Certificate installed"
else
  warn "certbot failed. The site is up on http://$DOMAIN but NOT on https."
  warn "Check /var/log/letsencrypt/letsencrypt.log, fix, and re-run this script."
  exit 1
fi

systemctl reload nginx

# ── 5. Tell Odoo its own address ────────────────────────────────────────────
#
# Odoo builds absolute URLs — password resets, portal links, invoice PDFs, the
# WhatsApp messages this app sends — from web.base.url. Left unset it stays at
# the IP, so a customer gets a link to a host with no certificate.
#
# web.base.url.freeze matters just as much: without it Odoo REWRITES base url
# to whatever host the next administrator logged in through. One admin session
# over the raw IP and every link generated afterwards points back at the IP.

log "Setting the Odoo base URL"
BASE_URL="https://$DOMAIN"

sudo -u "$FAIZY_USER" "$FAIZY_HOME/venv/bin/python3" "$FAIZY_HOME/odoo/odoo-bin" \
  shell -c "$CONF" -d "$FAIZY_DB" --logfile= --no-http <<PY
params = env["ir.config_parameter"].sudo()
params.set_param("web.base.url", "$BASE_URL")
params.set_param("web.base.url.freeze", "True")

website = env["website"].sudo().search([], limit=1)
if website:
    website.domain = "$BASE_URL"

env.cr.commit()
print("web.base.url =", params.get_param("web.base.url"))
print("website.domain =", website.domain if website else "<no website record>")
PY

systemctl restart faizy-odoo

# ── 6. Did we break the neighbours? ─────────────────────────────────────────
#
# Checked after certbot, because certbot is the step that rewrites config it
# did not write. If any other site answers differently than it did at the
# start, say so loudly and point at the backup — a silent regression on C2P or
# IG2 would be found by their users, not by us.

if [[ ${#NEIGHBOUR_NAMES[@]} -gt 0 ]]; then
  log "Re-checking the other sites"
  REGRESSED=0
  for name in "${NEIGHBOUR_NAMES[@]}"; do
    after="$(probe "$name")"
    if [[ "$after" == "${BEFORE[$name]}" ]]; then
      echo "    $name -> $after  (unchanged)"
    else
      warn "$name changed: ${BEFORE[$name]} -> $after"
      REGRESSED=1
    fi
  done
  if [[ "$REGRESSED" == "1" ]]; then
    warn "Another site on this box now answers differently."
    warn "Restore with:  tar xzf $BACKUP -C /etc && nginx -t && systemctl reload nginx"
    exit 1
  fi
  log "Every other site answers exactly as before"
fi

# ── 7. Health ───────────────────────────────────────────────────────────────
log "Checking $BASE_URL"
sleep 3
CODE="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 20 "$BASE_URL" || echo 000)"
if [[ "$CODE" =~ ^(200|30[0-9])$ ]]; then
  log "Faizy is live at $BASE_URL (HTTP $CODE)"
else
  warn "Got HTTP $CODE from $BASE_URL — check: journalctl -u faizy-odoo -n 50"
  warn "and /var/log/nginx/faizy.error.log"
  exit 1
fi

cat <<TXT

  Done.

    Site      $BASE_URL
    Backend   $BASE_URL/odoo
    Renewal   certbot renews automatically; check with
              systemctl list-timers | grep certbot

  Worth doing now that the login page is on HTTPS: change the admin password
  if it is still the one from install, since every session before this one
  crossed the network in the clear.

TXT
