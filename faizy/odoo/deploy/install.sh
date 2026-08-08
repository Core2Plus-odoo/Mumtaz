#!/usr/bin/env bash
#
# Faizy — one-shot installer for a SEPARATE Odoo Community 19 instance.
#
#   sudo bash faizy/odoo/deploy/install.sh
#
# Safe to re-run: every step checks before it acts, so a failed run can simply
# be repeated. Nothing it does touches the existing Mumtaz/C2P deployment — it
# uses its own database, system user, ports, service and nginx site.
#
# By default it serves on the server's IP at port 8080, so you get a working URL
# before DNS exists. Once the domain is ready:
#
#   sudo FAIZY_DOMAIN=faizy.example bash faizy/odoo/deploy/install.sh
#   sudo certbot --nginx -d faizy.example
#
# ⚠️ Plain HTTP on an IP means the login password crosses the network in the
# clear. That is acceptable for a short internal preview and NOT acceptable once
# real customer data exists. Move to the domain with TLS before anyone signs in
# who isn't you.

set -euo pipefail

# ── Settings (override by exporting before running) ─────────────────────────
FAIZY_DB="${FAIZY_DB:-faizy_prod}"
FAIZY_USER="${FAIZY_USER:-faizy}"
FAIZY_HOME="${FAIZY_HOME:-/opt/faizy}"
FAIZY_ODOO_PORT="${FAIZY_ODOO_PORT:-8079}"        # must not clash with Odoo's 8069
FAIZY_LONGPOLL_PORT="${FAIZY_LONGPOLL_PORT:-8078}"
FAIZY_PUBLIC_PORT="${FAIZY_PUBLIC_PORT:-8080}"    # nginx listens here
FAIZY_DOMAIN="${FAIZY_DOMAIN:-}"                  # empty = serve on the IP
FAIZY_BRANCH="${FAIZY_BRANCH:-claude/repo-audit-faizy-instance-fck6o3}"
FAIZY_REPO="${FAIZY_REPO:-https://github.com/Core2Plus-odoo/Mumtaz.git}"
ODOO_VERSION="${ODOO_VERSION:-19.0}"

SECRETS_FILE="/root/faizy-credentials.txt"

log()  { printf '\n\033[1;33m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;31m!!\033[0m %s\n' "$*"; }

[[ $EUID -eq 0 ]] || { warn "Run with sudo: sudo bash $0"; exit 1; }

# Refuse to collide with the existing instance rather than half-installing.
if ss -ltn 2>/dev/null | grep -q ":${FAIZY_ODOO_PORT}\b"; then
  warn "Port ${FAIZY_ODOO_PORT} is already in use. Set FAIZY_ODOO_PORT to a free port."
  exit 1
fi

# ── 1. Packages ─────────────────────────────────────────────────────────────
#
# apt aborts an entire batch when one name is unresolvable, which turns a single
# renamed package into "held broken packages" with no clue which one. So batches
# are retried one package at a time to name the culprit, and only the core set is
# fatal — the -dev headers merely let pip fall back to compiling from source when
# no wheel exists, which on a current distro is rare.

# Core: without these nothing works.
CORE_PKGS=(git python3-venv python3-dev python3-pip build-essential
           libpq-dev nginx postgresql-client)

# Build headers for the Python extensions Odoo pulls in (lxml, Pillow, ldap).
# Package names drift between releases — libtiff5-dev became libtiff-dev in
# Ubuntu 24.04, node-less was dropped entirely.
BUILD_PKGS=(libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev
            libtiff-dev libjpeg-dev libopenjp2-7-dev zlib1g-dev
            libfreetype6-dev liblcms2-dev libwebp-dev libharfbuzz-dev
            libfribidi-dev libxcb1-dev)

install_pkgs() {
  local fatal="$1"; shift
  local pkgs=("$@") missing=()

  if apt-get install -y -qq "${pkgs[@]}" >/dev/null 2>&1; then
    return 0
  fi

  for p in "${pkgs[@]}"; do
    apt-get install -y -qq "$p" >/dev/null 2>&1 || missing+=("$p")
  done

  if ((${#missing[@]})); then
    if [[ "$fatal" == "fatal" ]]; then
      warn "Could not install required packages: ${missing[*]}"
      warn "Check the names for this release: apt-cache search <name>"
      exit 1
    fi
    warn "Skipped unavailable build headers: ${missing[*]}"
    warn "Only matters if pip has to compile a package from source."
  fi
}

log "Installing system packages"
apt-get update -qq
install_pkgs fatal "${CORE_PKGS[@]}"
install_pkgs optional "${BUILD_PKGS[@]}"

# wkhtmltopdf powers PDF invoices. Odoo works without it; PDFs just fail.
if ! command -v wkhtmltopdf >/dev/null; then
  warn "wkhtmltopdf not installed — PDF invoices will not render."
  warn "Install the patched-qt build from wkhtmltopdf.org when you need them."
fi

# ── 2. System user ──────────────────────────────────────────────────────────
if id -u "$FAIZY_USER" >/dev/null 2>&1; then
  log "System user '$FAIZY_USER' already exists"
else
  log "Creating system user '$FAIZY_USER'"
  useradd -m -d "$FAIZY_HOME" -U -r -s /bin/bash "$FAIZY_USER"
fi
mkdir -p "$FAIZY_HOME"
chown "$FAIZY_USER":"$FAIZY_USER" "$FAIZY_HOME"

# ── 3. Database ─────────────────────────────────────────────────────────────
DB_PASSWORD="$(openssl rand -hex 24)"
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$FAIZY_USER'" | grep -q 1; then
  log "Postgres role '$FAIZY_USER' already exists — keeping its password"
  DB_PASSWORD="$(grep -oP '(?<=^DB_PASSWORD=).*' "$SECRETS_FILE" 2>/dev/null || true)"
  if [[ -z "$DB_PASSWORD" ]]; then
    warn "Existing role but no stored password. Resetting it."
    DB_PASSWORD="$(openssl rand -hex 24)"
    sudo -u postgres psql -qc "ALTER ROLE $FAIZY_USER WITH PASSWORD '$DB_PASSWORD';"
  fi
else
  log "Creating Postgres role '$FAIZY_USER'"
  sudo -u postgres createuser --createdb "$FAIZY_USER"
  sudo -u postgres psql -qc "ALTER ROLE $FAIZY_USER WITH PASSWORD '$DB_PASSWORD';"
fi

if sudo -u postgres psql -tAlq | cut -d'|' -f1 | grep -qw "$FAIZY_DB"; then
  log "Database '$FAIZY_DB' already exists"
else
  log "Creating database '$FAIZY_DB'"
  sudo -u postgres createdb --owner="$FAIZY_USER" "$FAIZY_DB"
fi

# ── 4. Odoo source and virtualenv ───────────────────────────────────────────
if [[ -d "$FAIZY_HOME/odoo/.git" ]]; then
  log "Odoo source present — fetching latest $ODOO_VERSION"
  sudo -u "$FAIZY_USER" git -C "$FAIZY_HOME/odoo" fetch --depth 1 origin "$ODOO_VERSION"
  sudo -u "$FAIZY_USER" git -C "$FAIZY_HOME/odoo" reset --hard FETCH_HEAD
else
  log "Cloning Odoo $ODOO_VERSION (this is the slow step — a few minutes)"
  sudo -u "$FAIZY_USER" git clone --depth 1 --branch "$ODOO_VERSION" \
    https://github.com/odoo/odoo.git "$FAIZY_HOME/odoo"
fi

if [[ ! -x "$FAIZY_HOME/venv/bin/python3" ]]; then
  log "Creating the Python virtualenv"
  sudo -u "$FAIZY_USER" python3 -m venv "$FAIZY_HOME/venv"
fi
log "Installing Python dependencies"
sudo -u "$FAIZY_USER" "$FAIZY_HOME/venv/bin/pip" install --quiet --upgrade pip wheel setuptools
sudo -u "$FAIZY_USER" "$FAIZY_HOME/venv/bin/pip" install --quiet -r "$FAIZY_HOME/odoo/requirements.txt"

# ── 5. Faizy addons ─────────────────────────────────────────────────────────
if [[ -d "$FAIZY_HOME/src/.git" ]]; then
  log "Updating Faizy addons"
  sudo -u "$FAIZY_USER" git -C "$FAIZY_HOME/src" fetch origin "$FAIZY_BRANCH"
  sudo -u "$FAIZY_USER" git -C "$FAIZY_HOME/src" checkout -B "$FAIZY_BRANCH" "origin/$FAIZY_BRANCH"
else
  log "Cloning the Faizy addons"
  sudo -u "$FAIZY_USER" git clone --branch "$FAIZY_BRANCH" "$FAIZY_REPO" "$FAIZY_HOME/src"
fi
ADDONS_PATH="$FAIZY_HOME/odoo/addons,$FAIZY_HOME/src/faizy/odoo/addons"

# ── 6. Configuration ────────────────────────────────────────────────────────
CONF="$FAIZY_HOME/odoo.conf"
if [[ -f "$CONF" ]]; then
  log "Keeping the existing $CONF"
else
  log "Writing $CONF"
  MASTER_PASSWORD="$(openssl rand -hex 24)"
  cat > "$CONF" <<EOF
[options]
admin_passwd = $MASTER_PASSWORD
db_host = localhost
db_port = 5432
db_user = $FAIZY_USER
db_password = $DB_PASSWORD

; Pinned to one database so the login page cannot enumerate the others on this
; box, and the database manager is not reachable from the internet.
db_name = $FAIZY_DB
dbfilter = ^${FAIZY_DB}\$
list_db = False

addons_path = $ADDONS_PATH
data_dir = $FAIZY_HOME/data

; Loopback only — nginx is the sole public entrance.
http_interface = 127.0.0.1
http_port = $FAIZY_ODOO_PORT
gevent_port = $FAIZY_LONGPOLL_PORT
proxy_mode = True

workers = 3
limit_time_cpu = 120
limit_time_real = 240
logfile = /var/log/faizy/odoo.log
log_level = info
EOF
  chmod 640 "$CONF"
  chown "$FAIZY_USER":"$FAIZY_USER" "$CONF"

  umask 077
  cat > "$SECRETS_FILE" <<EOF
# Faizy instance credentials — generated $(date -u +%FT%TZ)
# Readable by root only. Do not commit, do not paste into chat.
DB_PASSWORD=$DB_PASSWORD
ODOO_MASTER_PASSWORD=$MASTER_PASSWORD
EOF
  chmod 600 "$SECRETS_FILE"
fi

mkdir -p /var/log/faizy "$FAIZY_HOME/data"
chown -R "$FAIZY_USER":"$FAIZY_USER" /var/log/faizy "$FAIZY_HOME/data"

# ── 7. Service ──────────────────────────────────────────────────────────────
log "Installing the systemd service"
cat > /etc/systemd/system/faizy-odoo.service <<EOF
[Unit]
Description=Faizy Odoo
After=network.target postgresql.service

[Service]
Type=simple
User=$FAIZY_USER
ExecStart=$FAIZY_HOME/venv/bin/python3 $FAIZY_HOME/odoo/odoo-bin -c $CONF
Restart=always
RestartSec=5
KillMode=mixed

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable faizy-odoo >/dev/null

# ── 8. Modules ──────────────────────────────────────────────────────────────
#
# Captured rather than streamed. Odoo prints a lot of docutils noise from its own
# core modules' descriptions, and under `set -e` a real failure would otherwise
# scroll past as the script died silently — leaving that harmless noise as the
# last thing on screen and looking like the cause.
log "Installing faizy_core and faizy_website (Odoo must be stopped for this)"
systemctl stop faizy-odoo 2>/dev/null || true

INSTALL_LOG="/var/log/faizy/module-install.log"
if sudo -u "$FAIZY_USER" "$FAIZY_HOME/venv/bin/python3" "$FAIZY_HOME/odoo/odoo-bin" \
     -c "$CONF" -d "$FAIZY_DB" -i faizy_core,faizy_website --stop-after-init \
     > "$INSTALL_LOG" 2>&1; then
  log "Modules installed"
else
  warn "Module installation failed. Last 40 lines of $INSTALL_LOG:"
  echo "------------------------------------------------------------"
  # Skip the docutils chatter so the genuine traceback is what you see.
  grep -vE '^<string>:[0-9]+: \((ERROR|WARNING|INFO)/' "$INSTALL_LOG" | tail -40
  echo "------------------------------------------------------------"
  warn "Full log: $INSTALL_LOG"
  exit 1
fi

systemctl start faizy-odoo

# ── 9. nginx ────────────────────────────────────────────────────────────────
log "Configuring nginx"
if [[ -n "$FAIZY_DOMAIN" ]]; then
  LISTEN="listen 80;"
  SERVER_NAME="server_name $FAIZY_DOMAIN www.$FAIZY_DOMAIN;"
  PUBLIC_URL="http://$FAIZY_DOMAIN"
else
  # No domain yet: a dedicated port so this cannot disturb whatever already
  # answers on 80.
  LISTEN="listen $FAIZY_PUBLIC_PORT;"
  SERVER_NAME="server_name _;"
  IP="$(hostname -I | awk '{print $1}')"
  PUBLIC_URL="http://$IP:$FAIZY_PUBLIC_PORT"
fi

cat > /etc/nginx/sites-available/faizy <<EOF
upstream faizy_odoo     { server 127.0.0.1:$FAIZY_ODOO_PORT; }
upstream faizy_longpoll { server 127.0.0.1:$FAIZY_LONGPOLL_PORT; }

server {
    $LISTEN
    $SERVER_NAME

    access_log /var/log/nginx/faizy.access.log;
    error_log  /var/log/nginx/faizy.error.log;

    client_max_body_size 25M;   # CNIC scans and proof-of-delivery photos

    proxy_set_header Host              \$host;
    proxy_set_header X-Real-IP         \$remote_addr;
    proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_read_timeout 720s;

    # Long-polling needs its own upstream or realtime updates stall.
    location /longpolling { proxy_pass http://faizy_longpoll; }
    location /websocket   { proxy_pass http://faizy_longpoll; }

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
EOF

ln -sf /etc/nginx/sites-available/faizy /etc/nginx/sites-enabled/faizy
nginx -t
systemctl reload nginx

if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
  log "Opening port $FAIZY_PUBLIC_PORT in ufw"
  ufw allow "$FAIZY_PUBLIC_PORT/tcp" >/dev/null || true
fi

# ── 10. Health ──────────────────────────────────────────────────────────────
log "Waiting for Odoo to come up"
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$FAIZY_ODOO_PORT/web/login" >/dev/null; then
    HEALTHY=1; break
  fi
  sleep 2
done

echo
echo "============================================================"
if [[ -n "${HEALTHY:-}" ]]; then
  echo " Faizy is live:  $PUBLIC_URL"
else
  echo " Odoo did not answer in 60s. Check: journalctl -u faizy-odoo -n 50"
fi
echo
echo " Credentials:    $SECRETS_FILE  (root only)"
echo " Service:        systemctl status faizy-odoo"
echo " Logs:           journalctl -u faizy-odoo -f"
echo
echo " First login creates the admin user for database '$FAIZY_DB'."
echo
if [[ -z "$FAIZY_DOMAIN" ]]; then
  echo " ⚠️  Plain HTTP on an IP — the password crosses the network in the clear."
  echo "    Fine for an internal look. Before anyone else signs in:"
  echo "      sudo FAIZY_DOMAIN=your-domain bash $0"
  echo "      sudo certbot --nginx -d your-domain"
fi
echo "============================================================"
