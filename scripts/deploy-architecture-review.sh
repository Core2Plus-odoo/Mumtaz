#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Mumtaz — deploy the architecture-review branch
#
# Deploys all pieces from claude/odoo-architecture-review-ujm0W:
#   1. Theme teal migration (mumtaz_theme)
#   2. Wildcard nginx config           (only if --nginx flag passed)
#   3. mumtaz_org_config module
#   4. ZATCA gateway fix + QR + Phase 2 onboarding
#   5. FBR URL fix + IRN QR
#   6. Marketplace OWL widget
#   7. Vendor portal — PO detail + acknowledge + invoice upload
#
# Run as root on the VPS:  bash deploy-architecture-review.sh [--nginx]
#
# Environment variables (set in /opt/mumtaz/.deploy.env or override inline):
#   REPO_DIR        path to the git checkout            (default /opt/mumtaz)
#   ADDONS_DIR      where Odoo loads custom addons      (default /opt/custom_addons)
#   PORTAL_DIR      static portal HTML root             (default /var/www/app.mumtaz.digital)
#   ZAKI_DIR        FastAPI server directory            (default /opt/zaki-server)
#   ODOO_BIN        path to odoo-bin                    (default /opt/odoo/odoo-bin)
#   ODOO_CONF       odoo configuration                  (default /etc/odoo/odoo.conf)
#   ODOO_DB         main Odoo database                  (default mumtaz_main)
#   ODOO_USER       OS user that runs Odoo              (default odoo)
#   BRANCH          git branch to deploy                (default claude/odoo-architecture-review-ujm0W)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/mumtaz}"
ADDONS_DIR="${ADDONS_DIR:-/opt/custom_addons}"
PORTAL_DIR="${PORTAL_DIR:-/var/www/app.mumtaz.digital}"
ZAKI_DIR="${ZAKI_DIR:-/opt/zaki-server}"
ODOO_BIN="${ODOO_BIN:-/opt/odoo/odoo-bin}"
ODOO_CONF="${ODOO_CONF:-/etc/odoo/odoo.conf}"
ODOO_DB="${ODOO_DB:-mumtaz_main}"
ODOO_USER="${ODOO_USER:-odoo}"
BRANCH="${BRANCH:-claude/odoo-architecture-review-ujm0W}"

DEPLOY_NGINX=0
if [[ "${1:-}" == "--nginx" ]]; then
    DEPLOY_NGINX=1
fi

# Source extra env if it exists
if [[ -f "${REPO_DIR}/.deploy.env" ]]; then
    # shellcheck disable=SC1091
    source "${REPO_DIR}/.deploy.env"
fi

# ── Logging helpers ──────────────────────────────────────────────────────────
log() { printf '\033[1;36m[deploy]\033[0m %s\n' "$*"; }
ok()  { printf '\033[1;32m[ ok ]\033[0m %s\n'   "$*"; }
warn(){ printf '\033[1;33m[warn]\033[0m %s\n'   "$*"; }
die() { printf '\033[1;31m[fail]\033[0m %s\n' "$*" >&2; exit 1; }

# ── Pre-flight ───────────────────────────────────────────────────────────────
[[ "$EUID" -eq 0 ]] || die "Must run as root."
[[ -d "$REPO_DIR/.git" ]] || die "REPO_DIR=$REPO_DIR is not a git checkout."
command -v rsync >/dev/null   || die "rsync is required."
command -v systemctl >/dev/null || die "systemctl is required."

log "Repo:    $REPO_DIR"
log "Branch:  $BRANCH"
log "Addons:  $ADDONS_DIR"
log "Portal:  $PORTAL_DIR"
log "Odoo DB: $ODOO_DB"
[[ $DEPLOY_NGINX -eq 1 ]] && log "Will install wildcard nginx config." || log "Skipping nginx install (use --nginx to enable)."

# ── 1. Pull latest code ──────────────────────────────────────────────────────
log "Pulling latest from $BRANCH …"
cd "$REPO_DIR"
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"
ok "Code at $(git rev-parse --short HEAD)"

# ── 2. Sync custom addons (modules touched by the architecture-review pieces)
log "Syncing custom addons …"
mkdir -p "$ADDONS_DIR"
TARGETS=(
    mumtaz_theme
    mumtaz_org_config
    mumtaz_einvoicing
    mumtaz_marketplace
    mumtaz_vendor_portal
    mumtaz_portal_routing
)
for mod in "${TARGETS[@]}"; do
    if [[ -d "$REPO_DIR/addons/$mod" ]]; then
        rsync -a --delete \
              --exclude='__pycache__' \
              --exclude='*.pyc' \
              "$REPO_DIR/addons/$mod/" "$ADDONS_DIR/$mod/"
        ok "synced $mod"
    else
        warn "missing $REPO_DIR/addons/$mod (skipping)"
    fi
done
chown -R "$ODOO_USER":"$ODOO_USER" "$ADDONS_DIR" 2>/dev/null || warn "Could not chown $ADDONS_DIR"

# ── 3. Update / install Odoo modules ─────────────────────────────────────────
log "Restarting Odoo to load new addons …"
systemctl stop odoo 2>/dev/null || warn "odoo service not running"

log "Updating Odoo modules in DB '$ODOO_DB' …"
sudo -u "$ODOO_USER" \
    "$ODOO_BIN" -c "$ODOO_CONF" \
    -d "$ODOO_DB" \
    -u mumtaz_theme,mumtaz_einvoicing,mumtaz_marketplace,mumtaz_vendor_portal,mumtaz_portal_routing \
    -i mumtaz_org_config \
    --stop-after-init \
    --no-http \
    || die "Odoo module update failed (check /var/log/odoo/odoo.log)."

ok "Odoo modules updated."

systemctl start odoo
systemctl is-active --quiet odoo && ok "odoo running" || die "Odoo failed to start."

# ── 4. Sync portal static HTML (apps/portal) ─────────────────────────────────
if [[ -d "$REPO_DIR/apps/portal" && -d "$PORTAL_DIR" ]]; then
    log "Syncing portal HTML to $PORTAL_DIR …"
    rsync -a --delete \
          --exclude='nginx.conf' \
          --exclude='*.sh' \
          --exclude='__pycache__' \
          "$REPO_DIR/apps/portal/" "$PORTAL_DIR/"
    ok "portal synced"
fi

# ── 5. Sync zaki-server backend files ────────────────────────────────────────
if [[ -d "$REPO_DIR/apps/zaki-server" && -d "$ZAKI_DIR" ]]; then
    log "Syncing zaki-server …"
    for f in main.py mail.py billing.py zatca.py settings_store.py requirements.txt; do
        if [[ -f "$REPO_DIR/apps/zaki-server/$f" ]]; then
            cp "$REPO_DIR/apps/zaki-server/$f" "$ZAKI_DIR/"
        fi
    done
    systemctl restart zaki-server 2>/dev/null && ok "zaki-server restarted" || warn "zaki-server service not found"
fi

# ── 6. Optional: install wildcard nginx vhost ────────────────────────────────
if [[ $DEPLOY_NGINX -eq 1 ]]; then
    log "Installing wildcard nginx vhost …"
    cp "$REPO_DIR/apps/platform/nginx-wildcard.conf" /etc/nginx/sites-available/mumtaz-wildcard
    ln -sf /etc/nginx/sites-available/mumtaz-wildcard /etc/nginx/sites-enabled/
    if nginx -t >/dev/null 2>&1; then
        systemctl reload nginx
        ok "nginx reloaded"
    else
        warn "nginx config test failed — vhost NOT enabled. Run 'nginx -t' to inspect."
        rm -f /etc/nginx/sites-enabled/mumtaz-wildcard
    fi
fi

# ── 7. Smoke checks ──────────────────────────────────────────────────────────
log "Running smoke checks …"
SMOKE_OK=1

curl -sf -o /dev/null "http://localhost:8069/web/database/selector" \
    && ok "Odoo HTTP responding" \
    || { warn "Odoo HTTP not responding"; SMOKE_OK=0; }

if systemctl is-enabled --quiet zaki-server 2>/dev/null; then
    curl -sf -o /dev/null "http://localhost:8001/api/v1/health" \
        && ok "zaki-server healthy" \
        || warn "zaki-server health check failed"
fi

if [[ $SMOKE_OK -eq 1 ]]; then
    ok "Deploy complete. Visit https://app.mumtaz.digital and the Odoo backend to verify."
else
    warn "Deploy completed with warnings — please verify services manually."
fi
