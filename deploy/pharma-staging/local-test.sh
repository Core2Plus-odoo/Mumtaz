#!/usr/bin/env bash
# deploy/pharma-staging/local-test.sh — run the pharma tests (and an upgrade rehearsal) against a REAL Odoo 19 on any
# Linux box with PostgreSQL, with no VPS and no production data. Everything lives under $WORK (default ~/pharma-local);
# databases are throwaway (pharma_local_*). Nothing here touches a server, nginx, DNS or any existing database.
#
#   local-test.sh tests                  fresh install of the pharma module list + the tests tagged `pharma`
#   local-test.sh rehearse <git-rev>     install the add-ons AS THEY WERE at <git-rev> (e.g. what staging runs), then
#                                        upgrade the same database with the current checkout, and print what changed
#
# Not covered (still the VPS gates): the third-party accounting kit and pharma_accounting_hardening (their source is not in
# the repo), the real service/nginx/TLS, and anything a browser shows. Output is evidence only when you paste the result line.
set -euo pipefail
MODE="${1:-}"; REV="${2:-}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="${WORK:-$HOME/pharma-local}"; ODOO="$WORK/odoo"; VENV="$WORK/venv"; PORT="${PORT:-8199}"
MODS=base,account,sale_management,purchase,stock,mrp,website_sale,contacts,pharma_core,pharma_pk_tax_core,pharma_reconciliation_hub,pharma_partner_stock,pharma_demo_data,pharma_website_demo,pharma_courier_cod,pharma_courier_cod_accounting,pharma_courier_cod_demo
say() { printf '\n==> %s\n' "$*"; }

prepare() {
  mkdir -p "$WORK"
  command -v psql >/dev/null || { echo "PostgreSQL client/server is required"; exit 1; }
  pg_isready -q || { sudo pg_ctlcluster "$(ls /usr/lib/postgresql | tail -1)" main start 2>/dev/null || true; sleep 3; }
  psql -d postgres -tAc "select 1" >/dev/null 2>&1 || { echo "cannot connect to PostgreSQL as $(whoami): create the role with: sudo -u postgres createuser -s $(whoami)"; exit 1; }
  [ -d "$ODOO/.git" ] || { say "fetch Odoo 19.0 (depth 1)"; git clone -q --depth 1 --branch 19.0 --single-branch https://github.com/odoo/odoo.git "$ODOO"; }
  if [ ! -x "$VENV/bin/python" ]; then
    say "create venv and install Odoo's requirements (psycopg2-binary instead of psycopg2; python-ldap skipped: no pharma module uses LDAP)"
    python3 -m venv "$VENV"; "$VENV/bin/pip" install -q --upgrade pip wheel setuptools
    grep -viE '^psycopg2|^python-ldap' "$ODOO/requirements.txt" > "$WORK/requirements-filtered.txt"
    "$VENV/bin/pip" install -q psycopg2-binary -r "$WORK/requirements-filtered.txt"
  fi
}
odoo() { "$VENV/bin/python" "$ODOO/odoo-bin" --http-port="$PORT" --max-cron-threads=0 --log-level=info "$@"; }
resultline() { grep -E "odoo.tests.result|post-tests in" "$1" | sed 's/^.*odoo\.//' ; grep -E " (ERROR|CRITICAL) " "$1" | grep -v "bad query" | head -5 || true; }

case "$MODE" in
  tests)
    prepare; DB=pharma_local_tests; dropdb --if-exists "$DB"
    say "fresh install into $DB with --test-tags pharma (log: $WORK/tests.log)"
    set +e; odoo -d "$DB" -i "$MODS" --addons-path="$ODOO/odoo/addons,$REPO/addons" --without-demo --test-enable --test-tags pharma --stop-after-init > "$WORK/tests.log" 2>&1; rc=$?; set -e
    say "result (exit $rc)"; resultline "$WORK/tests.log"; dropdb --if-exists "$DB"; exit $rc ;;
  rehearse)
    [ -n "$REV" ] || { echo "usage: $0 rehearse <git-rev>"; exit 2; }
    prepare; DB=pharma_local_up; OLD="$WORK/old-addons"; dropdb --if-exists "$DB"
    rm -rf "$OLD"; git -C "$REPO" worktree add -f --detach "$OLD" "$REV" >/dev/null 2>&1
    say "install the add-ons as of $REV into $DB"
    odoo -d "$DB" -i "$MODS" --addons-path="$ODOO/odoo/addons,$OLD/addons" --without-demo --stop-after-init > "$WORK/up1.log" 2>&1
    psql -d "$DB" -tAc "select '  menu roots before: '||string_agg(name->>'en_US', ', ') from ir_ui_menu where parent_id is null and id in (select res_id from ir_model_data where model='ir.ui.menu' and module like 'pharma%')"
    UPD="$(psql -d "$DB" -tAc "select string_agg(name, ',') from ir_module_module where state='installed' and name like 'pharma%'")"
    say "upgrade $DB with the current checkout: -u $UPD (log: $WORK/up2.log)"
    set +e; odoo -d "$DB" -u "$UPD" --addons-path="$ODOO/odoo/addons,$REPO/addons" --stop-after-init > "$WORK/up2.log" 2>&1; rc=$?; set -e
    grep -E " (ERROR|CRITICAL) |Traceback" "$WORK/up2.log" | head -5 || true
    psql -d "$DB" -tAc "select '  menu roots after: '||coalesce(string_agg(name->>'en_US', ', '),'(none)') from ir_ui_menu where parent_id is null and id in (select res_id from ir_model_data where model='ir.ui.menu' and module like 'pharma%')"
    psql -d "$DB" -tAc "select '  versions after: '||string_agg(name||'='||latest_version, ', ' order by name) from ir_module_module where state='installed' and name like 'pharma%'"
    git -C "$REPO" worktree remove --force "$OLD" 2>/dev/null || true; dropdb --if-exists "$DB"
    say "rehearsal $([ $rc -eq 0 ] && echo 'upgrade exit 0' || echo "FAILED (exit $rc)")"; exit $rc ;;
  *) sed -n '2,12p' "$0"; exit 2 ;;
esac
