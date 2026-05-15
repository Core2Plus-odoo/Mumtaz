#!/usr/bin/env bash
# Deploy Mumtaz Marketplace static site to /var/www/marketplace.mumtaz.digital
#
# Usage on VPS:
#   cd /opt/Mumtaz
#   git pull origin claude/odoo-architecture-review-ujm0W
#   sudo bash apps/marketplace/deploy.sh
#
# What this does:
#   1. Syncs marketplace HTML/CSS/JS → /var/www/marketplace.mumtaz.digital
#   2. Installs nginx site config (idempotent)
#   3. Reloads nginx
#   4. Optionally gets SSL via certbot
set -euo pipefail

DOMAIN="marketplace.mumtaz.digital"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST_DIR="/var/www/${DOMAIN}"
NGINX_AVAIL="/etc/nginx/sites-available/${DOMAIN}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${DOMAIN}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Mumtaz Marketplace Deploy"
echo " src:    $SRC_DIR"
echo " dest:   $DEST_DIR"
echo " domain: $DOMAIN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Sync static files ──────────────────────────────────────────────
echo "→ Syncing marketplace files…"
sudo mkdir -p "$DEST_DIR"
sudo rsync -av --delete \
    --exclude='deploy.sh' \
    --exclude='nginx.conf' \
    --exclude='*.sh' \
    "$SRC_DIR/" "$DEST_DIR/"
sudo chown -R www-data:www-data "$DEST_DIR"
echo "✅ Marketplace files synced to $DEST_DIR"

# ── 2. Install nginx config ───────────────────────────────────────────
echo "→ Installing nginx config…"
sudo tee "$NGINX_AVAIL" > /dev/null <<NGINX_EOF
server {
    listen 80;
    server_name ${DOMAIN};

    root ${DEST_DIR};
    index index.html;

    # Gzip
    gzip on;
    gzip_types text/html text/css application/javascript application/json image/svg+xml;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location ~* \.(css|js|svg|png|jpg|jpeg|webp|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
NGINX_EOF

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
echo " SSL Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v certbot &>/dev/null; then
    read -rp "Get/renew SSL certificate for ${DOMAIN}? [y/N] " yn
    if [[ "$yn" =~ ^[Yy]$ ]]; then
        sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
            --email "${SSL_EMAIL:-admin@mumtaz.digital}" --redirect
        echo "✅ SSL certificate obtained"
    fi
else
    echo "  certbot not installed — skipping SSL"
    echo "  Install: apt-get install certbot python3-certbot-nginx"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✅ Marketplace deployed!"
echo " URL: https://${DOMAIN}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
