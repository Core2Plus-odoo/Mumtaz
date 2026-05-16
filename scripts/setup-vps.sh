#!/usr/bin/env bash
# One-shot VPS setup for Mumtaz Digital Platform
#
# Run as root (or with sudo) on a fresh Ubuntu 22.04 / 24.04 VPS:
#   git clone ... /opt/Mumtaz && cd /opt/Mumtaz
#   sudo bash scripts/setup-vps.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ZAKI_DIR="/opt/zaki-server"
ERP_DIR="/opt/erp-server"
PORTAL_DIR="/var/www/app.mumtaz.digital"
DEPLOY_USER="${SUDO_USER:-deploy}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Mumtaz VPS Setup"
echo " Repo: $REPO_DIR"
echo " User: $DEPLOY_USER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. System packages ────────────────────────────────────────────────
echo "→ Installing system packages…"
apt-get update -q
apt-get install -y -q \
    git nginx ufw certbot python3-certbot-nginx \
    python3 python3-pip python3-venv \
    sqlite3 rsync curl wget \
    ca-certificates gnupg lsb-release

# ── 2. Node.js 20 + npm ───────────────────────────────────────────────
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 18 ]]; then
    echo "→ Installing Node.js 20…"
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# ── 3. PM2 ───────────────────────────────────────────────────────────
if ! command -v pm2 >/dev/null 2>&1; then
    echo "→ Installing PM2…"
    npm install -g pm2
fi

# ── 4. Firewall ───────────────────────────────────────────────────────
echo "→ Configuring firewall…"
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# ── 5. Directories ───────────────────────────────────────────────────
echo "→ Creating service directories…"
mkdir -p "$ZAKI_DIR" "$ERP_DIR" "$PORTAL_DIR"

# ── 6. Copy server code ───────────────────────────────────────────────
echo "→ Copying server code…"
rsync -a --delete --exclude='__pycache__' --exclude='*.pyc' \
    "$REPO_DIR/apps/zaki-server/" "$ZAKI_DIR/"
rsync -a --delete --exclude='__pycache__' --exclude='*.pyc' \
    "$REPO_DIR/apps/erp-server/"  "$ERP_DIR/"

# ── 7. Python virtual envs + deps ────────────────────────────────────
echo "→ Installing Python dependencies for zaki-server…"
python3 -m venv "$ZAKI_DIR/.venv"
"$ZAKI_DIR/.venv/bin/pip" install -q --upgrade pip
"$ZAKI_DIR/.venv/bin/pip" install -q -r "$ZAKI_DIR/requirements.txt"

echo "→ Installing Python dependencies for erp-server…"
python3 -m venv "$ERP_DIR/.venv"
"$ERP_DIR/.venv/bin/pip" install -q --upgrade pip
"$ERP_DIR/.venv/bin/pip" install -q -r "$ERP_DIR/requirements.txt"

# ── 8. Environment files ──────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Environment Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Create .env for zaki-server if it doesn't exist
if [[ ! -f "$ZAKI_DIR/.env" ]]; then
    cat > "$ZAKI_DIR/.env" <<'ENVEOF'
# Mumtaz ZAKI Server — environment variables
# Edit all change_me values before starting the service!

# Odoo connection
ODOO_URL=http://localhost:8069
ODOO_DB=mumtaz
ODOO_MASTER_PASS=change_me
ODOO_ADMIN_USER=admin@mumtaz.digital
ODOO_ADMIN_PASS=change_me

# Security
JWT_SECRET=change_me
ANTHROPIC_API_KEY=sk-ant-change_me

# Database
DB_PATH=/opt/zaki-server/users.db

# Email
EMAIL_FROM=noreply@mumtaz.digital
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# Server
PORTAL_HOST=app.mumtaz.digital
CORS_ORIGINS=https://app.mumtaz.digital
ENVEOF
    echo "  Created $ZAKI_DIR/.env — EDIT THIS FILE before starting services!"
else
    echo "  $ZAKI_DIR/.env already exists — skipping"
fi

# Create .env for erp-server if it doesn't exist
if [[ ! -f "$ERP_DIR/.env" ]]; then
    cat > "$ERP_DIR/.env" <<'ENVEOF'
# Mumtaz ERP Server — environment variables
ODOO_URL=http://localhost:8069
ODOO_ADMIN=admin@mumtaz.digital
ODOO_PASS=change_me
ERP_SECRET=change_me
ENVEOF
    echo "  Created $ERP_DIR/.env — EDIT THIS FILE before starting services!"
else
    echo "  $ERP_DIR/.env already exists — skipping"
fi

# ── 9. PM2 ecosystem file ─────────────────────────────────────────────
# zaki-server runs on port 8002 to avoid conflict with existing zaki-ai (8001).
# Nginx for app.mumtaz.digital proxies /api/* → 8002.
cat > /opt/mumtaz-pm2.config.js <<PMEOF
module.exports = {
  apps: [
    {
      name:          'zaki-server',
      cwd:           '${ZAKI_DIR}',
      script:        '${ZAKI_DIR}/.venv/bin/uvicorn',
      args:          'main:app --host 127.0.0.1 --port 8002',
      env_file:      '${ZAKI_DIR}/.env',
      max_restarts:  10,
      restart_delay: 3000,
      error_file:    '/var/log/zaki-server.err.log',
      out_file:      '/var/log/zaki-server.out.log',
    },
    {
      name:          'erp-server',
      cwd:           '${ERP_DIR}',
      script:        '${ERP_DIR}/.venv/bin/uvicorn',
      args:          'main:app --host 127.0.0.1 --port 8003',
      env_file:      '${ERP_DIR}/.env',
      max_restarts:  10,
      restart_delay: 3000,
      error_file:    '/var/log/erp-server.err.log',
      out_file:      '/var/log/erp-server.out.log',
    },
  ],
};
PMEOF
echo "→ PM2 ecosystem written to /opt/mumtaz-pm2.config.js"

# ── 10. Portal static files ───────────────────────────────────────────
echo "→ Deploying portal static files…"
rsync -a --delete \
    --exclude='nginx.conf' --exclude='deploy.sh' --exclude='*.sh' \
    "$REPO_DIR/apps/portal/" "$PORTAL_DIR/"
chown -R www-data:www-data "$PORTAL_DIR"

# ── 11. Nginx ─────────────────────────────────────────────────────────
echo "→ Installing nginx config…"
NGINX_CONF="/etc/nginx/sites-available/app.mumtaz.digital"
cp "$REPO_DIR/apps/portal/nginx.conf" "$NGINX_CONF"
ln -sf "$NGINX_CONF" "/etc/nginx/sites-enabled/app.mumtaz.digital"
nginx -t && systemctl reload nginx

# ── 12. SSL renewal cron ──────────────────────────────────────────────
echo "0 3 * * * root certbot renew --quiet && systemctl reload nginx" \
    > /etc/cron.d/certbot-renew

# ── 13. Domain update cron ───────────────────────────────────────────
chmod +x "$REPO_DIR/scripts/update-nginx-domains.sh"
echo "*/10 * * * * root DB_PATH=/opt/zaki-server/users.db bash $REPO_DIR/scripts/update-nginx-domains.sh" \
    > /etc/cron.d/mumtaz-tenant-domains

# ── 14. Odoo addons path ─────────────────────────────────────────────
echo "→ Deploying addons & patching odoo.conf…"
bash "$REPO_DIR/apps/addons/deploy.sh"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Setup complete!"
echo ""
echo " REQUIRED — Edit these files before starting:"
echo "   $ZAKI_DIR/.env"
echo "   $ERP_DIR/.env"
echo ""
echo " Then start services:"
echo "   pm2 start /opt/mumtaz-pm2.config.js"
echo "   pm2 save && pm2 startup"
echo ""
echo " Get SSL cert:"
echo "   certbot --nginx -d app.mumtaz.digital"
echo ""
echo " Verify:"
echo "   pm2 list"
echo "   curl http://localhost:8002/api/v1/health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
