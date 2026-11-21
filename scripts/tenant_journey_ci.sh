#!/usr/bin/env bash
#
# Tenant journey check — the first platform milestone, proven for real:
#
#   Register organization -> Choose Mumtaz ERP -> Assign entitlement
#     -> Provision isolated staging tenant -> Open ERP workspace
#
# Nothing here is mocked. It builds a throwaway control database, runs the
# journey through the same methods the operator's buttons and the scheduled
# worker call, lets the provisioner create a real tenant database, starts an
# Odoo HTTP server on that database and signs in through the one-time link.
# It also proves the opposite: on a server that may not create databases, the
# same journey ends with no database and no "active" tenant.
#
# Same guard rails as scripts/platform_ci.sh: databases whose names it builds
# itself, a refusal to run from `main`, no deploy script, no service restart.
# It drops only the databases it created.
#
# Usage:
#   ODOO_PATH=/path/to/odoo19 scripts/tenant_journey_ci.sh
#   KEEP_DB=1 ... scripts/tenant_journey_ci.sh      # keep databases for inspection
#
# Configuration (environment): ODOO_PATH, PYTHON, PGHOST PGPORT PGUSER
# PGPASSWORD, LOG_DIR, JOURNEY_HTTP_PORT, JEWEL_CI_ALLOW_MAIN.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
ODOO_PATH="${ODOO_PATH:-}"
RUN_ID="${RUN_ID:-$$}"
CONTROL_DB="cpj_ci_${RUN_ID}"
TENANT_DB="stg_journey_ci_${RUN_ID}"          # derived from the organization name below
DRY_TENANT_DB="stg_journey_dry_${RUN_ID}"
ORG_NAME="Journey CI ${RUN_ID}"
DRY_ORG_NAME="Journey Dry ${RUN_ID}"
LOG_DIR="${LOG_DIR:-${TMPDIR:-/tmp}/tenant-journey}"
PORT="${JOURNEY_HTTP_PORT:-8097}"
export PGHOST="${PGHOST:-localhost}" PGPORT="${PGPORT:-5432}" PGUSER="${PGUSER:-odoo}"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
green(){ printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '\033[36m==> %s\033[0m\n' "$*"; }

# -- guard rails -------------------------------------------------------------
BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
if [ "$BRANCH" = "main" ] && [ "${JEWEL_CI_ALLOW_MAIN:-0}" != "1" ]; then
  red "Refusing to run on 'main': the production VPS pulls that branch."
  red "Check out a feature branch, or set JEWEL_CI_ALLOW_MAIN=1 on a disposable CI runner."
  exit 2
fi
case "$RUN_ID" in *[!0-9a-z]*|"") red "RUN_ID must be lowercase letters and digits."; exit 2 ;; esac
if [ -z "$ODOO_PATH" ] || [ ! -x "$ODOO_PATH/odoo-bin" ]; then
  red "Set ODOO_PATH to an Odoo 19 Community checkout containing odoo-bin."
  exit 2
fi
for db in "$CONTROL_DB" "$TENANT_DB" "$DRY_TENANT_DB"; do
  if psql -d postgres -tAc "select 1 from pg_database where datname='$db'" | grep -q 1; then
    red "Database '$db' already exists. This script only works with databases it creates."; exit 2
  fi
done

mkdir -p "$LOG_DIR"
REAL_JSON="$(mktemp "${LOG_DIR:?}/journey-real.XXXXXX")"   # holds a sign-in link for the throwaway tenant
DRY_JSON="$(mktemp "${LOG_DIR:?}/journey-dry.XXXXXX")"

SERVER_PID=""
cleanup() {
  if [ -n "$SERVER_PID" ]; then kill "$SERVER_PID" >/dev/null 2>&1 || true; wait "$SERVER_PID" 2>/dev/null || true; fi
  : > "$REAL_JSON"; : > "$DRY_JSON"     # empty rather than delete: no rm on computed paths
  if [ "${KEEP_DB:-0}" = "1" ]; then info "Databases kept: $CONTROL_DB $TENANT_DB"; return; fi
  for db in "$TENANT_DB" "$DRY_TENANT_DB" "$CONTROL_DB"; do
    dropdb --if-exists "$db" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

ADDONS_PATH="$ODOO_PATH/addons,$REPO_ROOT/addons"
# --no-database-list: the way a multi-tenant server should run. Provisioning
# must not depend on the database manager being exposed.
ODOO_BIN=( "$PYTHON" "$ODOO_PATH/odoo-bin" )
ODOO_ARGS=( --addons-path="$ADDONS_PATH"
       --db_host="$PGHOST" --db_port="$PGPORT" --db_user="$PGUSER"
       --data-dir="$LOG_DIR/$CONTROL_DB-filestore"
       --without-demo=True --no-database-list --log-level=info )
if [ -n "${PGPASSWORD:-}" ]; then ODOO_ARGS+=( --db_password="$PGPASSWORD" ); fi

journey() {   # journey <real|dry> <org name> <email> <summary file> <log file>
  JOURNEY_MODE="$1" JOURNEY_ORG="$2" JOURNEY_EMAIL="$3" JOURNEY_OUT="$4" \
    "${ODOO_BIN[@]}" shell "${ODOO_ARGS[@]}" -d "$CONTROL_DB" --no-http < "$REPO_ROOT/scripts/tenant_journey/journey.py" > "$5" 2>&1
}
show() { grep -E '^(  ok  |JOURNEY|WORKSPACE)' "$1" || true; }

# -- 1. control database -----------------------------------------------------
info "Branch: $BRANCH"
info "Creating the control database: $CONTROL_DB"
createdb "$CONTROL_DB"
if ! "${ODOO_BIN[@]}" "${ODOO_ARGS[@]}" -d "$CONTROL_DB" -i mumtaz_tenant_manager,mumtaz_control_plane \
      --no-http --stop-after-init > "$LOG_DIR/$CONTROL_DB-install.log" 2>&1; then
  red "Control-plane install FAILED:"; tail -40 "$LOG_DIR/$CONTROL_DB-install.log"; exit 1
fi
green "Control plane installed (mumtaz_tenant_manager, mumtaz_control_plane)."

# -- 2. the journey on a server that may NOT create databases ----------------
info "Journey with real provisioning switched off (must create nothing)"
if ! MUMTAZ_REAL_PROVISIONING=0 journey dry "$DRY_ORG_NAME" "owner@journey-dry-${RUN_ID}.example" "$DRY_JSON" "$LOG_DIR/$CONTROL_DB-dry.log"; then
  show "$LOG_DIR/$CONTROL_DB-dry.log"; red "Dry journey FAILED. Log: $LOG_DIR/$CONTROL_DB-dry.log"; tail -30 "$LOG_DIR/$CONTROL_DB-dry.log"; exit 1
fi
show "$LOG_DIR/$CONTROL_DB-dry.log"
if psql -d postgres -tAc "select 1 from pg_database where datname='$DRY_TENANT_DB'" | grep -q 1; then
  red "A database was created during the dry journey."; exit 1
fi
green "No database created, no tenant activated."

# -- 3. the journey for real -------------------------------------------------
info "Journey with real provisioning enabled (creates $TENANT_DB; takes a few minutes)"
if ! MUMTAZ_REAL_PROVISIONING=1 journey real "$ORG_NAME" "owner@journey-ci-${RUN_ID}.example" "$REAL_JSON" "$LOG_DIR/$CONTROL_DB-real.log"; then
  show "$LOG_DIR/$CONTROL_DB-real.log"; red "Journey FAILED. Log: $LOG_DIR/$CONTROL_DB-real.log"
  grep -E ' (ERROR|CRITICAL) ' "$LOG_DIR/$CONTROL_DB-real.log" | head -20 || true; exit 1
fi
show "$LOG_DIR/$CONTROL_DB-real.log"

# -- 4. isolation, read straight from PostgreSQL ------------------------------
info "Isolation checks"
q() { psql -d "$1" -tAc "$2" | tr -d '[:space:]'; }
[ "$(q "$TENANT_DB" "select to_regclass('mumtaz_tenant') is null and to_regclass('mumtaz_subscription') is null and to_regclass('mumtaz_plan') is null")" = "t" ] \
  || { red "Control-plane tables found inside the tenant database."; exit 1; }
green "  ok  the tenant database holds no control-plane tables"
[ "$(q "$CONTROL_DB" "select to_regclass('crm_lead') is null and to_regclass('account_move') is null")" = "t" ] \
  || { red "ERP tables found inside the control database."; exit 1; }
green "  ok  the control database holds no ERP tables"
[ "$(q "$CONTROL_DB" "select count(*) from res_users where login like 'owner@journey-ci-%'")" = "0" ] \
  || { red "The tenant administrator exists as a user of the control database."; exit 1; }
green "  ok  the tenant administrator is not a user of the control database"
[ "$(q "$TENANT_DB" "select count(*) from res_users where active and not share and id > 1")" = "1" ] \
  || { red "Expected exactly one internal user in the new tenant database."; exit 1; }
green "  ok  the tenant database has exactly one internal user"

# -- 5. open the workspace over HTTP -----------------------------------------
info "Opening the workspace over HTTP on port $PORT"
"${ODOO_BIN[@]}" "${ODOO_ARGS[@]}" -d "$TENANT_DB" --db-filter="^${TENANT_DB}\$" --http-port="$PORT" --http-interface=127.0.0.1 \
  --workers=0 --max-cron-threads=0 > "$LOG_DIR/$CONTROL_DB-server.log" 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 60); do
  if curl -fsS --noproxy '*' "http://127.0.0.1:$PORT/web/health" >/dev/null 2>&1; then break; fi
  sleep 1
done
if ! NO_PROXY='*' no_proxy='*' "$PYTHON" "$REPO_ROOT/scripts/tenant_journey/open_workspace.py" \
      "http://127.0.0.1:$PORT" "$REAL_JSON" > "$LOG_DIR/$CONTROL_DB-workspace.log" 2>&1; then
  show "$LOG_DIR/$CONTROL_DB-workspace.log"; red "Opening the workspace FAILED:"; tail -20 "$LOG_DIR/$CONTROL_DB-workspace.log"; exit 1
fi
show "$LOG_DIR/$CONTROL_DB-workspace.log"

green "Tenant journey passed: register -> choose ERP -> entitlement -> isolated staging database -> workspace opened."
