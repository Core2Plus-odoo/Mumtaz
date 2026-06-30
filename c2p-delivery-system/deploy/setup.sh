#!/usr/bin/env bash
#
# C2P Delivery System — one-shot installer for Ubuntu 24.04 (Hostinger VPS).
#
# Run from inside the unzipped package:
#     sudo bash deploy/setup.sh
#
# It installs dependencies, creates the Python service, sets up Nginx with a
# login gate, and asks you (right here, on your own server) for the few secrets
# it needs. Re-running it is safe — it updates rather than duplicates.

set -euo pipefail

# --- resolve paths -----------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"          # package root
API_DIR="$APP_DIR/delivery_api"
WEB_DIR="$APP_DIR/web"
ENV_FILE="$API_DIR/.env"
HTPASSWD="$APP_DIR/.htpasswd"
RUN_USER="${SUDO_USER:-root}"

echo "==> C2P Delivery System installer"
echo "    package: $APP_DIR"
echo "    user:    $RUN_USER"
echo

if [[ $EUID -ne 0 ]]; then
  echo "Please run with sudo:  sudo bash deploy/setup.sh"; exit 1
fi

# --- 1. system packages ------------------------------------------------------
echo "==> Installing system packages (python venv, nginx, htpasswd)…"
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip nginx apache2-utils >/dev/null

# --- 2. python environment ---------------------------------------------------
echo "==> Setting up the Python service…"
python3 -m venv "$API_DIR/.venv"
"$API_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$API_DIR/.venv/bin/pip" install --quiet -r "$API_DIR/requirements.txt"

# --- 3. secrets (.env) -------------------------------------------------------
if [[ -f "$ENV_FILE" ]]; then
  echo "==> $ENV_FILE already exists — keeping your existing secrets."
else
  echo "==> A few questions (these stay on this server, in $ENV_FILE):"
  read -rp "    Anthropic API key (sk-...): " ANTHROPIC_API_KEY
  read -rp "    Model id [claude-sonnet-4-6]: " C2P_MODEL; C2P_MODEL="${C2P_MODEL:-claude-sonnet-4-6}"
  read -rp "    Odoo URL [http://127.0.0.1:8069]: " ODOO_URL; ODOO_URL="${ODOO_URL:-http://127.0.0.1:8069}"
  read -rp "    Odoo login user [admin]: " ODOO_USER; ODOO_USER="${ODOO_USER:-admin}"
  read -rsp "    Odoo password: " ODOO_PASSWORD; echo
  cat > "$ENV_FILE" <<EOF
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
C2P_MODEL=$C2P_MODEL
ODOO_URL=$ODOO_URL
ODOO_USER=$ODOO_USER
ODOO_PASSWORD=$ODOO_PASSWORD
C2P_STORE=$API_DIR/delivery.db
C2P_CORS=*
EOF
  chmod 600 "$ENV_FILE"; chown "$RUN_USER":"$RUN_USER" "$ENV_FILE"
  echo "    Saved $ENV_FILE (readable only by you)."
fi

# --- 4. login gate (HTTP basic auth) ----------------------------------------
if [[ -f "$HTPASSWD" ]]; then
  echo "==> Login already configured — keeping it."
else
  echo "==> Set a login for the console (you'll type this in the browser):"
  read -rp "    Username: " AUTH_USER
  htpasswd -c "$HTPASSWD" "$AUTH_USER"
  chown "$RUN_USER":"$RUN_USER" "$HTPASSWD"
fi

# --- 5. web root (the console) ----------------------------------------------
echo "==> Publishing the console…"
mkdir -p "$WEB_DIR"
# Symlink (not copy) so `git pull` updates the served console with no extra step.
ln -sfn "$APP_DIR/console/c2p-delivery-console.html" "$WEB_DIR/index.html"

# --- 6. systemd service ------------------------------------------------------
echo "==> Installing the background service…"
sed -e "s|__API_DIR__|$API_DIR|g" \
    -e "s|__RUN_USER__|$RUN_USER|g" \
    "$SCRIPT_DIR/delivery-api.service.tmpl" > /etc/systemd/system/delivery-api.service
systemctl daemon-reload
systemctl enable --now delivery-api
systemctl restart delivery-api

# --- 7. nginx site -----------------------------------------------------------
echo "==> Configuring the web server…"
read -rp "    Domain or server IP for the console [_]: " SERVER_NAME; SERVER_NAME="${SERVER_NAME:-_}"
sed -e "s|__WEB_DIR__|$WEB_DIR|g" \
    -e "s|__HTPASSWD__|$HTPASSWD|g" \
    -e "s|__SERVER_NAME__|$SERVER_NAME|g" \
    "$SCRIPT_DIR/nginx-delivery.conf.tmpl" > /etc/nginx/sites-available/c2p-delivery
ln -sf /etc/nginx/sites-available/c2p-delivery /etc/nginx/sites-enabled/c2p-delivery
nginx -t
systemctl reload nginx

echo
echo "============================================================"
echo " Done. The delivery console is live."
echo
echo "   Open:   http://$SERVER_NAME/      (log in with the user you set)"
echo "   Service: systemctl status delivery-api"
echo "   Logs:    journalctl -u delivery-api -f"
echo
echo " To add HTTPS once your domain's DNS points here, run:"
echo "   sudo apt-get install -y certbot python3-certbot-nginx"
echo "   sudo certbot --nginx -d $SERVER_NAME"
echo "============================================================"
