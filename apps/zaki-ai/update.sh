#!/bin/bash
# update.sh — Pull latest code and restart ZAKI (run on the server)
# Usage: bash update.sh

set -e

DOMAIN="zaki.mumtaz.digital"
APP_DIR="/var/www/$DOMAIN"
BRANCH="claude/odoo-architecture-review-ujm0W"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== ZAKI — Update ==="

# Pull latest from git (if running from a cloned repo)
if [ -d "$REPO_DIR/.git" ] || git -C "$REPO_DIR" rev-parse --git-dir &>/dev/null; then
  echo "→ Pulling latest..."
  git -C "$(git -C "$REPO_DIR" rev-parse --show-toplevel)" fetch origin "$BRANCH"
  git -C "$(git -C "$REPO_DIR" rev-parse --show-toplevel)" checkout "$BRANCH"
  git -C "$(git -C "$REPO_DIR" rev-parse --show-toplevel)" pull origin "$BRANCH"
fi

# Sync app files
echo "→ Syncing files to $APP_DIR..."
rsync -av --exclude=node_modules --exclude=.env "$REPO_DIR/" "$APP_DIR/"

# Install any new dependencies
cd "$APP_DIR"
npm install --production
echo "✓ npm install done"

# Restart
pm2 restart zaki-ai
echo ""
echo "✅ ZAKI updated and restarted"
echo "   pm2 logs zaki-ai → view logs"
