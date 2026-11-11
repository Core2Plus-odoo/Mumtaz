#!/usr/bin/env bash
#
# Jawhar CI: fresh database -> install the addons -> run the tests.
#
# Slice 0 acceptance: "one command installs, tests and seeds a clean database;
# report lists real counts".
#
# This script only ever touches a throwaway database whose name it builds
# itself, and it refuses to run from `main`, because `main` auto-deploys to the
# production VPS (docs/mumtaz-jewel/CLAUDE.md). It never calls
# c2p-delivery-system/deploy/update.sh and never restarts a service.
#
# Usage:
#   scripts/jewel_ci.sh                 # install, test, seed, then drop the DB
#   KEEP_DB=1 scripts/jewel_ci.sh       # keep the database for inspection
#   SKIP_SEED=1 scripts/jewel_ci.sh     # install and test only
#
# The branch guard below refuses to run on `main`, so that nobody points this
# at the production checkout at /opt/mumtaz. A disposable CI runner has no
# production checkout, and gating `main` is exactly what CI is for, so it may
# opt out with JEWEL_CI_ALLOW_MAIN=1. Nothing else about the guard changes:
# the database name check and the refusal to touch update.sh still hold.
#
# Configuration (environment):
#   ODOO_PATH   checkout of Odoo 19 Community (must contain odoo-bin)
#   PYTHON      interpreter with Odoo's dependencies  (default: python3)
#   PGHOST PGPORT PGUSER PGPASSWORD     standard libpq variables
#   DB_NAME     override the generated database name
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULES="mumtaz_jewellery,mumtaz_jewellery_vip,mumtaz_jewellery_owner,mumtaz_jewellery_sale,mumtaz_jewellery_api"
SEED_MODULE="mumtaz_jewellery_demo"
TEST_TAGS="${TEST_TAGS:-/mumtaz_jewellery,/mumtaz_jewellery_vip,/mumtaz_jewellery_owner,/mumtaz_jewellery_sale,/mumtaz_jewellery_api,/mumtaz_jewellery_demo}"

PYTHON="${PYTHON:-python3}"
ODOO_PATH="${ODOO_PATH:-}"
DB_NAME="${DB_NAME:-jewel_ci_$$}"
LOG_DIR="${LOG_DIR:-${TMPDIR:-/tmp}/jewel-ci}"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
green(){ printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '\033[36m==> %s\033[0m\n' "$*"; }

# -- guard rails -------------------------------------------------------------
BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
if [ "$BRANCH" = "main" ] && [ "${JEWEL_CI_ALLOW_MAIN:-0}" != "1" ]; then
  red "Refusing to run on 'main': the production VPS pulls that branch."
  red "Check out the Jawhar feature branch first, or set"
  red "JEWEL_CI_ALLOW_MAIN=1 if this checkout is a disposable CI runner."
  exit 2
fi
case "$DB_NAME" in
  jewel_ci_*|jewel_test_*) : ;;
  *) red "DB_NAME must start with jewel_ci_ or jewel_test_ (got '$DB_NAME')."; exit 2 ;;
esac
if [ -z "$ODOO_PATH" ] || [ ! -x "$ODOO_PATH/odoo-bin" ]; then
  red "Set ODOO_PATH to an Odoo 19 Community checkout containing odoo-bin."
  exit 2
fi

mkdir -p "$LOG_DIR"
INSTALL_LOG="$LOG_DIR/$DB_NAME-install.log"
TEST_LOG="$LOG_DIR/$DB_NAME-test.log"
SEED_LOG="$LOG_DIR/$DB_NAME-seed.log"
ADDONS_PATH="$ODOO_PATH/addons,$REPO_ROOT/addons"

ODOO=( "$PYTHON" "$ODOO_PATH/odoo-bin"
       --addons-path="$ADDONS_PATH"
       --db_host="${PGHOST:-localhost}" --db_port="${PGPORT:-5432}"
       --db_user="${PGUSER:-odoo}"
       --data-dir="$LOG_DIR/$DB_NAME-filestore"
       --without-demo=True --no-http --stop-after-init --log-level=info
       # --test-enable starts an HTTP server regardless of --no-http
       # (odoo/service/server.py), so bind it to a port nothing else uses.
       # On the default 8069 a developer's running Odoo aborts the entire
       # test run with "Address already in use".
       --http-port="${JEWEL_TEST_HTTP_PORT:-8099}" )
if [ -n "${PGPASSWORD:-}" ]; then ODOO+=( --db_password="$PGPASSWORD" ); fi

cleanup() {
  if [ "${KEEP_DB:-0}" = "1" ]; then
    info "Database kept: $DB_NAME"
  else
    dropdb --if-exists "$DB_NAME" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

# -- 0. pure-Python engine tests --------------------------------------------
# The pricing engine and the offer ranking import no Odoo, so they run first
# and need no database. Odoo's own --test-tags filter skips plain
# unittest.TestCase classes, so running them here is what actually covers them.
info "Running the pure-Python engine tests (no database needed)"
UNIT_LOG="$LOG_DIR/unit.log"
mkdir -p "$LOG_DIR"
set +e
( cd "$REPO_ROOT/addons" && "$PYTHON" -m unittest discover -s mumtaz_jewellery/tests \
    -p 'test_pricing.py' -v ) > "$UNIT_LOG" 2>&1
UNIT_RC_A=$?
( cd "$REPO_ROOT/addons" && "$PYTHON" -m unittest discover -s mumtaz_jewellery_vip/tests \
    -p 'test_nbo.py' -v ) >> "$UNIT_LOG" 2>&1
UNIT_RC_B=$?
set -e
UNIT_COUNT="$(grep -cE '\.\.\. ok$' "$UNIT_LOG" || true)"
grep -E '^Ran [0-9]+ test' "$UNIT_LOG" || true
if [ "$UNIT_RC_A" -ne 0 ] || [ "$UNIT_RC_B" -ne 0 ]; then
  red "Pure-Python tests FAILED. See $UNIT_LOG"
  grep -E '^(FAIL|ERROR):' "$UNIT_LOG" | head -20 || true
  exit 1
fi
green "Pure-Python tests OK: $UNIT_COUNT passed"

# -- 1. fresh database -------------------------------------------------------
info "Branch: $BRANCH"
info "Creating a fresh database: $DB_NAME"
dropdb --if-exists "$DB_NAME" >/dev/null 2>&1 || true
createdb "$DB_NAME"

# -- 2. install --------------------------------------------------------------
info "Installing $MODULES"
if ! "${ODOO[@]}" -d "$DB_NAME" -i "$MODULES" > "$INSTALL_LOG" 2>&1; then
  red "Install FAILED. Last lines of $INSTALL_LOG:"; tail -40 "$INSTALL_LOG"; exit 1
fi
if grep -qE '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL)' "$INSTALL_LOG"; then
  red "Install logged errors:"; grep -E '(ERROR|CRITICAL)' "$INSTALL_LOG" | head -20; exit 1
fi
green "Install OK"

# -- 3. tests ---------------------------------------------------------------
info "Running the test suite (tags: $TEST_TAGS)"
set +e
"${ODOO[@]}" -d "$DB_NAME" -u "$MODULES" --test-enable --test-tags "$TEST_TAGS" \
  > "$TEST_LOG" 2>&1
TEST_RC=$?
set -e

# Odoo prints: "N failed, M error(s) of X tests" or "X tests ... 0 failed, 0 error(s)"
# `|| true`: a run that aborts before any test starts has no "Starting"
# lines; without it grep exits 1, pipefail propagates, and the script dies
# here -- before the TESTS FAILED report below that would show the cause.
ODOO_COUNT="$( (grep -oE 'Starting [A-Za-z]+\.[a-z0-9_]+ \.\.\.' "$TEST_LOG" || true) \
  | sort -u | wc -l | tr -d ' ')"
echo
info "Odoo test summary (verbatim):"
grep -E 'odoo\.tests\.(stats|result)|post-tests in ' "$TEST_LOG" | tail -10 || true
info "Distinct TransactionCase tests executed: $ODOO_COUNT"

if [ "$TEST_RC" -ne 0 ]; then
  echo
  red "TESTS FAILED (odoo-bin exit $TEST_RC). Failures:"
  grep -E '(FAIL|ERROR):' "$TEST_LOG" | head -40 || true
  red "Full log: $TEST_LOG"
  exit 1
fi
green "Tests OK  (log: $TEST_LOG)"

# -- 4. seed ----------------------------------------------------------------
if [ "${SKIP_SEED:-0}" = "1" ]; then
  info "SKIP_SEED=1, not seeding"
else
  info "Seeding synthetic DEMO data ($SEED_MODULE)"
  if ! "${ODOO[@]}" -d "$DB_NAME" -i "$SEED_MODULE" > "$SEED_LOG" 2>&1; then
    red "Seed FAILED. Last lines of $SEED_LOG:"; tail -40 "$SEED_LOG"; exit 1
  fi
  grep -E 'DEMO seed' "$SEED_LOG" | tail -3 || true
  green "Seed OK  (log: $SEED_LOG)"
fi

echo
green "Slice 0 CI finished on branch $BRANCH (database $DB_NAME)"
green "Totals: $UNIT_COUNT pure-Python tests, $ODOO_COUNT Odoo TransactionCase tests, 0 failures"
