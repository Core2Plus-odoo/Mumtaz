#!/usr/bin/env bash
# Deploy the Mumtaz portal (apps/portal) to /var/www/app.mumtaz.digital.
#
# Usage on the VPS:
#   cd /home/user/Mumtaz
#   git pull origin claude/odoo-architecture-review-ujm0W
#   sudo bash apps/portal/deploy.sh
#
# What this does:
#   1. Syncs portal HTML/CSS/JS → /var/www/app.mumtaz.digital
#   2. Installs the nginx site config (idempotent)
#   3. Reloads nginx
#   4. Optionally gets/renews SSL via certbot (prompt)
set -euo pipefail

DOMAIN="app.mumtaz.digital"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST_DIR="/var/www/${DOMAIN}"
NGINX_AVAIL="/etc/nginx/sites-available/${DOMAIN}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${DOMAIN}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Mumtaz Portal Deploy"
echo " src:    $SRC_DIR"
echo " dest:   $DEST_DIR"
echo " domain: $DOMAIN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Sync static files ──────────────────────────────────────────────
echo "→ Syncing portal files…"
sudo mkdir -p "$DEST_DIR"
sudo rsync -av --delete \
    --exclude='nginx.conf' \
    --exclude='deploy.sh' \
    --exclude='*.sh' \
    --exclude='onboarding.css' \
    "$SRC_DIR/" "$DEST_DIR/"
sudo chown -R www-data:www-data "$DEST_DIR"
echo "✅ Portal files synced to $DEST_DIR"

# ── 2. Install nginx config ───────────────────────────────────────────
echo "→ Installing nginx config…"
sudo cp "$SRC_DIR/nginx.conf" "$NGINX_AVAIL"
sudo ln -sf "$NGINX_AVAIL" "$NGINX_ENABLED"
echo "✅ Nginx config installed"

# ── 3. Test + reload nginx ────────────────────────────────────────────
echo "→ Testing nginx config…"
sudo nginx -t
echo "→ Reloading nginx…"
if sudo systemctl is-active --quiet nginx; then
    sudo systemctl reload nginx
else
    sudo systemctl start nginx
fi
echo "✅ Nginx reloaded"

# ── 4. SSL (certbot) ─────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if sudo certbot certificates 2>/dev/null | grep -q "$DOMAIN"; then
    echo "✅ SSL cert already exists for $DOMAIN."
    echo "   Renewing if near expiry:"
    sudo certbot renew --quiet --nginx --cert-name "$DOMAIN" || true
else
    read -rp "   Get SSL cert for $DOMAIN now? [Y/n] " ans
    if [[ "${ans,,}" != "n" ]]; then
        sudo certbot --nginx -d "$DOMAIN"
    else
        echo "   Skipped — site is HTTP-only. Run later:"
        echo "   sudo certbot --nginx -d $DOMAIN"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Portal deploy complete!"
echo "   Visit: https://${DOMAIN}"
echo ""
echo "   Also verify zaki-server is running:"
echo "   pm2 list"
echo "   curl http://localhost:8001/api/v1/health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
