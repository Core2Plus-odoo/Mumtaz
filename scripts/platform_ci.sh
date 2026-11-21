#!/usr/bin/env bash
#
# Platform CI: fresh database -> install every non-jewellery addon -> run
# whatever tests those addons carry -> drop the database.
#
# This is backlog item 1 of docs/erp/BACKLOG.md ("fresh-database install CI
# for every module"). Before it existed, 39 of the 52 addons had never been
# installed on a clean Odoo 19 database by any automated check; four of them
# could not be (see docs/erp/quality/RELEASE_CHANGELOG.md, 21 Nov 2026).
#
# Same shape and the same guard rails as scripts/jewel_ci.sh: a throwaway
# database whose name it builds itself, a refusal to run from `main` unless
# a disposable runner opts out, no deploy script, no service restart.
#
# Usage:
#   scripts/platform_ci.sh                  # install + tests, then drop the DB
#   KEEP_DB=1 scripts/platform_ci.sh        # keep the database for inspection
#   MODULES=a,b scripts/platform_ci.sh      # a subset
#
# Configuration (environment): ODOO_PATH, PYTHON, PGHOST PGPORT PGUSER
# PGPASSWORD, DB_NAME, LOG_DIR, JEWEL_CI_ALLOW_MAIN (same meaning as jewel_ci).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Every addon that is not part of the Jawhar edition (that set has its own
# script and workflow). Computed from the tree so a new module cannot be
# forgotten: the day it is added it is installed here.
DEFAULT_MODULES="$(ls "$REPO_ROOT/addons" | grep -v '^mumtaz_jewellery' | tr '\n' ',' | sed 's/,$//')"
MODULES="${MODULES:-$DEFAULT_MODULES}"
# Odoo's --test-tags takes module names prefixed with a slash.
TEST_TAGS="${TEST_TAGS:-$(echo "$MODULES" | sed 's/^/\//; s/,/,\//g')}"

PYTHON="${PYTHON:-python3}"
ODOO_PATH="${ODOO_PATH:-}"
DB_NAME="${DB_NAME:-plat_ci_$$}"
LOG_DIR="${LOG_DIR:-${TMPDIR:-/tmp}/platform-ci}"

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
case "$DB_NAME" in
  plat_ci_*|plat_test_*) : ;;
  *) red "DB_NAME must start with plat_ci_ or plat_test_ (got '$DB_NAME')."; exit 2 ;;
esac
if [ -z "$ODOO_PATH" ] || [ ! -x "$ODOO_PATH/odoo-bin" ]; then
  red "Set ODOO_PATH to an Odoo 19 Community checkout containing odoo-bin."
  exit 2
fi

cleanup() {
  if [ "${KEEP_DB:-0}" = "1" ]; then info "Database kept: $DB_NAME"
  else dropdb --if-exists "$DB_NAME" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT

mkdir -p "$LOG_DIR"
INSTALL_LOG="$LOG_DIR/$DB_NAME-install.log"
TEST_LOG="$LOG_DIR/$DB_NAME-tests.log"
ADDONS_PATH="$ODOO_PATH/addons,$REPO_ROOT/addons"
ODOO=( "$PYTHON" "$ODOO_PATH/odoo-bin"
       --addons-path="$ADDONS_PATH"
       --db_host="${PGHOST:-localhost}" --db_port="${PGPORT:-5432}" --db_user="${PGUSER:-odoo}"
       --data-dir="$LOG_DIR/$DB_NAME-filestore"
       --without-demo=True --no-http --stop-after-init --log-level=info
       --http-port="${PLATFORM_TEST_HTTP_PORT:-8098}" )
if [ -n "${PGPASSWORD:-}" ]; then ODOO+=( --db_password="$PGPASSWORD" ); fi

# -- 1. fresh database -------------------------------------------------------
info "Branch: $BRANCH"
info "Creating a fresh database: $DB_NAME"
dropdb --if-exists "$DB_NAME" >/dev/null 2>&1 || true
createdb "$DB_NAME"

# -- 2. install every module in one go ---------------------------------------
COUNT="$(echo "$MODULES" | tr ',' '\n' | wc -l | tr -d ' ')"
info "Installing $COUNT modules: $MODULES"
if ! "${ODOO[@]}" -d "$DB_NAME" -i "$MODULES" > "$INSTALL_LOG" 2>&1; then
  red "Install FAILED. Last lines of $INSTALL_LOG:"; tail -40 "$INSTALL_LOG"; exit 1
fi
if grep -qE '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL)' "$INSTALL_LOG"; then
  red "Install logged errors:"; grep -E '(ERROR|CRITICAL)' "$INSTALL_LOG" | head -20; exit 1
fi
# Counted in SQL rather than through odoo shell: psql ships with createdb,
# and a count that cannot be read must fail the run, not pass as "?".
INSTALLED="$(psql -d "$DB_NAME" -tAc "select count(*) from ir_module_module where state='installed' and name = any(string_to_array('$MODULES', ','))" | tr -d '[:space:]')"
green "Install OK: $INSTALLED of $COUNT modules report state=installed"
if [ "$INSTALLED" != "$COUNT" ]; then red "Not every module is installed."; exit 1; fi

# -- 3. tests (the modules that carry any) + upgrade --------------------------
info "Upgrading all modules with --test-enable (tags: $TEST_TAGS)"
set +e
"${ODOO[@]}" -d "$DB_NAME" -u "$MODULES" --test-enable --test-tags "$TEST_TAGS" > "$TEST_LOG" 2>&1
TEST_RC=$?
set -e
ODOO_COUNT="$( (grep -oE 'Starting [A-Za-z]+\.[a-z0-9_]+ \.\.\.' "$TEST_LOG" || true) | sort -u | wc -l | tr -d ' ')"
info "Odoo test summary (verbatim):"
grep -E 'odoo\.tests\.(stats|result)' "$TEST_LOG" | tail -5 || true
info "Distinct test methods executed: $ODOO_COUNT"
if [ "$TEST_RC" -ne 0 ]; then
  red "TESTS or UPGRADE FAILED (odoo-bin exit $TEST_RC):"; grep -E '(FAIL|ERROR):' "$TEST_LOG" | head -40 || true
  red "Full log: $TEST_LOG"; exit 1
fi
if grep -qE '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL)' "$TEST_LOG"; then
  red "Upgrade/tests logged errors:"; grep -E '(ERROR|CRITICAL)' "$TEST_LOG" | head -20; exit 1
fi
green "Upgrade and tests OK  (log: $TEST_LOG)"
green "Platform CI passed: $COUNT modules install, upgrade and test on a fresh Odoo 19 database."
