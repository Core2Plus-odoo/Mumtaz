#!/usr/bin/env bash
# Deploys the Mumtaz hub (apps/portal) to /var/www/app.mumtaz.digital.
# Usage on the VPS:  sudo bash apps/portal/deploy.sh
set -euo pipefail

REPO_BRANCH="${REPO_BRANCH:-claude/odoo-architecture-review-ujm0W}"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST_DIR="/var/www/app.mumtaz.digital"

echo "→ Deploying portal from: $SRC_DIR"
echo "→ Target:                $DEST_DIR"

sudo mkdir -p "$DEST_DIR"

# Sync only the files the browser needs (skip nginx.conf, deploy.sh, .css fallback)
sudo rsync -av --delete \
    --exclude='nginx.conf' \
    --exclude='deploy.sh' \
    "$SRC_DIR/" "$DEST_DIR/"

sudo chown -R www-data:www-data "$DEST_DIR"

echo "✅ Portal deployed."
echo "   Test: curl -I https://app.mumtaz.digital"
