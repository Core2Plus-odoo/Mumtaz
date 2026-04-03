#!/usr/bin/env bash
set -euo pipefail
cd /opt/mumtaz

git fetch origin
git checkout develop
git pull origin develop
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build
