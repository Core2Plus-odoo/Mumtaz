#!/usr/bin/env bash
# Enable true server-side PDF generation (WeasyPrint). Optional: without it,
# documents still open the browser's Save-as-PDF dialog automatically.
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/delivery_api"
PIP="$API_DIR/.venv/bin/pip"

echo "==> Installing WeasyPrint system libraries…"
apt-get update -qq || true
# Ubuntu 24.04 package names (fall back to older names if needed).
apt-get install -y -qq libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
  libcairo2 libffi-dev fonts-dejavu >/dev/null 2>&1 \
  || apt-get install -y -qq libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
       libcairo2 libffi-dev fonts-dejavu >/dev/null 2>&1 || true

echo "==> Installing WeasyPrint into the API venv…"
"$PIP" install -q weasyprint || { echo "WeasyPrint install failed — the browser Save-as-PDF fallback still works."; exit 1; }

systemctl restart delivery-api
echo "==> Verifying…"
"$API_DIR/.venv/bin/python" -c "import weasyprint; print('WeasyPrint', weasyprint.__version__, 'ready')" \
  && echo "Done. Documents now download as real PDFs." \
  || echo "Imported with warnings — if PDFs don't render, the browser fallback still works."
