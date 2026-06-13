#!/bin/bash
# Deploy static websites only — no Odoo restart, fast (<10 s).
# Usage: bash deploy-website.sh [branch]
#   branch — git branch to pull from (default: main)
#
# What it deploys:
#   apps/website/       → /var/www/mumtaz.digital/
#   apps/portal/        → /var/www/app.mumtaz.digital/
#   apps/marketplace/   → /var/www/marketplace.mumtaz.digital/
#   apps/zaki/static/   → /var/www/zaki.mumtaz.digital/
set -euo pipefail

BRANCH="${1:-main}"
REPO="/opt/custom_addons/Mumtaz"

log()  { echo "==> $*"; }
ok()   { echo "    ✓ $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

[ -d "$REPO" ]       || die "Repo not found at $REPO. Clone it first."
[ "$(id -u)" -eq 0 ] || die "Run as root or with sudo."
command -v rsync &>/dev/null || apt-get install -y rsync -qq

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Mumtaz — Static Website Deploy          ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Pull latest code ───────────────────────────────────
log "Pulling branch '$BRANCH'..."
cd "$REPO"
git fetch origin "$BRANCH" \
  || die "git fetch failed. Check network and branch name."
git checkout "origin/$BRANCH" -- \
  apps/website/ \
  apps/portal/ \
  apps/marketplace/ \
  apps/zaki/ \
  || die "git checkout failed — branch '$BRANCH' may not have these paths."
ok "Code pulled from '$BRANCH'"

# ── 2. Sync static sites ──────────────────────────────────
log "Syncing static files..."

sync_site() {
  local src="$1" dest="$2" label="$3"
  if [ -d "$src" ]; then
    mkdir -p "$dest"
    rsync -a --delete "$src" "$dest/"
    ok "$label → $dest"
  else
    echo "    ↷ $src not found — skipping $label"
  fi
}

sync_site "$REPO/apps/website/"     /var/www/mumtaz.digital        "mumtaz.digital"
sync_site "$REPO/apps/portal/"      /var/www/app.mumtaz.digital    "app.mumtaz.digital"
sync_site "$REPO/apps/marketplace/" /var/www/marketplace.mumtaz.digital "marketplace.mumtaz.digital"
sync_site "$REPO/apps/zaki/static/" /var/www/zaki.mumtaz.digital   "zaki.mumtaz.digital"

# Also serve the marketplace as a path under the apex domain so
# https://mumtaz.digital/marketplace/ works without separate DNS/SSL.
# (Runs after the website sync above so it isn't wiped by --delete.)
sync_site "$REPO/apps/marketplace/" /var/www/mumtaz.digital/marketplace "mumtaz.digital/marketplace"

# ── 3. Reload nginx ───────────────────────────────────────
log "Reloading nginx..."
nginx -t 2>&1 | tail -2
systemctl reload nginx
ok "Nginx reloaded"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Deploy complete!                        ║"
echo "║                                          ║"
echo "║  https://mumtaz.digital                  ║"
echo "║  https://app.mumtaz.digital              ║"
echo "║  https://marketplace.mumtaz.digital      ║"
echo "║  https://zaki.mumtaz.digital             ║"
echo "╚══════════════════════════════════════════╝"
echo ""
