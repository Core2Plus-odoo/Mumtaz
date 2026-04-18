#!/bin/bash
# Mumtaz Platform — One-command deploy script
# Run on VPS: bash deploy-mumtaz.sh

set -e
REPO="/opt/custom_addons/Mumtaz"
BRANCH="claude/odoo-architecture-review-ujm0W"

echo "==> Pulling latest code..."
cd $REPO
git fetch origin $BRANCH
git checkout origin/$BRANCH -- zaki/index.html apps/portal/index.html ops/deployment/nginx-mumtaz-platform.conf

echo "==> Creating web directories..."
mkdir -p /var/www/mumtaz.digital
mkdir -p /var/www/zaki.mumtaz.digital
mkdir -p /var/www/app.mumtaz.digital

echo "==> Deploying files..."
cp zaki/index.html /var/www/zaki.mumtaz.digital/index.html
cp apps/portal/index.html /var/www/app.mumtaz.digital/index.html
cp apps/website/index.html /var/www/mumtaz.digital/index.html 2>/dev/null || true
cp -r apps/website/assets /var/www/mumtaz.digital/ 2>/dev/null || true

echo "==> Deploying nginx config..."
cp ops/deployment/nginx-mumtaz-platform.conf /etc/nginx/sites-available/mumtaz
ln -sf /etc/nginx/sites-available/mumtaz /etc/nginx/sites-enabled/mumtaz
rm -f /etc/nginx/sites-enabled/default

echo "==> Testing nginx config..."
nginx -t

echo "==> Reloading nginx..."
systemctl reload nginx

echo "==> Re-applying SSL certificates..."
certbot --nginx --reinstall --non-interactive \
  -d mumtaz.digital -d www.mumtaz.digital \
  -d app.mumtaz.digital \
  -d zaki.mumtaz.digital \
  -d marketplace.mumtaz.digital \
  -d admin.mumtaz.digital 2>/dev/null || true

nginx -t && systemctl reload nginx

echo ""
echo "✅ Deploy complete!"
echo ""
echo "Sites:"
echo "  https://mumtaz.digital       — Website"
echo "  https://app.mumtaz.digital   — Portal"
echo "  https://zaki.mumtaz.digital  — ZAKI CFO"
echo "  https://erp.mumtaz.digital   — ERP (Odoo)"
echo ""
echo "SSL (run once if not done):"
echo "  certbot --nginx -d mumtaz.digital -d www.mumtaz.digital -d app.mumtaz.digital -d zaki.mumtaz.digital -d erp.mumtaz.digital -d marketplace.mumtaz.digital -d admin.mumtaz.digital"
