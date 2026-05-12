#!/usr/bin/env bash
# Deploy Mumtaz ERP to /var/www/erp.mumtaz.digital
#
# Usage on VPS:
#   cd /opt/Mumtaz
#   git pull origin claude/odoo-architecture-review-ujm0W
#   sudo bash apps/erp/deploy.sh
#
# What this does:
#   1. Creates PostgreSQL DB + user (idempotent)
#   2. Installs Python deps for erp-server
#   3. Installs/reloads systemd service (erp-server on port 8002)
#   4. Syncs static frontend → /var/www/erp.mumtaz.digital
#   5. Installs nginx site config + reloads
#   6. Optionally gets SSL via certbot
set -euo pipefail

DOMAIN="erp.mumtaz.digital"
ERP_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$ERP_DIR/../.." && pwd)"
SERVER_DIR="$REPO_ROOT/apps/erp-server"
STATIC_DIR="$ERP_DIR/static"
DEST_DIR="/var/www/${DOMAIN}"
NGINX_AVAIL="/etc/nginx/sites-available/${DOMAIN}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${DOMAIN}"
SERVICE_NAME="erp-server"
VENV_DIR="/opt/erp-server/venv"
DB_NAME="mumtaz_erp"
DB_USER="erp_user"
DB_PASS="${ERP_DB_PASS:-erp_secure_pass_change_me}"
ERP_SECRET="${ERP_SECRET:-erp-secret-change-in-production}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Mumtaz ERP Deploy"
echo " domain: $DOMAIN"
echo " server: $SERVER_DIR"
echo " static: $STATIC_DIR → $DEST_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. PostgreSQL setup ───────────────────────────────────────
echo "→ Setting up PostgreSQL…"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
echo "✅ PostgreSQL ready"

# ── 2. Python virtualenv + deps ───────────────────────────────
echo "→ Installing Python dependencies…"
sudo mkdir -p /opt/erp-server
sudo python3 -m venv "$VENV_DIR"
sudo "$VENV_DIR/bin/pip" install --quiet --upgrade pip
sudo "$VENV_DIR/bin/pip" install --quiet -r "$SERVER_DIR/requirements.txt"
echo "✅ Python deps installed"

# ── 3. Systemd service ────────────────────────────────────────
echo "→ Installing systemd service…"
sudo cp "$SERVER_DIR/main.py" /opt/erp-server/main.py

sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=Mumtaz ERP Server
After=network.target postgresql.service

[Service]
User=www-data
WorkingDirectory=/opt/erp-server
Environment="ERP_DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@localhost/${DB_NAME}"
Environment="ERP_SECRET=${ERP_SECRET}"
ExecStart=${VENV_DIR}/bin/uvicorn main:app --host 127.0.0.1 --port 8002 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}
sleep 2
sudo systemctl is-active --quiet ${SERVICE_NAME} && echo "✅ $SERVICE_NAME is running" || echo "⚠️  $SERVICE_NAME failed to start — check: journalctl -u $SERVICE_NAME"

# ── 4. Sync static files ──────────────────────────────────────
echo "→ Syncing frontend…"
sudo mkdir -p "$DEST_DIR"
sudo rsync -av --delete \
    --exclude='*.sh' \
    "$STATIC_DIR/" "$DEST_DIR/"
sudo chown -R www-data:www-data "$DEST_DIR"
echo "✅ Frontend synced"

# ── 5. Nginx ──────────────────────────────────────────────────
echo "→ Installing nginx config…"
sudo cp "$ERP_DIR/nginx.conf" "$NGINX_AVAIL"
sudo ln -sf "$NGINX_AVAIL" "$NGINX_ENABLED"
sudo nginx -t
if sudo systemctl is-active --quiet nginx; then
    sudo systemctl reload nginx
else
    sudo systemctl start nginx
fi
echo "✅ Nginx reloaded"

# ── 6. SSL ────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if sudo certbot certificates 2>/dev/null | grep -q "$DOMAIN"; then
    echo "✅ SSL cert already exists for $DOMAIN."
    sudo certbot renew --quiet --nginx --cert-name "$DOMAIN" || true
else
    read -rp "   Get SSL cert for $DOMAIN now? [Y/n] " ans
    if [[ "${ans,,}" != "n" ]]; then
        sudo certbot --nginx -d "$DOMAIN"
    else
        echo "   Skipped — run later: sudo certbot --nginx -d $DOMAIN"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ERP deploy complete!"
echo "   Visit: https://${DOMAIN}"
echo ""
echo "   On first visit, you'll be prompted to:"
echo "   1. Set your company name and VAT number"
echo "   2. Create an admin account"
echo ""
echo "   Backend health check:"
echo "   curl http://localhost:8002/api/health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
