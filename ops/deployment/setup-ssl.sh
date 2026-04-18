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

echo ""
echo "=============================================="
echo "  Mumtaz Platform — Deploy + SSL Setup"
echo "=============================================="
echo ""

# ── Step 1: Pull latest code ───────────────────────────────
echo "[1/6] Pulling latest code..."
cd $REPO
git config --global --add safe.directory $REPO 2>/dev/null || true
git pull origin claude/odoo-architecture-review-ujm0W
echo "      ✓ Code updated"

# ── Step 2: Deploy static files ───────────────────────────
echo "[2/6] Deploying static files..."
mkdir -p /var/www/mumtaz.digital
mkdir -p /var/www/app.mumtaz.digital
mkdir -p /var/www/zaki.mumtaz.digital
mkdir -p /var/www/marketplace.mumtaz.digital

cp $REPO/apps/portal/index.html      /var/www/app.mumtaz.digital/index.html
cp $REPO/apps/marketplace/index.html /var/www/marketplace.mumtaz.digital/index.html
cp $REPO/apps/marketplace/vendor.html /var/www/marketplace.mumtaz.digital/vendor.html

# Deploy website if exists
if [ -d "$REPO/apps/website" ]; then
  cp -r $REPO/apps/website/. /var/www/mumtaz.digital/
fi

# Deploy zaki standalone if exists
if [ -f "$REPO/zaki/index.html" ]; then
  cp $REPO/zaki/index.html /var/www/zaki.mumtaz.digital/index.html
fi

echo "      ✓ Static files deployed"

# ── Step 3: Install Nginx config ──────────────────────────
echo "[3/6] Installing nginx config..."
cp $NGINX_CONF /etc/nginx/sites-available/mumtaz
ln -sf /etc/nginx/sites-available/mumtaz /etc/nginx/sites-enabled/mumtaz
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl reload nginx
echo "      ✓ Nginx config active"

# ── Step 4: Install Certbot ───────────────────────────────
echo "[4/6] Checking certbot..."
if ! command -v certbot &>/dev/null; then
  echo "      Installing certbot..."
  apt-get update -qq
  apt-get install -y certbot python3-certbot-nginx -qq
  echo "      ✓ Certbot installed"
else
  echo "      ✓ Certbot already installed"
fi

# ── Step 5: Obtain SSL certificates ───────────────────────
echo "[5/6] Obtaining SSL certificates..."
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
echo "[6/6] Setting up auto-renewal..."
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
