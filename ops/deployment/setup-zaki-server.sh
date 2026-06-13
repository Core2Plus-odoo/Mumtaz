#!/bin/bash
# ZAKI Server setup — run once on VPS after cloning the repo.
# Usage: bash setup-zaki-server.sh [branch]
#   branch — git branch to deploy from (default: main)
#
# Example:
#   bash setup-zaki-server.sh
#   bash setup-zaki-server.sh develop
set -euo pipefail

BRANCH="${1:-main}"
REPO="/opt/custom_addons/Mumtaz"
DEST="/opt/zaki-server"
SERVICE="zaki-server"

log()  { echo "==> $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

# ── Validate environment ──────────────────────────────────────────────
[ -d "$REPO" ] || die "Repo not found at $REPO. Clone it first."
[ "$(id -u)" -eq 0 ] || die "Run as root or with sudo."

# ── Pull latest code ──────────────────────────────────────────────────
log "Fetching branch '$BRANCH'..."
cd "$REPO"
git fetch origin "$BRANCH" || die "git fetch failed for branch '$BRANCH'. Check network and branch name."
git checkout "origin/$BRANCH" -- apps/zaki-server/ ops/deployment/zaki-server.service \
  || die "git checkout failed — branch '$BRANCH' may not have these paths."

# ── Backup existing installation ──────────────────────────────────────
if [ -d "$DEST" ]; then
  BACKUP="${DEST}.backup.$(date +%Y%m%d%H%M%S)"
  log "Backing up $DEST → $BACKUP"
  cp -a "$DEST" "$BACKUP"
fi

# ── Deploy server files ───────────────────────────────────────────────
log "Deploying server files to $DEST..."
mkdir -p "$DEST"
cp -r apps/zaki-server/. "$DEST/"

# ── Ensure Python venv ────────────────────────────────────────────────
log "Ensuring Python venv support..."
apt-get install -y python3-venv python3-pip 2>/dev/null || true

# Recreate the venv if it is missing OR broken (e.g. no interpreter/pip).
if [ ! -x "$DEST/venv/bin/python" ]; then
  log "Creating Python venv (missing or broken)..."
  rm -rf "$DEST/venv"
  python3 -m venv "$DEST/venv"
fi

log "Installing Python dependencies..."
# Use `python -m pip` (works even when the pip console-script is missing) and
# bootstrap pip via ensurepip in case the venv was created without it.
"$DEST/venv/bin/python" -m ensurepip --upgrade 2>/dev/null || true
"$DEST/venv/bin/python" -m pip install -q --upgrade pip \
  || die "pip bootstrap failed — venv may be broken at $DEST/venv"
"$DEST/venv/bin/python" -m pip install -q -r "$DEST/requirements.txt" \
  || die "pip install failed — check requirements.txt"

# ── Create .env (only if it doesn't exist) ───────────────────────────
if [ ! -f "$DEST/.env" ]; then
  log "Creating .env template (EDIT IT BEFORE STARTING THE SERVICE)..."
  JWT_SECRET="$(openssl rand -hex 64)"
  cat > "$DEST/.env" <<EOF
ENVIRONMENT=production
JWT_SECRET=${JWT_SECRET}

# REQUIRED: Set before starting the service
ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE
ODOO_URL=http://127.0.0.1:8069
ODOO_DB=mumtaz
ODOO_ADMIN_USER=admin
ODOO_ADMIN_PASS=YOUR-STRONG-ODOO-PASSWORD
CORS_ORIGINS=https://app.mumtaz.digital,https://zaki.mumtaz.digital

# Database — use PostgreSQL in production
DATABASE_URL=postgresql://mumtaz:CHANGE_ME@127.0.0.1:5432/mumtaz_platform
EOF
  chmod 600 "$DEST/.env"
  echo ""
  echo "⚠️  IMPORTANT: Edit $DEST/.env and set ALL required values:"
  echo "   ANTHROPIC_API_KEY  — your Anthropic key"
  echo "   ODOO_ADMIN_PASS    — your Odoo admin password"
  echo "   DATABASE_URL       — PostgreSQL connection string"
  echo "   nano $DEST/.env"
  echo ""
else
  log ".env already exists — skipping creation."
  # Warn if placeholder values remain
  if grep -q "CHANGE_ME\|YOUR-KEY-HERE\|YOUR-STRONG" "$DEST/.env"; then
    echo ""
    echo "⚠️  WARNING: $DEST/.env still contains placeholder values. Update before proceeding."
    echo "   nano $DEST/.env"
    echo ""
  fi
fi

# ── Install systemd service ───────────────────────────────────────────
log "Installing systemd service..."
cp ops/deployment/zaki-server.service /etc/systemd/system/${SERVICE}.service \
  || die "Failed to copy service file"
systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE" || die "Service failed to start — check: journalctl -u $SERVICE -n 50"

echo ""
echo "✅ ZAKI Server deployed from branch '$BRANCH' → $DEST"
echo ""
echo "Post-deploy checklist:"
echo "  1. Edit .env:     nano $DEST/.env && systemctl restart $SERVICE"
echo "  2. Seed admin:    $DEST/venv/bin/python $DEST/create_user.py admin@mumtaz.digital PASSWORD"
echo "  3. Health check:  curl http://127.0.0.1:8002/health"
echo "  4. View logs:     journalctl -u $SERVICE -f"
echo ""
