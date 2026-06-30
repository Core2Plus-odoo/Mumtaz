#!/usr/bin/env bash
# Enable the branded single-admin login and remove the nginx Basic-Auth popup.
# Safe to re-run (idempotent). Run as root on the VPS.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"          # .../c2p-delivery-system
API_DIR="$APP_DIR/delivery_api"
ENV="$API_DIR/.env"
NGINX_SITE="/etc/nginx/sites-available/c2p-delivery"
PYBIN="$API_DIR/.venv/bin/python"

[[ -f "$ENV" ]] || { echo "No .env at $ENV — run setup.sh first."; exit 1; }

read -rp "Admin username [admin]: " ADMIN_USER; ADMIN_USER="${ADMIN_USER:-admin}"
read -rsp "Admin password: " ADMIN_PW; echo
[[ -n "$ADMIN_PW" ]] || { echo "Password cannot be empty."; exit 1; }

# Hash the password (pbkdf2) so no plaintext sits in .env.
HASH="$(cd "$API_DIR" && "$PYBIN" -c 'import sys,tenancy; print(tenancy.hash_password(sys.argv[1]))' "$ADMIN_PW")"

set_env() {                                       # idempotent KEY=VALUE in .env
  local k="$1" v="$2"
  sed -i "/^${k}=/d" "$ENV"
  printf '%s=%s\n' "$k" "$v" >> "$ENV"
}

# Keep an existing JWT secret if there is one; otherwise mint a strong one.
if ! grep -q '^C2P_JWT_SECRET=' "$ENV"; then
  set_env C2P_JWT_SECRET "$(openssl rand -hex 32)"
fi
set_env C2P_ADMIN_AUTH 1
set_env C2P_ADMIN_USER "$ADMIN_USER"
set_env C2P_ADMIN_PASSWORD_HASH "$HASH"
sed -i '/^C2P_ADMIN_PASSWORD=/d' "$ENV"           # drop any old plaintext password
echo "==> .env updated (admin auth on, password hashed, JWT secret set)."

# Remove the nginx Basic-Auth gate (the app now handles login). Leaves the
# acme-challenge 'auth_basic off;' line untouched.
if [[ -f "$NGINX_SITE" ]] && grep -q 'auth_basic .*C2P' "$NGINX_SITE"; then
  cp "$NGINX_SITE" "${NGINX_SITE}.bak.$(date +%s 2>/dev/null || echo bak)" 2>/dev/null || true
  sed -i '/auth_basic .*C2P Delivery/d; /auth_basic_user_file/d' "$NGINX_SITE"
  nginx -t && systemctl reload nginx
  echo "==> nginx Basic-Auth popup removed; reloaded."
else
  echo "==> nginx Basic-Auth already absent — nothing to change."
fi

systemctl restart delivery-api
echo
echo "Done. Open the console and sign in as '$ADMIN_USER'."
echo "Hard-refresh the browser (Ctrl+Shift+R)."
