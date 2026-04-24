#!/bin/bash
# =============================================================
#  Mumtaz Platform — Full Deploy Script
#  Run on VPS as root: bash /opt/Mumtaz/ops/deployment/deploy.sh
# =============================================================
set -e

REPO="/opt/Mumtaz"
CUSTOM="/opt/custom_addons/Mumtaz"
DB="Mumtaz_ERP"
ODOO_CONF="/etc/odoo/odoo.conf"
NGINX_CONF="/etc/nginx/sites-available/mumtaz"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Mumtaz Platform — Full Deploy          ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Pull latest code ───────────────────────────────────
echo "[1/6] Pulling latest code from git..."
cd $REPO
git pull origin claude/odoo-architecture-review-ujm0W
echo "      ✓ Code up to date"

# ── 2. Deploy static sites ────────────────────────────────
echo "[2/6] Deploying static files..."
mkdir -p /var/www/app.mumtaz.digital
mkdir -p /var/www/zaki.mumtaz.digital
mkdir -p /var/www/marketplace.mumtaz.digital
mkdir -p /var/www/mumtaz.digital

cp $REPO/apps/portal/index.html               /var/www/app.mumtaz.digital/index.html
cp $REPO/apps/zaki/static/index.html          /var/www/zaki.mumtaz.digital/index.html
cp $REPO/apps/marketplace/index.html          /var/www/marketplace.mumtaz.digital/index.html
cp $REPO/apps/marketplace/vendor.html         /var/www/marketplace.mumtaz.digital/vendor.html

if [ -d "$REPO/apps/website" ]; then
  cp -r $REPO/apps/website/. /var/www/mumtaz.digital/
fi

echo "      ✓ portal    → app.mumtaz.digital"
echo "      ✓ ZAKI      → zaki.mumtaz.digital"
echo "      ✓ marketplace → marketplace.mumtaz.digital"

# ── 3. Sync Odoo addons ───────────────────────────────────
echo "[3/6] Syncing Odoo addons..."
mkdir -p $CUSTOM

rm -rf $CUSTOM/mumtaz_theme
rm -rf $CUSTOM/mumtaz_marketplace
cp -r $REPO/addons/mumtaz_theme       $CUSTOM/
cp -r $REPO/addons/mumtaz_marketplace $CUSTOM/
echo "      ✓ mumtaz_theme synced"
echo "      ✓ mumtaz_marketplace synced"

# ── 4. Install / upgrade Odoo modules ─────────────────────
echo "[4/6] Installing/upgrading Odoo modules (this takes ~60s)..."
sudo -u odoo odoo \
  -c $ODOO_CONF \
  -d $DB \
  -i mumtaz_theme \
  -u mumtaz_marketplace \
  --stop-after-init \
  --logfile="" 2>&1 | grep -E "INFO.*modules|ERROR|ParseError|installed|upgraded" | tail -15

echo "      ✓ Odoo modules updated"

# ── 5. Update nginx config ────────────────────────────────
echo "[5/6] Updating nginx..."
cp $REPO/ops/deployment/nginx-mumtaz-platform.conf $NGINX_CONF
ln -sf $NGINX_CONF /etc/nginx/sites-enabled/mumtaz
rm -f /etc/nginx/sites-enabled/default

nginx -t 2>&1 | tail -3
systemctl reload nginx
echo "      ✓ Nginx reloaded"

# ── 6. Restart Odoo ───────────────────────────────────────
echo "[6/6] Restarting Odoo..."
systemctl restart odoo
sleep 4
systemctl is-active odoo && echo "      ✓ Odoo running" || echo "      ✗ Odoo failed — check: journalctl -u odoo -n 30"

# ── Done ──────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Deploy complete!                       ║"
echo "║                                          ║"
echo "║   https://app.mumtaz.digital             ║"
echo "║   https://zaki.mumtaz.digital            ║"
echo "║   https://erp.mumtaz.digital             ║"
echo "║   https://marketplace.mumtaz.digital     ║"
echo "╚══════════════════════════════════════════╝"
echo ""
