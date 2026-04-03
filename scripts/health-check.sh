#!/usr/bin/env bash
set -euo pipefail

for endpoint in \
  "http://localhost:8069/web" \
  "http://localhost:8069/web/session/info"; do
  curl -fsS "$endpoint" >/dev/null
  echo "OK: $endpoint"
done
