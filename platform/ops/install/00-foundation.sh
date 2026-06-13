#!/usr/bin/env bash
# =====================================================================
#  Mumtaz Platform — Phase 0: Foundation (safe, idempotent, additive)
#  Run as root on the VPS:  bash platform/ops/install/00-foundation.sh
#
#  Does NOT touch the existing live services or nginx — it only:
#    - installs base packages
#    - creates /opt/mumtaz/* directories
#    - ensures /opt/mumtaz/.env (generates JWT_SECRET if blank)
#    - creates the mumtaz_platform PostgreSQL DB + schema + module catalogue
#    - bootstraps the super-admin + C2P tenant (password from .env, bcrypt-hashed)
#  All secrets are read from .env. Nothing is hardcoded.
# =====================================================================
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"      # repo root
PDIR="$REPO/platform"
ENV_FILE="/opt/mumtaz/.env"

log(){ echo "==> $*"; }
die(){ echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "Run as root."

# --- 1. Packages -----------------------------------------------------
log "Installing base packages..."
apt-get update -qq
apt-get install -y -qq postgresql postgresql-contrib python3 python3-pip python3-venv \
    git curl redis-server >/dev/null
python3 -m pip install --quiet --break-system-packages bcrypt 2>/dev/null || pip3 install --quiet bcrypt || true
systemctl enable --now postgresql redis-server >/dev/null 2>&1 || true

# --- 2. Directories --------------------------------------------------
log "Creating /opt/mumtaz tree..."
mkdir -p /opt/mumtaz/{marketing,logs,backups,uploads,scripts}
mkdir -p /opt/mumtaz/platform/{backend,frontend}
mkdir -p /opt/mumtaz/zaki/{backend,frontend}
mkdir -p /opt/mumtaz/odoo/{server,custom_addons}

# --- 3. .env ---------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
  log "Creating $ENV_FILE from template (EDIT IT before going live)..."
  cp "$PDIR/ops/.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi
# Auto-generate JWT_SECRET if blank
if grep -qE '^JWT_SECRET=\s*$' "$ENV_FILE"; then
  SEC="$(openssl rand -hex 48)"
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${SEC}|" "$ENV_FILE"
  log "Generated JWT_SECRET."
fi
set -a; . "$ENV_FILE"; set +a
[ "${DB_PASS:-CHANGE_ME_STRONG}" != "CHANGE_ME_STRONG" ] || die "Set DB_PASS in $ENV_FILE first."

# --- 4. PostgreSQL role + database ----------------------------------
log "Ensuring PostgreSQL role + database..."
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}' SUPERUSER CREATEDB;
  ELSE
    ALTER ROLE ${DB_USER} PASSWORD '${DB_PASS}';
  END IF;
END \$\$;
SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname='${DB_NAME}')\gexec
SQL

# --- 5. Schema + catalogue ------------------------------------------
log "Applying schema + module catalogue..."
export PGPASSWORD="$DB_PASS"
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "$PDIR/db/schema.sql"
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "$PDIR/db/seed_catalogue.sql"

# --- 6. Bootstrap super-admin + C2P tenant (password from .env) ------
log "Bootstrapping super admin (password from .env, bcrypt-hashed)..."
HASH="$(python3 -c "import bcrypt,os;print(bcrypt.hashpw(os.environ['SUPER_ADMIN_PASSWORD'].encode(),bcrypt.gensalt(12)).decode())")"
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<SQL
INSERT INTO tenants (slug,name,type,status,plan,country,currency,industry,odoo_db,activated_at)
VALUES ('c2p','C2P Consultants FZC LLC','business','active','enterprise','UAE','AED','Technology','corp_c2p',NOW())
ON CONFLICT (slug) DO NOTHING;

INSERT INTO platform_users (tenant_id,email,name,first_name,password_hash,role,is_super_admin)
VALUES ((SELECT id FROM tenants WHERE slug='c2p'),
        '${SUPER_ADMIN_EMAIL}','Muhammad Umar Mubashir Ali','Muhammad','${HASH}','super_admin',TRUE)
ON CONFLICT (email) DO UPDATE SET is_super_admin=TRUE, role='super_admin';

-- C2P gets all modules
INSERT INTO tenant_modules (tenant_id,module_id)
SELECT t.id,m.id FROM tenants t,module_catalogue m WHERE t.slug='c2p'
ON CONFLICT DO NOTHING;
SQL
unset PGPASSWORD

echo ""
log "Phase 0 complete. Verify:"
echo "    PGPASSWORD=\$DB_PASS psql -h localhost -U $DB_USER -d $DB_NAME -c \"SELECT slug,type,status FROM tenants;\""
echo "    → expect: c2p | business | active"
