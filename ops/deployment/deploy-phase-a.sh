#!/bin/bash
# =============================================================
#  Mumtaz Phase A Deployment Script
#  Run this on the VPS (187.77.128.199) as root or with sudo
# =============================================================

set -e

REPO_DIR="/opt/mumtaz"
NGINX_CONF="$REPO_DIR/ops/deployment/nginx-mumtaz-platform.conf"
STATIC_DIR="/var/www/mumtaz.digital"

echo "=== Phase A: Mumtaz Platform Deployment ==="

# 1. Pull latest code
echo "[1/6] Pulling latest code..."
cd "$REPO_DIR"
git pull origin claude/odoo-architecture-review-ujm0W

# 2. Install nginx if not present
if ! command -v nginx &> /dev/null; then
    echo "[2/6] Installing nginx..."
    apt-get update && apt-get install -y nginx
else
    echo "[2/6] nginx already installed."
fi

# 3. Install certbot if not present
if ! command -v certbot &> /dev/null; then
    echo "[3/6] Installing certbot..."
    apt-get install -y certbot python3-certbot-nginx
else
    echo "[3/6] certbot already installed."
fi

# 4. Deploy nginx config
echo "[4/6] Deploying nginx config..."
cp "$NGINX_CONF" /etc/nginx/sites-available/mumtaz
ln -sf /etc/nginx/sites-available/mumtaz /etc/nginx/sites-enabled/mumtaz

# Remove default site if it exists
if [ -f /etc/nginx/sites-enabled/default ]; then
    rm -f /etc/nginx/sites-enabled/default
    echo "      Removed default nginx site."
fi

# Test config before reloading
nginx -t
systemctl reload nginx
echo "      nginx reloaded OK."

# 5. Ensure static site directory exists
echo "[5/6] Checking static site directory..."
if [ ! -d "$STATIC_DIR" ]; then
    mkdir -p "$STATIC_DIR"
    # Copy from repo if not already deployed
    if [ -d "$REPO_DIR/apps/website" ]; then
        cp -r "$REPO_DIR/apps/website/." "$STATIC_DIR/"
        echo "      Copied website assets to $STATIC_DIR"
    else
        echo "      WARNING: $REPO_DIR/apps/website not found."
    fi
else
    echo "      $STATIC_DIR already exists."
    # Sync latest assets
    if [ -d "$REPO_DIR/apps/website" ]; then
        rsync -a "$REPO_DIR/apps/website/." "$STATIC_DIR/"
        echo "      Synced latest website assets."
    fi
fi

# 6. Restart Odoo container to pick up new addons
echo "[6/6] Restarting Odoo to pick up mumtaz_api addon..."
cd "$REPO_DIR"
docker compose -f docker-compose.production.yml restart odoo
echo "      Waiting 15s for Odoo to start..."
sleep 15

# Check Odoo is up
if curl -sf http://127.0.0.1:8069/web/health > /dev/null 2>&1; then
    echo "      Odoo is UP."
else
    echo "      WARNING: Odoo health check failed — check logs with:"
    echo "      docker compose -f docker-compose.production.yml logs odoo"
fi

echo ""
echo "=== Phase A Deployment Complete ==="
echo ""
echo "Next steps:"
echo "  1. Add DNS records in Hostinger (if not done):"
echo "       zaki.mumtaz.digital        A  187.77.128.199"
echo "       marketplace.mumtaz.digital A  187.77.128.199"
echo "       admin.mumtaz.digital       A  187.77.128.199"
echo ""
echo "  2. After DNS propagates (5-60 min), add SSL:"
echo "       sudo certbot --nginx \\"
echo "         -d mumtaz.digital -d www.mumtaz.digital \\"
echo "         -d app.mumtaz.digital \\"
echo "         -d zaki.mumtaz.digital \\"
echo "         -d marketplace.mumtaz.digital \\"
echo "         -d admin.mumtaz.digital"
echo ""
echo "  3. Install mumtaz_api in Odoo:"
echo "       docker exec mumtaz-odoo-1 odoo -d <your_db_name> --stop-after-init -i mumtaz_api"
echo ""
echo "  4. Test routing:"
echo "       curl -I http://app.mumtaz.digital"
echo "       curl -I http://zaki.mumtaz.digital"
echo "       curl -I http://marketplace.mumtaz.digital"
echo "       curl -I http://admin.mumtaz.digital"
