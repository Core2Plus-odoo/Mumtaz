#!/usr/bin/env bash
# Updates the Mumtaz marketing site at mumtaz.digital.
# Run on the VPS:  sudo bash /usr/local/bin/update-website
#
# What it does:
#   1. Clones the repo to /tmp
#   2. Detects (or creates) the nginx web root for mumtaz.digital
#   3. Rsyncs apps/website/ → that web root
#   4. Reloads nginx
#
# Set REPO_TOKEN as an env var if cloning a private repo.

set -euo pipefail

BRANCH="${BRANCH:-claude/odoo-architecture-review-ujm0W}"
REPO="${REPO:-core2plus-odoo/mumtaz}"
TMP_DIR="/tmp/mumtaz-website-deploy"
DOMAIN="mumtaz.digital"
DEFAULT_ROOT="/var/www/$DOMAIN"

echo "→ Cleaning $TMP_DIR"
rm -rf "$TMP_DIR"

CLONE_URL="https://github.com/$REPO.git"
[ -n "${REPO_TOKEN:-}" ] && CLONE_URL="https://$REPO_TOKEN@github.com/$REPO.git"

echo "→ Cloning branch $BRANCH"
git clone -b "$BRANCH" --depth 1 "$CLONE_URL" "$TMP_DIR"

# 1. Detect existing nginx web root for mumtaz.digital
NGINX_FILE="/etc/nginx/sites-enabled/$DOMAIN"
if [ ! -f "$NGINX_FILE" ] && [ ! -L "$NGINX_FILE" ]; then
    echo "→ No nginx config for $DOMAIN — installing one"
    cp "$TMP_DIR/apps/website/nginx.conf" "/etc/nginx/sites-available/$DOMAIN"
    ln -sf "/etc/nginx/sites-available/$DOMAIN" "$NGINX_FILE"
    NEW_CONFIG=1
fi

# Read root directory from nginx config
ROOT=$(grep -hE '^\s*root\s+' "$NGINX_FILE" 2>/dev/null \
        | head -1 | awk '{print $2}' | tr -d ';' || true)
ROOT="${ROOT:-$DEFAULT_ROOT}"
echo "→ Web root: $ROOT"

# 2. Make sure target directory exists
mkdir -p "$ROOT"

# 3. Rsync website files
echo "→ Syncing apps/website/ → $ROOT/"
rsync -av --delete \
    --exclude='nginx.conf' \
    --exclude='*.sh' \
    --exclude='README.md' \
    "$TMP_DIR/apps/website/" "$ROOT/"

chown -R www-data:www-data "$ROOT" 2>/dev/null || true

# 4. Reload nginx
if nginx -t 2>/dev/null; then
    systemctl reload nginx
    echo "→ Nginx reloaded"
else
    echo "✗ nginx config test failed — fix before reloading:"
    nginx -t
    exit 1
fi

# 5. Cleanup
rm -rf "$TMP_DIR"

echo
echo "✅ Website deployed to $ROOT"
[ "${NEW_CONFIG:-0}" = "1" ] && {
    echo
    echo "⚠  NEW nginx config installed. If you don't have an SSL cert yet, run:"
    echo "    sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
}
echo
echo "   Test: curl -I https://$DOMAIN"
