#!/usr/bin/env bash
set -euo pipefail

TEMPLATE_PATH="/etc/odoo/odoo.conf.tmpl"
CONFIG_PATH="/etc/odoo/odoo.conf"

render_odoo_config() {
  if [[ ! -f "$TEMPLATE_PATH" ]]; then
    echo "[entrypoint] template not found: $TEMPLATE_PATH" >&2
    return 1
  fi

  python3 - <<'PY'
import os
from pathlib import Path

template_path = Path('/etc/odoo/odoo.conf.tmpl')
config_path = Path('/etc/odoo/odoo.conf')
content = template_path.read_text()
for key, value in os.environ.items():
    content = content.replace('${' + key + '}', value)
config_path.write_text(content)
PY

  echo "[entrypoint] rendered Odoo config at $CONFIG_PATH"
}

render_odoo_config
exec odoo -c "$CONFIG_PATH"
