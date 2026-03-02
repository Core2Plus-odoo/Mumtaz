#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   sudo bash deployment/make_odoo_detect_mumtaz.sh <DB_NAME> [ODOO_CONF] [ODOO_SERVICE]
# Example:
#   sudo bash deployment/make_odoo_detect_mumtaz.sh mydb /etc/odoo/odoo.conf odoo

DB_NAME="${1:-}"
ODOO_CONF="${2:-/etc/odoo/odoo.conf}"
ODOO_SERVICE="${3:-odoo}"
REPO_PATH="/workspace/Mumtaz"

if [[ -z "$DB_NAME" ]]; then
  echo "ERROR: DB_NAME is required."
  echo "Usage: sudo bash deployment/make_odoo_detect_mumtaz.sh <DB_NAME> [ODOO_CONF] [ODOO_SERVICE]"
  exit 1
fi

if [[ ! -f "$ODOO_CONF" ]]; then
  echo "ERROR: Odoo config not found: $ODOO_CONF"
  exit 1
fi

if [[ ! -d "$REPO_PATH" ]]; then
  echo "ERROR: Repo path not found: $REPO_PATH"
  exit 1
fi

echo "[1/6] Checking Mumtaz module structure..."
python3 "$REPO_PATH/deployment/check_mumtaz_modules.py"

echo "[2/6] Updating addons_path in $ODOO_CONF ..."
python3 - "$ODOO_CONF" "$REPO_PATH" <<'PY'
from pathlib import Path
import sys

conf = Path(sys.argv[1])
repo = sys.argv[2]
text = conf.read_text()
lines = text.splitlines()
updated = False
for i, line in enumerate(lines):
    if line.strip().startswith("addons_path"):
        key, val = line.split("=", 1)
        paths = [p.strip() for p in val.split(",") if p.strip()]
        if repo not in paths:
            paths.append(repo)
            lines[i] = f"{key.strip()} = {','.join(paths)}"
        updated = True
        break

if not updated:
    lines.append(f"addons_path = {repo}")

conf.write_text("\n".join(lines) + "\n")
print("addons_path updated")
PY

echo "[3/6] Fixing ownership/permissions for $REPO_PATH ..."
chown -R odoo:odoo "$REPO_PATH"
find "$REPO_PATH" -type d -exec chmod 755 {} \;
find "$REPO_PATH" -type f -exec chmod 644 {} \;
chmod +x "$REPO_PATH/deployment/check_mumtaz_modules.py" "$REPO_PATH/deployment/make_odoo_detect_mumtaz.sh"

echo "[4/6] Restarting service: $ODOO_SERVICE ..."
systemctl restart "$ODOO_SERVICE"
systemctl --no-pager --full status "$ODOO_SERVICE" | head -n 20

echo "[5/6] Refreshing apps list in database: $DB_NAME ..."
sudo -u odoo /usr/bin/odoo -c "$ODOO_CONF" -d "$DB_NAME" -u base --stop-after-init

echo "[6/6] Verifying module records in ir.module.module ..."
sudo -u odoo /usr/bin/odoo shell -c "$ODOO_CONF" -d "$DB_NAME" <<'PY'
mods = env['ir.module.module'].search([('name', 'in', ['mumtaz_base', 'mumtaz_core', 'mumtaz_ai'])])
print("Found modules:", mods.mapped(lambda m: (m.name, m.state)))
PY

echo "DONE: In Odoo UI -> Apps, clear filters, search Mumtaz."
