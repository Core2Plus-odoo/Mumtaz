#!/usr/bin/env bash
set -euo pipefail

cd /opt/mumtaz
git checkout HEAD~1
docker compose -f docker-compose.production.yml --env-file .env.production up -d --build
