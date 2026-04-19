#!/bin/bash
# =============================================================
#  Mumtaz Platform — SSL + Full Deploy Script
#  Run as root on the VPS
#  Usage: bash setup-ssl.sh
# =============================================================
set -e

DOMAINS="-d mumtaz.digital -d www.mumtaz.digital -d app.mumtaz.digital -d erp.mumtaz.digital -d zaki.mumtaz.digital -d marketplace.mumtaz.digital -d admin.mumtaz.digital"
EMAIL="admin@mumtaz.digital"
REPO="/opt/Mumtaz"
NGINX_CONF="$REPO/ops/deployment/nginx-mumtaz-platform.conf"
ZAKI_FRONTEND="$REPO/apps/zaki/frontend"

echo ""
echo "=============================================="
echo "  Mumtaz Platform — Deploy + SSL Setup"
echo "=============================================="
echo ""

# ── Step 1: Pull latest code ───────────────────────────────
echo "[1/7] Pulling latest code..."
cd $REPO
git config --global --add safe.directory $REPO 2>/dev/null || true
git pull origin claude/odoo-architecture-review-ujm0W
echo "      ✓ Code updated"

# ── Step 2: Build ZAKI Next.js frontend ───────────────────
echo "[2/7] Building ZAKI Next.js frontend..."
if command -v node &>/dev/null; then
  cd $ZAKI_FRONTEND
  # Install deps if node_modules missing
  [ ! -d node_modules ] && npm install --silent
  npm run build
  echo "      ✓ ZAKI frontend built → out/"
  cd $REPO
else
  echo "      ⚠  Node.js not found — skipping ZAKI build (install with: curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs)"
fi

# ── Step 3: Deploy static files ───────────────────────────
echo "[3/7] Deploying static files..."
mkdir -p /var/www/mumtaz.digital
mkdir -p /var/www/app.mumtaz.digital
mkdir -p /var/www/zaki.mumtaz.digital
mkdir -p /var/www/marketplace.mumtaz.digital

cp $REPO/apps/portal/index.html       /var/www/app.mumtaz.digital/index.html
cp $REPO/apps/marketplace/index.html  /var/www/marketplace.mumtaz.digital/index.html
cp $REPO/apps/marketplace/vendor.html /var/www/marketplace.mumtaz.digital/vendor.html

# Deploy website
if [ -d "$REPO/apps/website" ]; then
  cp -r $REPO/apps/website/. /var/www/mumtaz.digital/
fi

# Deploy ZAKI static export
if [ -d "$ZAKI_FRONTEND/out" ]; then
  rm -rf /var/www/zaki.mumtaz.digital/*
  cp -r $ZAKI_FRONTEND/out/. /var/www/zaki.mumtaz.digital/
  echo "      ✓ ZAKI static export deployed"
else
  echo "      ⚠  ZAKI out/ not found — zaki.mumtaz.digital will show blank page until built"
fi

echo "      ✓ Static files deployed"

# ── Step 4: Install Nginx config ──────────────────────────
echo "[4/7] Installing nginx config..."
cp $NGINX_CONF /etc/nginx/sites-available/mumtaz
ln -sf /etc/nginx/sites-available/mumtaz /etc/nginx/sites-enabled/mumtaz
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl reload nginx
echo "      ✓ Nginx config active"

# ── Step 5: Install Certbot ───────────────────────────────
echo "[5/7] Checking certbot..."
if ! command -v certbot &>/dev/null; then
  echo "      Installing certbot..."
  apt-get update -qq
  apt-get install -y certbot python3-certbot-nginx -qq
  echo "      ✓ Certbot installed"
else
  echo "      ✓ Certbot already installed"
fi

# ── Step 5b: Obtain SSL certificates ──────────────────────
echo "[6/7] Obtaining SSL certificates..."
echo "      This may take 1-2 minutes..."
certbot --nginx \
  $DOMAINS \
  --email $EMAIL \
  --agree-tos \
  --non-interactive \
  --redirect \
  --keep-until-expiring
echo "      ✓ SSL certificates obtained"

# ── Step 6: Enable auto-renewal ───────────────────────────
echo "[7/7] Configuring auto-renewal..."
systemctl enable certbot.timer 2>/dev/null || true
# Add cron if systemd timer not available
if ! systemctl is-active certbot.timer &>/dev/null; then
  (crontab -l 2>/dev/null | grep -v certbot; echo "0 3 * * * certbot renew --quiet && systemctl reload nginx") | crontab -
fi
echo "      ✓ Auto-renewal configured"

# ── Final reload ──────────────────────────────────────────
systemctl reload nginx

echo ""
echo "=============================================="
echo "  ✅  All done!"
echo "=============================================="
echo ""
echo "  https://mumtaz.digital"
echo "  https://app.mumtaz.digital"
echo "  https://erp.mumtaz.digital"
echo "  https://zaki.mumtaz.digital"
echo "  https://marketplace.mumtaz.digital"
echo "  https://admin.mumtaz.digital"
echo ""
echo "  SSL renews automatically every 60 days."
echo "=============================================="
