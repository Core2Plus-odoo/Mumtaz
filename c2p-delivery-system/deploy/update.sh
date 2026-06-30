#!/usr/bin/env bash
# C2P update: pull the latest code, (re)link the served console, restart the API.
# Run this after pushing changes — replaces the old "git pull + manual copy" gap.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"        # .../c2p-delivery-system
WEB_DIR="$APP_DIR/web"

echo "==> Pulling latest code…"
git -C "$APP_DIR" pull --ff-only origin main

echo "==> Linking the served console (so the web root is always current)…"
mkdir -p "$WEB_DIR"
ln -sfn "$APP_DIR/console/c2p-delivery-console.html" "$WEB_DIR/index.html"

echo "==> Restarting the API…"
sudo systemctl restart delivery-api

echo "==> Health:"
curl -s http://127.0.0.1:8800/health && echo
echo "Done. Hard-refresh the browser (Ctrl+Shift+R / Cmd+Shift+R)."
