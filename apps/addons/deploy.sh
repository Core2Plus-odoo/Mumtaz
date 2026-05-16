#!/usr/bin/env bash
# Deploy Mumtaz custom Odoo addons to /opt/custom_addons
# and optionally trigger module install/upgrade in Odoo.
#
# Usage on VPS:
#   cd /opt/Mumtaz
#   git pull origin claude/odoo-architecture-review-ujm0W
#   sudo bash apps/addons/deploy.sh
#
# What this does:
#   1. Rsyncs addons/ → /opt/custom_addons/
#   2. Sets ownership to the odoo service user
#   3. Optionally runs odoo -u <modules> --stop-after-init
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC_DIR="${REPO_ROOT}/addons"
DEST_DIR="/opt/custom_addons"
ODOO_BIN="${ODOO_BIN:-$(command -v odoo || command -v odoo-bin || echo '/usr/bin/odoo')}"
ODOO_CONF="${ODOO_CONF:-/etc/odoo/odoo.conf}"
ODOO_USER="${ODOO_USER:-odoo}"

# Modules to install/upgrade (comma-separated, or "all" to skip prompt)
MODULES="${MODULES:-mumtaz_theme,mumtaz_organization,mumtaz_base,mumtaz_core,mumtaz_marketplace,mumtaz_vendor_portal,mumtaz_customer_portal,mumtaz_einvoicing,mumtaz_api,mumtaz_api_gateway}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Mumtaz Addons Deploy"
echo " src:  $SRC_DIR"
echo " dest: $DEST_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Sync addons ────────────────────────────────────────────────────
echo "→ Syncing addons…"
sudo mkdir -p "$DEST_DIR"
sudo rsync -av --delete \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    "$SRC_DIR/" "$DEST_DIR/"
sudo chown -R "${ODOO_USER}:${ODOO_USER}" "$DEST_DIR"
echo "✅ Addons synced to $DEST_DIR"

# ── 2. Patch odoo.conf — proxy_mode + dbfilter + addons_path ─────────
echo "→ Checking odoo.conf settings…"
if [[ -f "$ODOO_CONF" ]]; then
    # proxy_mode — required when Odoo sits behind nginx
    if grep -q 'proxy_mode' "$ODOO_CONF"; then
        sudo sed -i 's/proxy_mode.*/proxy_mode = True/' "$ODOO_CONF"
    else
        echo "proxy_mode = True" | sudo tee -a "$ODOO_CONF" > /dev/null
    fi
    echo "  ✅ proxy_mode = True"

    # dbfilter — allow Mumtaz_ERP (admin) and all mt_* tenant databases
    # Use # as delimiter so the | in the filter value is not misread by sed
    DBFILTER='dbfilter = ^(Mumtaz_ERP|mt_)'
    if grep -q 'dbfilter' "$ODOO_CONF"; then
        sudo sed -i "s#dbfilter.*#${DBFILTER}#" "$ODOO_CONF"
    else
        echo "$DBFILTER" | sudo tee -a "$ODOO_CONF" > /dev/null
    fi
    echo "  ✅ ${DBFILTER}"
fi

echo "→ Checking odoo.conf addons_path…"
if [[ -f "$ODOO_CONF" ]]; then
    current_path=$(grep -E '^addons_path\s*=' "$ODOO_CONF" | sed 's/.*=\s*//' | tr -d ' ')
    if echo "$current_path" | grep -qF "$DEST_DIR"; then
        echo "  ✅ $DEST_DIR already in addons_path"
    else
        if [[ -n "$current_path" ]]; then
            new_path="${current_path},${DEST_DIR}"
            sudo sed -i "s|^addons_path\s*=.*|addons_path = ${new_path}|" "$ODOO_CONF"
        else
            echo "addons_path = ${DEST_DIR}" | sudo tee -a "$ODOO_CONF" > /dev/null
            new_path="$DEST_DIR"
        fi
        echo "  ✅ addons_path updated → $new_path"
    fi
else
    echo "  ⚠  $ODOO_CONF not found — skipping addons_path patch"
    echo "     Add this line manually: addons_path = $DEST_DIR"
fi

# ── 3. Restart Odoo service ───────────────────────────────────────────
echo "→ Restarting Odoo service…"
if sudo systemctl is-active --quiet odoo; then
    sudo systemctl restart odoo
    echo "✅ Odoo restarted"
else
    echo "  ⚠  Odoo service not running — skipping restart"
fi

# ── 3. Optional module install/upgrade ───────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Module Install / Upgrade"
echo " Modules: $MODULES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ ! -x "$ODOO_BIN" ]]; then
    echo "  ⚠  $ODOO_BIN not found — skipping module upgrade"
    echo "  Run manually: odoo -c $ODOO_CONF -u $MODULES --stop-after-init"
else
    read -rp "Run 'odoo -u ${MODULES}' now? [y/N] " yn
    if [[ "$yn" =~ ^[Yy]$ ]]; then
        echo "→ Upgrading modules (this may take a few minutes)…"
        sudo -u "$ODOO_USER" "$ODOO_BIN" \
            -c "$ODOO_CONF" \
            -u "$MODULES" \
            --stop-after-init
        echo "✅ Module upgrade complete"
    else
        echo "  Skipped — run manually when ready:"
        echo "    sudo -u $ODOO_USER $ODOO_BIN -c $ODOO_CONF -u $MODULES --stop-after-init"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✅ Addons deployed!"
echo " Custom addons path: $DEST_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
