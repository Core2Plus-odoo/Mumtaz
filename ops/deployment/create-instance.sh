#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# create-instance.sh — provision a new Odoo instance (database) for a tenant.
#
# Run this ON THE SERVER, from the repo root (where docker-compose.production.yml
# and .env.production live). It creates the database, installs the base + Mumtaz
# modules, and sets the admin login — using the credentials already in your env
# file. Nothing secret is stored in this script.
#
# Usage:
#   ./ops/deployment/create-instance.sh [DB_NAME] [ADMIN_EMAIL]
#
# Examples:
#   ./ops/deployment/create-instance.sh c2p_consultants umer@mumtaz.digital
#   DB_NAME=c2p_consultants ADMIN_EMAIL=umer@mumtaz.digital ./ops/deployment/create-instance.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── config ──────────────────────────────────────────────────────────────────
DB_NAME="${1:-${DB_NAME:-c2p_consultants}}"
ADMIN_EMAIL="${2:-${ADMIN_EMAIL:-admin@example.com}}"
COMPANY_NAME="${COMPANY_NAME:-C2P Consultants FZC LLC}"
ENV_FILE="${ENV_FILE:-.env.production}"
COMPOSE="${COMPOSE:-docker compose -f docker-compose.production.yml}"
ODOO_SVC="${ODOO_SVC:-odoo}"
DB_SVC="${DB_SVC:-db}"
# Modules to install on the fresh DB (comma-separated). Override with MODULES=...
MODULES="${MODULES:-base}"

# ── load credentials from the env file (never hard-coded here) ──────────────
if [[ ! -f "$ENV_FILE" ]]; then
  echo "✗ Env file '$ENV_FILE' not found. Run this from the repo root on the server." >&2
  exit 1
fi
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

: "${POSTGRES_USER:?POSTGRES_USER must be set in $ENV_FILE}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in $ENV_FILE}"
ADMIN_PW="${ADMIN_PASSWORD:-${ODOO_ADMIN_PASS:-}}"
: "${ADMIN_PW:?Set ADMIN_PASSWORD (or ODOO_ADMIN_PASS) in $ENV_FILE — used as the admin login password}"

echo "==> Creating Odoo instance:"
echo "      database : $DB_NAME"
echo "      company  : $COMPANY_NAME"
echo "      admin    : $ADMIN_EMAIL"
echo "      modules  : $MODULES"

# ── guard: refuse if the database already exists ────────────────────────────
if $COMPOSE exec -T "$DB_SVC" psql -U "$POSTGRES_USER" -tAc \
     "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" 2>/dev/null | grep -q 1; then
  echo "✗ Database '$DB_NAME' already exists — aborting so nothing is overwritten." >&2
  echo "  To recreate it, drop it first (irreversible):" >&2
  echo "    $COMPOSE exec $DB_SVC dropdb -U $POSTGRES_USER $DB_NAME" >&2
  exit 2
fi

# ── create + initialise the database via Odoo ───────────────────────────────
# Odoo creates the DB, installs the modules, and provisions the admin user.
echo "==> Initialising database (this can take a minute)…"
$COMPOSE exec -T "$ODOO_SVC" odoo \
  -d "$DB_NAME" \
  -i "$MODULES" \
  --db_host="${DB_SVC}" \
  --db_user="$POSTGRES_USER" \
  --db_password="$POSTGRES_PASSWORD" \
  --load-language=en_US \
  --without-demo=all \
  --stop-after-init

# ── set the company name + admin login/password ─────────────────────────────
echo "==> Setting company name and admin credentials…"
$COMPOSE exec -T "$ODOO_SVC" python3 - "$DB_NAME" "$ADMIN_EMAIL" "$ADMIN_PW" "$COMPANY_NAME" <<'PY'
import sys, odoo
db, admin_email, admin_pw, company = sys.argv[1:5]
odoo.tools.config.parse_config(['-d', db])
registry = odoo.registry(db)
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    env['res.company'].browse(1).write({'name': company})
    admin = env.ref('base.user_admin')
    admin.write({'login': admin_email, 'email': admin_email, 'password': admin_pw})
    cr.commit()
    print(f"   ✓ company='{company}', admin login='{admin_email}'")
PY

echo ""
echo "✓ Instance '$DB_NAME' created."
echo "  Log in at your Odoo URL with:"
echo "      email    : $ADMIN_EMAIL"
echo "      password : (the ADMIN_PASSWORD from $ENV_FILE)"
echo ""
echo "  Tip: to also install the Mumtaz modules, re-run with:"
echo "      MODULES=base,mumtaz_api ./ops/deployment/create-instance.sh $DB_NAME $ADMIN_EMAIL"
