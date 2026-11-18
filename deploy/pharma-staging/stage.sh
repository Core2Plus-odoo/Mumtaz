#!/usr/bin/env bash
# deploy/pharma-staging/stage.sh — stage the generic "pharma" Odoo 19 Community
# tenant on the VPS. STAGING ONLY. Touches exactly two databases, both named
# here: mumtaz_pharma (the tenant) and mumtaz_pharma_test (throwaway, dropped).
#
# It never edits nginx, DNS, the live odoo.conf or restarts the live service.
# Those are gates: see README.md / docs/pharma/DEPLOY_LOG.md.
#
#   bash deploy/pharma-staging/stage.sh backup       # pre-change backup
#   bash deploy/pharma-staging/stage.sh install      # create mumtaz_pharma + install modules
#   bash deploy/pharma-staging/stage.sh test         # fresh install into mumtaz_pharma_test with --test-tags pharma, then drop it
#   bash deploy/pharma-staging/stage.sh serve-check  # can the LIVE service see the pharma addons? (prints, changes nothing)
#   bash deploy/pharma-staging/stage.sh smoke        # /web/login, admin login, Pharma menus, pharma.mode, DEMO refusal
#   bash deploy/pharma-staging/stage.sh all          # backup + install + test
#
# Env overrides: ODOO_CONF (/etc/odoo/odoo.conf), ODOO_BIN (odoo), ODOO_USER (odoo),
#                STAGE_DIR (/opt/mumtaz/pharma-staging), KEEP_TEST_DB=1
set -euo pipefail

DB=mumtaz_pharma
TEST_DB=mumtaz_pharma_test
BRANCH=pharma-erp-v0.1
DOMAIN=pharma.mumtaz.digital
MODULES=base,account,sale_management,purchase,stock,mrp,website_sale,contacts,pharma_core,pharma_pk_tax_core,pharma_reconciliation_hub,pharma_demo_data

CHECKOUT="$(cd "$(dirname "$0")/../.." && pwd)"
LIVE_CONF="${ODOO_CONF:-/etc/odoo/odoo.conf}"
ODOO_BIN="${ODOO_BIN:-odoo}"
ODOO_USER="${ODOO_USER:-odoo}"
STAGE_DIR="${STAGE_DIR:-/opt/mumtaz/pharma-staging}"
STAGE_CONF="$STAGE_DIR/odoo-stage.conf"
BACKUP_DIR="$STAGE_DIR/backups"
LOG_DIR="$STAGE_DIR/logs"
TS="$(date +%Y%m%d_%H%M%S)"

say()  { printf '\n==> %s\n' "$*"; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
psqlq(){ sudo -u postgres psql -tAc "$1"; }
db_exists() { psqlq "select 1 from pg_database where datname='$1'" | grep -q 1; }
as_odoo() { sudo -u "$ODOO_USER" "$@"; }

guards() {
  [ "$(id -u)" -eq 0 ] || die "run as root (sudo)"
  local br; br="$(git -C "$CHECKOUT" rev-parse --abbrev-ref HEAD)"
  [ "$br" = "$BRANCH" ] || die "checkout $CHECKOUT is on '$br', expected '$BRANCH'"
  [ "$CHECKOUT" != "/opt/mumtaz" ] || die "refusing to run from /opt/mumtaz (tracks main). Clone the branch elsewhere."
  [ -r "$LIVE_CONF" ] || die "cannot read $LIVE_CONF (set ODOO_CONF=...)"
  for m in pharma_core pharma_pk_tax_core pharma_reconciliation_hub pharma_demo_data; do
    [ -f "$CHECKOUT/addons/$m/__manifest__.py" ] || die "missing addon $m in $CHECKOUT/addons"
  done
  command -v "$ODOO_BIN" >/dev/null || die "odoo binary '$ODOO_BIN' not found (set ODOO_BIN=...)"
  id "$ODOO_USER" >/dev/null 2>&1 || die "user '$ODOO_USER' not found (set ODOO_USER=...)"
  mkdir -p "$STAGE_DIR" "$BACKUP_DIR" "$LOG_DIR"
  chown "$ODOO_USER" "$LOG_DIR"
}

# A private config for the one-off CLI runs: the live conf + this checkout's
# addons, no dbfilter, its own logfile. The live conf is never modified.
render_conf() {
  python3 - "$LIVE_CONF" "$STAGE_CONF" "$CHECKOUT/addons" "$LOG_DIR/odoo-stage.log" <<'PY'
import configparser, sys
live, out, addons, log = sys.argv[1:]
cp = configparser.RawConfigParser(); cp.optionxform = str; cp.read(live)
o = cp["options"]
paths = [p.strip() for p in o.get("addons_path", "").split(",") if p.strip()]
if addons not in paths: paths.append(addons)
o["addons_path"] = ",".join(paths)
for k in ("dbfilter", "db_name", "logfile", "logrotate", "syslog", "workers"):
    o.pop(k, None)
o["logfile"] = log
o["list_db"] = "False"
with open(out, "w") as f: cp.write(f)
PY
  chmod 640 "$STAGE_CONF"; chown root:"$ODOO_USER" "$STAGE_CONF"
  echo "rendered $STAGE_CONF (live conf untouched)"
}

# Odoo 19 made --without-demo a plain flag; older builds want --without-demo=all.
without_demo_flag() {
  if "$ODOO_BIN" --help 2>/dev/null | grep -qE -- '--without-demo=?[A-Z]'; then echo "--without-demo=all"; else echo "--without-demo"; fi
}

cmd_backup() {
  say "backup -> $BACKUP_DIR (globals, DB list, nginx + odoo conf; $DB dump if it exists)"
  sudo -u postgres pg_dumpall --globals-only | gzip > "$BACKUP_DIR/pg_globals_$TS.sql.gz"
  psqlq "select datname from pg_database where not datistemplate order by 1" > "$BACKUP_DIR/databases_$TS.txt"
  tar czf "$BACKUP_DIR/conf_$TS.tgz" /etc/nginx "$LIVE_CONF" 2>/dev/null || tar czf "$BACKUP_DIR/conf_$TS.tgz" /etc/nginx
  if db_exists "$DB"; then
    sudo -u postgres pg_dump -Fc "$DB" > "$BACKUP_DIR/${DB}_$TS.dump"; echo "dumped existing $DB"
  fi
  chmod 600 "$BACKUP_DIR"/*; ls -la "$BACKUP_DIR"
}

set_admin_password() {
  say "set the admin password for $DB (never echoed, never stored)"
  local pw pw2 f
  read -r -s -p "new admin password: " pw; echo
  read -r -s -p "again: " pw2; echo
  [ -n "$pw" ] && [ "$pw" = "$pw2" ] || die "passwords empty or do not match"
  f="$(mktemp "$STAGE_DIR/.pw.XXXXXX")"; chmod 600 "$f"; chown "$ODOO_USER" "$f"; printf '%s' "$pw" > "$f"
  as_odoo "$ODOO_BIN" shell -c "$STAGE_CONF" -d "$DB" --no-http <<PY
import os
pw = open("$f").read()
env.ref("base.user_admin").write({"password": pw})
env.cr.commit()
print("admin password updated")
PY
  shred -u "$f" 2>/dev/null || rm -f "$f"
}

cmd_install() {
  guards; render_conf
  db_exists "$DB" && die "$DB already exists. This script never drops it; drop it yourself after a backup if a clean reinstall is wanted."
  local flag; flag="$(without_demo_flag)"
  say "create $DB and install: $MODULES  ($flag)"
  as_odoo "$ODOO_BIN" -c "$STAGE_CONF" -d "$DB" -i "$MODULES" "$flag" --stop-after-init --no-http \
    2>&1 | tee "$LOG_DIR/install_$TS.log" | grep -E "ERROR|CRITICAL|Traceback|Modules loaded|loading .* modules" || true
  grep -qE "ERROR|CRITICAL" "$LOG_DIR/install_$TS.log" && die "install log has errors: $LOG_DIR/install_$TS.log"
  set_admin_password
  say "pharma.mode after install:"
  sudo -u postgres psql -d "$DB" -tAc "select '  pharma.mode = '||value from ir_config_parameter where key='pharma.mode'"
}

cmd_test() {
  guards; render_conf
  db_exists "$TEST_DB" && die "$TEST_DB exists from a previous run; drop it first: sudo -u postgres dropdb $TEST_DB"
  local flag; flag="$(without_demo_flag)"
  say "fresh install into throwaway $TEST_DB with --test-enable --test-tags pharma (same deployment path, same module list)"
  set +e
  as_odoo "$ODOO_BIN" -c "$STAGE_CONF" -d "$TEST_DB" -i "$MODULES" "$flag" \
    --test-enable --test-tags pharma --stop-after-init --no-http --log-level=test > "$LOG_DIR/test_$TS.log" 2>&1
  local rc=$?
  set -e
  say "result (rc=$rc)"
  grep -E "tests when loading database|odoo.tests.result|post-tests in" "$LOG_DIR/test_$TS.log" || true
  grep -E "^.* (ERROR|FAIL):" "$LOG_DIR/test_$TS.log" | head -40 || true
  echo "full log: $LOG_DIR/test_$TS.log"
  if [ "${KEEP_TEST_DB:-0}" = "1" ]; then echo "kept $TEST_DB (KEEP_TEST_DB=1)"; else
    sudo -u postgres dropdb "$TEST_DB" && echo "dropped $TEST_DB"; fi
  return $rc
}

cmd_serve_check() {
  guards
  say "would the LIVE service ($LIVE_CONF) serve $DB at https://$DOMAIN ?"
  local f; f=$(grep -E '^\s*dbfilter\s*=' "$LIVE_CONF" | tail -1 | sed 's/.*=\s*//')
  [ "$f" = '^mumtaz_%d$' ] && echo "dbfilter OK (^mumtaz_%d\$): host 'pharma' -> $DB" || echo "GATE: dbfilter is '${f:-unset}', not ^mumtaz_%d\$ — needs a config change + restart (ask first)"
  grep -E '^\s*addons_path' "$LIVE_CONF" | sed 's/.*=\s*//' | tr ',' '\n' | while read -r p; do
    p="${p## }"; [ -d "$p/pharma_core" ] && echo "live addons_path has pharma_core via $p"
  done
  echo "If none of the live addons_path entries contains pharma_*, pick ONE (both are gates, ask first):"
  echo "  A) symlink the four addons/pharma_* dirs from $CHECKOUT/addons into an existing live addons dir (no restart, rm to roll back)"
  echo "  B) add $CHECKOUT/addons to addons_path in $LIVE_CONF and restart odoo (needs a restart window)"
}

cmd_smoke() {
  guards; render_conf
  say "HTTP: https://$DOMAIN/web/login"
  curl -sS -o /dev/null -w "  status=%{http_code}\n" --max-time 20 "https://$DOMAIN/web/login" || echo "  (curl failed)"
  say "XML-RPC as admin (password prompt, never echoed)"
  local pw; read -r -s -p "admin password: " pw; echo
  PHARMA_PW="$pw" python3 - "$DOMAIN" "$DB" <<'PY'
import os, sys, xmlrpc.client as x
host, db = sys.argv[1:]; pw = os.environ["PHARMA_PW"]
url = f"https://{host}"
uid = x.ServerProxy(url + "/xmlrpc/2/common").authenticate(db, "admin", pw, {})
print("  admin login:", "OK uid=%s" % uid if uid else "FAILED"); 
if not uid: sys.exit(1)
m = x.ServerProxy(url + "/xmlrpc/2/object")
def kw(model, meth, *a, **k): return m.execute_kw(db, uid, pw, model, meth, list(a), k)
print("  company:", kw("res.company", "search_read", [], fields=["name"])[0]["name"])
print("  pharma.mode:", kw("ir.config_parameter", "get_param", "pharma.mode"))
menus = kw("ir.ui.menu", "search_read", [["complete_name", "like", "Pharma"]], fields=["complete_name"], order="complete_name")
print("  Pharma menus visible to admin:")
for r in menus: print("    -", r["complete_name"])
want = {"Pharma/Tax Centre", "Pharma/Reconciliation", "Pharma/Reconciliation/Exception Queue"}
have = {r["complete_name"] for r in menus}
print("  required menus present:", "YES" if want <= have else f"MISSING {sorted(want - have)}")
for model in ("pharma.tax.rule", "pharma.recon.run", "pharma.recon.exception", "pharma.partner.stock.line", "pharma.tax.event"):
    print(f"  {model}: total={kw(model,'search_count',[])} demo={kw(model,'search_count',[['is_demo','=',True]])}")
PY
  say "production mode must refuse DEMO rules (odoo shell, transaction ROLLED BACK, DB unchanged)"
  as_odoo "$ODOO_BIN" shell -c "$STAGE_CONF" -d "$DB" --no-http <<'PY'
from datetime import date
P = env["ir.config_parameter"].sudo()
before = P.get_param("pharma.mode")
P.set_param("pharma.mode", "production")
p = env["product.product"].search([("default_code", "=", "DEMO-SKU-A")], limit=1)
res = env["pharma.tax.rule"].resolve(p, date(2026, 11, 3), 1000.0, "SALES_TAX_OUTPUT")
print("  in production mode:", res["resolution"], "|", res["reason"])
assert res["resolution"] != "resolved" and "DEMO-only" in res["reason"], "DEMO rule was NOT refused"
env.cr.rollback()
print("  rolled back; pharma.mode is still:", env["ir.config_parameter"].sudo().get_param("pharma.mode"), "(was %s)" % before)
PY
}

case "${1:-}" in
  backup)      guards; cmd_backup ;;
  install)     cmd_install ;;
  test)        cmd_test ;;
  serve-check) cmd_serve_check ;;
  smoke)       cmd_smoke ;;
  all)         guards; cmd_backup; cmd_install; cmd_test ;;
  *) sed -n '2,20p' "$0"; exit 2 ;;
esac
