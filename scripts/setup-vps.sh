#!/usr/bin/env bash
set -euo pipefail

echo "[mumtaz] Hostinger VPS setup starting..."
DEPLOY_USER="deploy"
DEPLOY_DIR="/opt/mumtaz"

sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release git nginx ufw certbot python3-certbot-nginx postgresql-client

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sudo sh /tmp/get-docker.sh
fi

if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  sudo useradd -m -s /bin/bash "$DEPLOY_USER"
fi
sudo usermod -aG docker "$DEPLOY_USER"

sudo mkdir -p "$DEPLOY_DIR"
sudo chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$DEPLOY_DIR"
sudo -u "$DEPLOY_USER" mkdir -p "$DEPLOY_DIR"/{backups,logs,ssl}

sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo "0 3 * * * /usr/bin/certbot renew --quiet && systemctl reload nginx" | sudo crontab -

echo "[mumtaz] setup complete. Next: clone repo in $DEPLOY_DIR and create .env.production"
