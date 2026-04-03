#!/usr/bin/env bash
set -euo pipefail
DEPLOY_DIR="/opt/mumtaz"
VERSION="${1:-latest}"

cd "$DEPLOY_DIR"

git fetch origin
git checkout main
git pull origin main

echo "[mumtaz] deploying version=$VERSION"
docker compose -f docker-compose.production.yml --env-file .env.production pull || true
docker compose -f docker-compose.production.yml --env-file .env.production up -d --build
