#!/bin/bash
# ZAKI Server setup — run once on VPS
# Usage: bash setup-zaki-server.sh
set -e

REPO="/opt/custom_addons/Mumtaz"
BRANCH="claude/odoo-architecture-review-ujm0W"
DEST="/opt/zaki-server"

echo "==> Pulling latest code..."
cd $REPO
git fetch origin $BRANCH
git checkout origin/$BRANCH -- apps/zaki-server/ ops/deployment/zaki-server.service

echo "==> Deploying server files..."
mkdir -p $DEST
cp apps/zaki-server/main.py $DEST/
cp apps/zaki-server/requirements.txt $DEST/
cp apps/zaki-server/create_user.py $DEST/

echo "==> Ensuring Python venv support..."
apt-get install -y python3-venv python3-pip 2>/dev/null || true

echo "==> Creating Python venv..."
if [ ! -d $DEST/venv ]; then
  python3 -m venv $DEST/venv
fi
$DEST/venv/bin/pip install -q --upgrade pip
$DEST/venv/bin/pip install -q -r $DEST/requirements.txt

echo "==> Creating .env (if not exists)..."
if [ ! -f $DEST/.env ]; then
  cat > $DEST/.env <<EOF
JWT_SECRET=$(openssl rand -hex 32)
ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE
DB_PATH=/opt/zaki-server/users.db
# Odoo connection (single source of truth for auth)
ODOO_URL=http://127.0.0.1:8069
ODOO_DB=mumtaz
ODOO_ADMIN_USER=admin
ODOO_ADMIN_PASS=YOUR-ODOO-ADMIN-PASSWORD
EOF
  echo ""
  echo "⚠️  IMPORTANT: Edit $DEST/.env and set:"
  echo "   ANTHROPIC_API_KEY  — your Anthropic key"
  echo "   ODOO_ADMIN_PASS    — your Odoo admin password"
  echo "   nano $DEST/.env"
  echo ""
else
  # Add Odoo vars if missing from existing .env
  grep -q "ODOO_URL" $DEST/.env || cat >> $DEST/.env <<EOF
ODOO_URL=http://127.0.0.1:8069
ODOO_DB=mumtaz
ODOO_ADMIN_USER=admin
ODOO_ADMIN_PASS=YOUR-ODOO-ADMIN-PASSWORD
EOF
  echo "⚠️  Odoo vars appended to $DEST/.env — update ODOO_ADMIN_PASS"
fi

echo "==> Installing systemd service..."
cp ops/deployment/zaki-server.service /etc/systemd/system/zaki-server.service
systemctl daemon-reload
systemctl enable zaki-server
systemctl restart zaki-server

echo ""
echo "✅ ZAKI Server is running on 127.0.0.1:8000"
echo ""
echo "Next steps:"
echo "  1. Set Anthropic key:  nano $DEST/.env && systemctl restart zaki-server"
echo "  2. Create your user:   $DEST/venv/bin/python $DEST/create_user.py umer@mumtaz.digital PASSWORD"
echo "  3. Check health:       curl http://127.0.0.1:8000/health"
echo ""
