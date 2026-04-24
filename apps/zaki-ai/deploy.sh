#!/bin/bash
# deploy.sh — Deploy ZAKI to zaki.mumtaz.digital
# Run once on your server as root (or with sudo)
# Usage: bash deploy.sh

set -e

DOMAIN="zaki.mumtaz.digital"
APP_DIR="/var/www/$DOMAIN"
LOG_DIR="/var/log/zaki"
REPO="https://github.com/core2plus-odoo/mumtaz"   # adjust if needed
BRANCH="claude/odoo-architecture-review-ujm0W"

echo "=== ZAKI AI — Deploy to $DOMAIN ==="

# 1. Install Node.js 22 (if not present)
if ! command -v node &>/dev/null; then
  echo "→ Installing Node.js 22..."
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi
echo "✓ Node $(node -v)"

# 2. Install PM2 (if not present)
if ! command -v pm2 &>/dev/null; then
  echo "→ Installing PM2..."
  npm install -g pm2
fi
echo "✓ PM2 $(pm2 -v)"

# 3. Install nginx + certbot (if not present)
if ! command -v nginx &>/dev/null; then
  echo "→ Installing nginx..."
  apt-get install -y nginx
fi
if ! command -v certbot &>/dev/null; then
  echo "→ Installing certbot..."
  apt-get install -y certbot python3-certbot-nginx
fi

# 4. Create directories
mkdir -p "$APP_DIR" "$LOG_DIR"

# 5. Copy app files (assumes you've cloned the repo or are running from it)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "→ Copying app from $SCRIPT_DIR to $APP_DIR..."
rsync -av --exclude=node_modules --exclude=.env "$SCRIPT_DIR/" "$APP_DIR/"

# 6. Set up .env (will prompt if ANTHROPIC_API_KEY not set)
if [ ! -f "$APP_DIR/.env" ]; then
  echo ""
  echo "Enter your Anthropic API key:"
  read -r ANTHROPIC_KEY
  cat > "$APP_DIR/.env" <<EOF
ANTHROPIC_API_KEY=$ANTHROPIC_KEY
SESSION_SECRET=$(openssl rand -hex 32)
PORT=3000
NODE_ENV=production
ODOO_BASE_URL=https://aj-arabia.odoo.com
ODOO_DB=aj-arabia
EOF
  echo "✓ .env created"
fi

# 7. Install dependencies
cd "$APP_DIR"
npm install --production
echo "✓ npm install done"

# 8. Set up nginx
NGINX_CONF="/etc/nginx/sites-available/$DOMAIN"
cp "$APP_DIR/nginx.conf" "$NGINX_CONF"
ln -sf "$NGINX_CONF" "/etc/nginx/sites-enabled/$DOMAIN"
nginx -t && systemctl reload nginx
echo "✓ nginx configured"

# 9. SSL via Let's Encrypt
echo "→ Obtaining SSL certificate..."
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@mumtaz.digital --redirect
echo "✓ SSL certificate installed"

# 10. Start with PM2
cp "$APP_DIR/ecosystem.config.js" "$APP_DIR/ecosystem.config.js"
sed -i "s|/var/www/zaki.mumtaz.digital|$APP_DIR|g" "$APP_DIR/ecosystem.config.js"
pm2 delete zaki-ai 2>/dev/null || true
pm2 start "$APP_DIR/ecosystem.config.js"
pm2 save
pm2 startup | tail -1 | bash   # enable restart on server reboot

echo ""
echo "✅ ZAKI is live at https://$DOMAIN"
echo "   pm2 logs zaki-ai    → view logs"
echo "   pm2 restart zaki-ai → restart"
