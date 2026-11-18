#!/usr/bin/env bash
# deploy/pharma-staging/stage.sh — stage the generic "pharma" Odoo 19 Community
# tenant on the VPS. STAGING ONLY.
#
# Shape (same as the other tenants on this box: one odooN.service + /etc/odooN.conf
# + one nginx vhost each): its own unit `odoo-pharma.service`, its own config
# /etc/odoo-pharma.conf with dbfilter ^mumtaz_%d$, ports 127.0.0.1:8076 (http) and
# 8077 (websocket), the same local Postgres. The live /etc/odoo/odoo.conf and the
# live odoo*.service units are never read for anything but db credentials, and
# never written or restarted.
#
# Databases touched, both named here and nowhere else: mumtaz_pharma (the tenant)
# and mumtaz_pharma_test (throwaway, dropped at the end of `test`).
#
#   stage.sh preflight     detect CLI flags, check the rendered conf is readable by odoo
#   stage.sh backup        pre-change backup (pg globals, DB list, /etc/nginx + odoo confs)
#   stage.sh install       create mumtaz_pharma + install the module list (resumes if done), set admin password, verify
#   stage.sh admin-login <login>  rename the admin user's login (e.g. to an email) and set its password
#   stage.sh verify        read-only facts about mumtaz_pharma (mode, module states, demo counts)
#   stage.sh test          fresh install into mumtaz_pharma_test with --test-tags pharma, drop it
#   stage.sh service       GATE: write /etc/odoo-pharma.conf + odoo-pharma.service, enable + start
#   stage.sh upgrade       GATE: backup mumtaz_pharma, -u pharma_* -i new pharma modules, restart odoo-pharma only, verify
#   stage.sh demo-passwords  set one password on the four demo users (pharma.ops / .maker / .approver / .finance), typed interactively
#   stage.sh neutralize    GATE: odoo neutralize -d mumtaz_pharma (banner; mail/crons/payments off), restart odoo-pharma
#   stage.sh smoke-local   via 127.0.0.1:8076 with Host: pharma.mumtaz.digital (before DNS/nginx)
#   stage.sh smoke         via https://pharma.mumtaz.digital (after DNS + nginx + cert)
#   stage.sh service-remove  rollback of `service` (stop, disable, delete the two files)
#
# Env overrides: ODOO_CONF (/etc/odoo/odoo.conf), ODOO_BIN (odoo), ODOO_USER (odoo),
#                STAGE_DIR (/var/local/pharma-staging), KEEP_TEST_DB=1
set -euo pipefail

DB=mumtaz_pharma
TEST_DB=mumtaz_pharma_test
BRANCH=pharma-erp-v0.1
DOMAIN=pharma.mumtaz.digital
HTTP_PORT=8076
WS_PORT=8077
UNIT=odoo-pharma
SVC_CONF=/etc/odoo-pharma.conf
SVC_LOG=/var/log/odoo/odoo-pharma.log
MODULES=base,account,sale_management,purchase,stock,mrp,website_sale,contacts,pharma_core,pharma_pk_tax_core,pharma_reconciliation_hub,pharma_demo_data,pharma_website_demo
PHARMA_MODULES=pharma_core,pharma_pk_tax_core,pharma_reconciliation_hub,pharma_demo_data,pharma_website_demo

CHECKOUT="$(cd "$(dirname "$0")/../.." && pwd)"
LIVE_CONF="${ODOO_CONF:-/etc/odoo/odoo.conf}"
ODOO_BIN="${ODOO_BIN:-odoo}"
ODOO_USER="${ODOO_USER:-odoo}"
STAGE_DIR="${STAGE_DIR:-/var/local/pharma-staging}"
STAGE_CONF="$STAGE_DIR/odoo-cli.conf"
BACKUP_DIR="$STAGE_DIR/backups"
LOG_DIR="$STAGE_DIR/logs"
TS="$(date +%Y%m%d_%H%M%S)"

say()  { printf '\n==> %s\n' "$*"; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
psqlq(){ sudo -u postgres psql -tAc "$1"; }
db_exists() { psqlq "select 1 from pg_database where datname='$1'" | grep -q 1; }
as_odoo() { sudo -u "$ODOO_USER" "$@"; }

guards() {
  [ "$(id -u)" -eq 0 ] || die "run as root"
  local br; br="$(git -C "$CHECKOUT" rev-parse --abbrev-ref HEAD)"
  [ "$br" = "$BRANCH" ] || die "checkout $CHECKOUT is on '$br', expected '$BRANCH'"
  case "$CHECKOUT" in /opt/mumtaz|/opt/custom_addons/*) die "refusing to run from a production checkout ($CHECKOUT)";; esac
  [ -r "$LIVE_CONF" ] || die "cannot read $LIVE_CONF (set ODOO_CONF=...)"
  for m in pharma_core pharma_pk_tax_core pharma_reconciliation_hub pharma_demo_data; do
    [ -f "$CHECKOUT/addons/$m/__manifest__.py" ] || die "missing addon $m in $CHECKOUT/addons"
  done
  command -v "$ODOO_BIN" >/dev/null || die "odoo binary '$ODOO_BIN' not found"
  id "$ODOO_USER" >/dev/null 2>&1 || die "user '$ODOO_USER' not found"
  mkdir -p "$STAGE_DIR" "$BACKUP_DIR" "$LOG_DIR"
  chown root:"$ODOO_USER" "$STAGE_DIR"; chmod 750 "$STAGE_DIR"   # odoo must traverse it to read the rendered conf
  chown "$ODOO_USER" "$LOG_DIR"; chmod 700 "$BACKUP_DIR"
}

# A free loopback port pair for one-off CLI runs (test mode starts an HTTP server).
free_cli_port() {
  local p; for p in 8086 8088 8090 8092 8094 8096; do
    ss -ltn | grep -qE ":($p|$((p+1)))\b" || { echo "$p"; return; }
  done; die "no free port pair in 8086-8097 for the CLI run"
}

# Render an Odoo config from the live one: keep db_* credentials, replace
# everything tenant-specific. $1 = output path, $2 = "cli" or "service".
render_conf() {
  local out="$1" mode="$2"
  python3 - "$LIVE_CONF" "$out" "$mode" "$CHECKOUT/addons" "$(free_cli_port)" "$SVC_LOG" "$HTTP_PORT" "$WS_PORT" <<'PY'
import configparser, sys
live, out, mode, addons, cli_port, svc_log, http_port, ws_port = sys.argv[1:]
cp = configparser.RawConfigParser(); cp.optionxform = str; cp.read(live)
o = cp["options"]
keep = {k: o[k] for k in ("db_host", "db_port", "db_user", "db_password", "db_sslmode", "db_maxconn", "admin_passwd")
        if k in o and o[k].strip() not in ("", "False", "None")}
for k in list(o): del o[k]
o.update(keep)
o["addons_path"] = "/usr/lib/python3/dist-packages/odoo/addons," + addons
o["list_db"] = "False"
o["proxy_mode"] = "True"
if mode == "service":
    o["dbfilter"] = "^mumtaz_%d$"
    o["db_name"] = "mumtaz_pharma"      # scopes the cron scheduler to this DB; without it Odoo polls EVERY database on the server
    o["http_interface"] = "127.0.0.1"
    o["http_port"] = http_port
    o["gevent_port"] = ws_port
    o["workers"] = "2"
    o["max_cron_threads"] = "1"
    o["limit_memory_soft"] = str(640 * 1024 * 1024)
    o["limit_memory_hard"] = str(1024 * 1024 * 1024)
    o["limit_time_cpu"] = "120"
    o["limit_time_real"] = "240"
    o["logfile"] = svc_log
    o["log_level"] = "info"
else:
    # --test-enable starts the HTTP server even with --no-http (browser tests need it), so
    # bind loopback on a free port instead of colliding with the live service on 8069.
    o["http_interface"] = "127.0.0.1"
    o["http_port"] = cli_port
    o["gevent_port"] = str(int(cli_port) + 1)
# cli mode: no logfile, so Odoo logs to stderr and the run log is one file
with open(out, "w") as f:
    f.write("; rendered by deploy/pharma-staging/stage.sh (%s) — STAGING tenant pharma. Not hand-edited.\n" % mode)
    cp.write(f)
PY
  chmod 640 "$out"; chown root:"$ODOO_USER" "$out"
}

# Odoo 19 splits the CLI into subcommands, so the server flags are under
# `odoo server --help`; older builds list them under `odoo --help`.
odoo_help() { "$ODOO_BIN" server --help 2>/dev/null || "$ODOO_BIN" --help 2>/dev/null || true; }
odoo_major() { "$ODOO_BIN" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1 | cut -d. -f1; }
# <=18: --without-demo=all ; 19+: plain --without-demo (a value is rejected with a warning)
without_demo_flag() {
  local maj; maj="$(odoo_major)"
  if [ -n "$maj" ] && [ "$maj" -ge 19 ]; then echo "--without-demo"
  elif grep -qE -- '--without-demo' <<<"$(odoo_help)"; then echo "--without-demo=all"
  else echo ""; fi
}
no_http_flag() { grep -qE -- '--no-http' <<<"$(odoo_help)" && echo "--no-http" || echo ""; }
preflight() {
  render_conf "$STAGE_CONF" cli
  say "preflight"
  echo "  odoo: $(command -v "$ODOO_BIN")  $("$ODOO_BIN" --version 2>/dev/null | tail -1)"
  echo "  demo flag: '$(without_demo_flag)'   no-http flag: '$(no_http_flag)'   cli http port: $(grep -E '^http_port' "$STAGE_CONF" | sed 's/.*= *//') (loopback)"
  as_odoo test -r "$STAGE_CONF" && echo "  $STAGE_CONF readable by $ODOO_USER: yes" || die "$STAGE_CONF not readable by $ODOO_USER"
  as_odoo test -r "$CHECKOUT/addons/pharma_core/__manifest__.py" && echo "  checkout readable by $ODOO_USER: yes" || die "$CHECKOUT not readable by $ODOO_USER"
}

cmd_backup() {
  say "backup -> $BACKUP_DIR"
  sudo -u postgres pg_dumpall --globals-only | gzip > "$BACKUP_DIR/pg_globals_$TS.sql.gz"
  psqlq "select datname from pg_database where not datistemplate order by 1" > "$BACKUP_DIR/databases_$TS.txt"
  tar czf "$BACKUP_DIR/conf_$TS.tgz" /etc/nginx /etc/odoo /etc/odoo*.conf /etc/systemd/system/odoo*.service 2>/dev/null || true
  if db_exists "$DB"; then sudo -u postgres pg_dump -Fc "$DB" > "$BACKUP_DIR/${DB}_$TS.dump"; echo "dumped existing $DB"; fi
  chmod 600 "$BACKUP_DIR"/*; ls -la "$BACKUP_DIR"
}

set_admin_password() {
  say "set the admin password for $DB (typed twice, never echoed, never stored)"
  local pw pw2 f
  read -r -s -p "new admin password: " pw; echo
  read -r -s -p "again: " pw2; echo
  [ -n "$pw" ] && [ "$pw" = "$pw2" ] || die "passwords empty or do not match"
  f="$(mktemp "$STAGE_DIR/.pw.XXXXXX")"; chmod 600 "$f"; chown "$ODOO_USER" "$f"; printf '%s' "$pw" > "$f"
  as_odoo "$ODOO_BIN" shell -c "$STAGE_CONF" -d "$DB" $(no_http_flag) <<PY
pw = open("$f").read()
env.ref("base.user_admin").write({"password": pw})
env.cr.commit()
print("admin password updated")
PY
  shred -u "$f" 2>/dev/null || rm -f "$f"
}

pharma_installed_count() { sudo -u postgres psql -d "$DB" -tAc "select count(*) from ir_module_module where name in ('pharma_core','pharma_pk_tax_core','pharma_reconciliation_hub','pharma_demo_data') and state='installed'" 2>/dev/null || echo 0; }

cmd_verify() {
  say "verify $DB"
  sudo -u postgres psql -d "$DB" -tAc "select '  pharma.mode = '||value from ir_config_parameter where key='pharma.mode'"
  sudo -u postgres psql -d "$DB" -tAc "select '  '||name||' = '||state from ir_module_module where name like 'pharma%' order by name"
  sudo -u postgres psql -d "$DB" -tAc "select '  modules installed total = '||count(*) from ir_module_module where state='installed'"
  sudo -u postgres psql -d "$DB" -tAc "select '  company = '||name from res_company order by id limit 1"
  sudo -u postgres psql -d "$DB" -tAc "select '  demo tax rules = '||count(*) from pharma_tax_rule where is_demo"
  sudo -u postgres psql -d "$DB" -tAc "select '  demo recon runs = '||count(*) from pharma_recon_run where is_demo"
  sudo -u postgres psql -d "$DB" -tAc "select '  open exceptions = '||count(*) from pharma_recon_exception where state <> 'closed'"
  sudo -u postgres psql -d "$DB" -tAc "select '  exceptions by state: '||string_agg(state||'='||n, ', ' order by state) from (select state, count(*) n from pharma_recon_exception group by state) x"
  sudo -u postgres psql -d "$DB" -tAc "select '  tax rules by state: '||string_agg(state||'='||n, ', ' order by state) from (select state, count(*) n from pharma_tax_rule group by state) x"
  sudo -u postgres psql -d "$DB" -tAc "select '  demo users = '||string_agg(login, ', ' order by login) from res_users where login like 'pharma.%'"
  sudo -u postgres psql -d "$DB" -tAc "select '  published DEMO products = '||count(*) from product_template where is_published and default_code like 'DEMO-SKU-%'" 2>/dev/null || true
  sudo -u postgres psql -d "$DB" -tAc "select '  website homepage_url = '||coalesce(homepage_url,'(default)')||' | name = '||name from website order by id limit 1" 2>/dev/null || true
}

cmd_install() {
  guards; preflight
  if db_exists "$DB"; then
    [ "$(pharma_installed_count)" = "4" ] || die "$DB exists but the pharma modules are not all installed. This script never drops it; inspect, then drop it yourself after a backup."
    say "$DB already exists with all four pharma modules installed — skipping install, continuing with password + verify"
  else
    local flags; flags="$(without_demo_flag) $(no_http_flag)"
    say "create $DB and install: $MODULES  ($flags)  — log: $LOG_DIR/install_$TS.log"
    # shellcheck disable=SC2086
    as_odoo "$ODOO_BIN" -c "$STAGE_CONF" -d "$DB" -i "$MODULES" $flags --stop-after-init \
      > "$LOG_DIR/install_$TS.log" 2>&1 || true
    grep -E " (ERROR|CRITICAL) |Traceback|modules loaded in|Modules loaded" "$LOG_DIR/install_$TS.log" | tail -20 || true
    grep -qE " (ERROR|CRITICAL) " "$LOG_DIR/install_$TS.log" && die "install log has errors: $LOG_DIR/install_$TS.log"
    grep -q "Modules loaded" "$LOG_DIR/install_$TS.log" || die "install did not reach 'Modules loaded': $LOG_DIR/install_$TS.log"
  fi
  set_admin_password
  cmd_verify
}

drop_test_db() {
  # Other Odoo instances on this box without db_name/dbfilter poll every database for cron
  # jobs, so a stray session on the throwaway DB is expected. --force ends only sessions on
  # THIS database (mumtaz_pharma_test); nothing else is touched.
  sudo -u postgres psql -tAc "select '  session on $TEST_DB: '||coalesce(application_name,'?')||' pid='||pid||' since '||backend_start from pg_stat_activity where datname='$TEST_DB'" || true
  sudo -u postgres dropdb --force "$TEST_DB" && echo "dropped $TEST_DB"
}

cmd_test() {
  guards; preflight
  if db_exists "$TEST_DB"; then say "$TEST_DB left over from a previous run — dropping it first"; drop_test_db; fi
  local flags; flags="$(without_demo_flag) $(no_http_flag)"
  say "fresh install into throwaway $TEST_DB with --test-enable --test-tags pharma (same module list as the real install)"
  set +e
  # shellcheck disable=SC2086
  as_odoo "$ODOO_BIN" -c "$STAGE_CONF" -d "$TEST_DB" -i "$MODULES" $flags \
    --test-enable --test-tags pharma --stop-after-init > "$LOG_DIR/test_$TS.log" 2>&1
  local rc=$?
  set -e
  say "result (exit $rc)"
  grep -E "tests when loading database|post-tests in|odoo.tests.stats|odoo.tests.result|Modules loaded" "$LOG_DIR/test_$TS.log" || true
  grep -E " (ERROR|FAIL|CRITICAL) |Traceback|Error:" "$LOG_DIR/test_$TS.log" | head -40 || true
  tail -n 5 "$LOG_DIR/test_$TS.log"
  echo "full log: $LOG_DIR/test_$TS.log"
  if ! db_exists "$TEST_DB"; then echo "($TEST_DB was never created — Odoo stopped before touching Postgres)"
  elif [ "${KEEP_TEST_DB:-0}" = "1" ]; then echo "kept $TEST_DB (KEEP_TEST_DB=1)"
  else drop_test_db; fi
  return $rc
}

cmd_service() {
  guards
  say "GATE: new unit $UNIT.service + $SVC_CONF (dbfilter ^mumtaz_%d\$, 127.0.0.1:$HTTP_PORT/$WS_PORT). Touches no other unit or conf."
  ss -ltn | grep -qE ":($HTTP_PORT|$WS_PORT)\b" && die "port $HTTP_PORT or $WS_PORT is in use"
  render_conf "$SVC_CONF" service
  cat > /etc/systemd/system/$UNIT.service <<UNITEOF
[Unit]
Description=Odoo 19 — pharma STAGING tenant (mumtaz_pharma, $DOMAIN)
Documentation=$CHECKOUT/docs/pharma/DEPLOY_LOG.md
After=network.target postgresql.service

[Service]
Type=simple
User=$ODOO_USER
Group=$ODOO_USER
ExecStart=$(command -v "$ODOO_BIN") --config $SVC_CONF
KillMode=mixed
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNITEOF
  systemctl daemon-reload
  systemctl enable --now $UNIT.service
  sleep 6
  systemctl --no-pager --lines=5 status $UNIT.service || true
  printf 'health: '; curl -sS -o /dev/null -w '%{http_code}\n' --max-time 20 "http://127.0.0.1:$HTTP_PORT/web/health" || echo "(not up yet; tail -f $SVC_LOG)"
}

admin_login() { sudo -u postgres psql -d "$DB" -tAc "select u.login from res_users u join ir_model_data d on d.res_id=u.id and d.model='res.users' and d.module='base' and d.name='user_admin'" | tr -d ' '; }

cmd_admin_login() {
  guards; render_conf "$STAGE_CONF" cli
  local new="${1:-}"; [ -n "$new" ] || die "usage: stage.sh admin-login <new login, e.g. an email>"
  say "set the admin user's login to '$new' on $DB (password prompted next)"
  as_odoo "$ODOO_BIN" shell -c "$STAGE_CONF" -d "$DB" $(no_http_flag) 2>/dev/null <<PY
u = env.ref("base.user_admin")
u.write({"login": "$new"})
env.cr.commit()
print("  admin login is now:", u.login)
PY
  set_admin_password
}

cmd_upgrade() {
  guards; preflight
  db_exists "$DB" || die "$DB does not exist; run install first"
  say "GATE: upgrade $DB — dump first, then -u (pharma modules already installed) -i (pharma modules not yet installed)"
  sudo -u postgres pg_dump -Fc "$DB" > "$BACKUP_DIR/${DB}_pre_upgrade_$TS.dump"; chmod 600 "$BACKUP_DIR/${DB}_pre_upgrade_$TS.dump"
  echo "  dump: $BACKUP_DIR/${DB}_pre_upgrade_$TS.dump ($(du -h "$BACKUP_DIR/${DB}_pre_upgrade_$TS.dump" | cut -f1))"
  local installed to_update="" to_install=""
  installed="$(sudo -u postgres psql -d "$DB" -tAc "select string_agg(name, ',') from ir_module_module where state='installed' and name like 'pharma%'")"
  for m in ${PHARMA_MODULES//,/ }; do
    case ",$installed," in *",$m,"*) to_update="$to_update,$m";; *) to_install="$to_install,$m";; esac
  done
  to_update="${to_update#,}"; to_install="${to_install#,}"
  echo "  update: ${to_update:-<none>}   install: ${to_install:-<none>}"
  local args=(-c "$STAGE_CONF" -d "$DB" --stop-after-init)
  [ -n "$to_update" ] && args+=(-u "$to_update")
  [ -n "$to_install" ] && args+=(-i "$to_install")
  # shellcheck disable=SC2086
  as_odoo "$ODOO_BIN" "${args[@]}" $(no_http_flag) > "$LOG_DIR/upgrade_$TS.log" 2>&1 || true
  grep -E " (ERROR|CRITICAL|WARNING) .*pharma|Traceback|Modules loaded|migrat|pharma_demo_data: seed|modules loaded in" "$LOG_DIR/upgrade_$TS.log" | tail -25 || true
  grep -qE " (ERROR|CRITICAL) " "$LOG_DIR/upgrade_$TS.log" && die "upgrade log has errors: $LOG_DIR/upgrade_$TS.log (DB dump kept for rollback)"
  grep -q "Modules loaded" "$LOG_DIR/upgrade_$TS.log" || die "upgrade did not reach 'Modules loaded': $LOG_DIR/upgrade_$TS.log"
  if systemctl is-active --quiet $UNIT.service; then
    say "restart $UNIT only (new code + assets)"
    systemctl restart $UNIT.service; sleep 6
    printf '  health: '; curl -sS -o /dev/null -w '%{http_code}\n' --max-time 30 "http://127.0.0.1:$HTTP_PORT/web/health" || true
  fi
  cmd_verify
  echo "rollback of this upgrade: systemctl stop $UNIT; sudo -u postgres dropdb $DB; sudo -u postgres createdb -O $ODOO_USER $DB; sudo -u postgres pg_restore -d $DB $BACKUP_DIR/${DB}_pre_upgrade_$TS.dump; systemctl start $UNIT"
}

cmd_demo_passwords() {
  guards; render_conf "$STAGE_CONF" cli
  say "one password for the four DEMO users (typed twice, never echoed, never stored)"
  local pw pw2 f
  read -r -s -p "demo users password: " pw; echo
  read -r -s -p "again: " pw2; echo
  [ -n "$pw" ] && [ "$pw" = "$pw2" ] || die "passwords empty or do not match"
  f="$(mktemp "$STAGE_DIR/.pw.XXXXXX")"; chmod 600 "$f"; chown "$ODOO_USER" "$f"; printf '%s' "$pw" > "$f"
  as_odoo "$ODOO_BIN" shell -c "$STAGE_CONF" -d "$DB" $(no_http_flag) 2>/dev/null <<PY
pw = open("$f").read()
print("  password set for:", ", ".join(env["pharma.demo.seed"].set_demo_passwords(pw)))
env.cr.commit()
PY
  shred -u "$f" 2>/dev/null || rm -f "$f"
}

cmd_neutralize() {
  guards; render_conf "$STAGE_CONF" cli
  say "neutralize $DB (standard Odoo: banner on every page, outgoing mail / crons / payment providers off). Reversible."
  as_odoo "$ODOO_BIN" neutralize -c "$STAGE_CONF" -d "$DB" 2>&1 | grep -vE "^\s*$" | tail -15
  sudo -u postgres psql -d "$DB" -tAc "select '  database.is_neutralized = '||value from ir_config_parameter where key='database.is_neutralized'"
  sudo -u postgres psql -d "$DB" -tAc "select '  pharma.mode = '||value from ir_config_parameter where key='pharma.mode'"
  sudo -u postgres psql -d "$DB" -tAc "select '  active crons = '||count(*) from ir_cron where active"
  sudo -u postgres psql -d "$DB" -tAc "select '  active outgoing mail server: '||name||' -> '||smtp_host||':'||smtp_port from ir_mail_server where active"
  sudo -u postgres psql -d "$DB" -tAc "select '  active cron: '||cron_name from ir_cron where active"
  if systemctl is-active --quiet $UNIT.service; then
    say "restart $UNIT only, so its workers drop cached parameters"
    systemctl restart $UNIT.service; sleep 5
    printf '  health: '; curl -sS -o /dev/null -w '%{http_code}\n' --max-time 20 "http://127.0.0.1:$HTTP_PORT/web/health" || true
  fi
}

cmd_service_remove() {
  say "rollback: stop + disable $UNIT, remove unit and conf (database untouched)"
  systemctl disable --now $UNIT.service 2>/dev/null || true
  rm -f /etc/systemd/system/$UNIT.service "$SVC_CONF"
  systemctl daemon-reload; echo "done"
}

smoke_common() {   # $1 = base URL, $2 = Host header
  local base="$1" host="$2"
  say "HTTP: $base/web/login  (Host: $host)"
  curl -sS -o /dev/null -w "  status=%{http_code}\n" --max-time 20 -H "Host: $host" "$base/web/login" || echo "  (curl failed)"
  say "public site: / (demo home), /shop, DEMO ribbon"
  for path in / /pharma /shop; do
    curl -sS -o /dev/null -w "  $path -> %{http_code}\n" --max-time 30 -L -H "Host: $host" "$base$path" || echo "  $path (curl failed)"
  done
  curl -sS --max-time 30 -L -H "Host: $host" "$base/shop" | grep -q "DEMO ENVIRONMENT" && echo "  DEMO ribbon on /shop: YES" || echo "  DEMO ribbon on /shop: NOT FOUND"
  curl -sS --max-time 30 -L -H "Host: $host" "$base/shop" | grep -oE "(Green Leaf Infusion|Golden Chai Blend|Rose Petal Tea|Lavender Evening Infusion|Warm Spice Mix)" | sort -u | sed 's/^/  shop lists: /'

  say "XML-RPC as admin (optional: type the admin password, or just press Enter to skip the login check)"
  local login; login="$(admin_login)"; echo "  admin login on $DB: $login"
  local pw; read -r -s -p "password for $login [Enter = skip]: " pw; echo
  if [ -z "$pw" ]; then echo "  skipped (verify the login in the browser later)"; else
  PHARMA_PW="$pw" PHARMA_LOGIN="$login" python3 - "$base" "$host" "$DB" <<'PY' || echo "  (login check failed — see /var/log/odoo/odoo-pharma.log; verify in the browser)"
import json, os, sys, urllib.request, http.cookiejar
base, host, db = sys.argv[1:]; pw = os.environ["PHARMA_PW"]; login = os.environ["PHARMA_LOGIN"]
cj = http.cookiejar.CookieJar(); opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def rpc(path, params):
    body = json.dumps({"jsonrpc": "2.0", "method": "call", "params": params, "id": 1}).encode()
    req = urllib.request.Request(base + path, data=body, headers={"Host": host, "Content-Type": "application/json"})
    with opener.open(req, timeout=60) as r: out = json.loads(r.read())
    if "error" in out: raise SystemExit("  RPC error: " + out["error"].get("data", {}).get("message", out["error"].get("message")))
    return out["result"]
info = rpc("/web/session/authenticate", {"db": db, "login": login, "password": pw})
print(f"  login as {login}:", f"OK uid={info['uid']}" if info.get("uid") else "FAILED")
if not info.get("uid"): sys.exit(1)
print("  session db:", info.get("db"), "| company:", info.get("user_companies", {}).get("current_company"))
root = rpc("/web/dataset/call_kw", {"model": "ir.model.data", "method": "search_read",
                                    "args": [[["module", "=", "pharma_core"], ["name", "=", "menu_pharma_root"]]], "kwargs": {"fields": ["res_id"]}})
menus = rpc("/web/dataset/call_kw", {"model": "ir.ui.menu", "method": "search_read", "args": [[["id", "child_of", root[0]["res_id"]]]],
                                     "kwargs": {"fields": ["complete_name"]}})
print("  Pharma menus reachable through the web session: %d" % len(menus))
PY
  fi
  say "menus / mode / DEMO data as admin, and: production mode must refuse DEMO rules (odoo shell, transaction ROLLED BACK, DB unchanged)"
  render_conf "$STAGE_CONF" cli
  local err="$LOG_DIR/smoke_shell_$TS.err"
  as_odoo "$ODOO_BIN" shell -c "$STAGE_CONF" -d "$DB" $(no_http_flag) 2>"$err" <<'PY' || { echo "  odoo shell step FAILED — stderr:"; tail -n 25 "$err"; }
from datetime import date
admin = env.ref("base.user_admin")
P = env["ir.config_parameter"].sudo()
print("  company:", env.company.name)
print("  pharma.mode:", P.get_param("pharma.mode"))
print("  neutralized:", P.get_param("database.is_neutralized"))
Menu = env["ir.ui.menu"]
root = env.ref("pharma_core.menu_pharma_root")
visible = set(Menu.with_user(admin)._visible_menu_ids())
pharma = Menu.sudo().search([("id", "child_of", root.id)])
shown = sorted(m.complete_name for m in pharma if m.id in visible)
print("  Pharma menus visible to admin (%d of %d):" % (len(shown), len(pharma)))
for name in shown: print("    -", name)
want = {"Pharma/Tax Centre", "Pharma/Reconciliation", "Pharma/Reconciliation/Exception Queue"}
print("  required menus present:", "YES" if want <= set(shown) else f"MISSING {sorted(want - set(shown))}")
for model in ("pharma.tax.rule", "pharma.tax.event", "pharma.recon.run", "pharma.recon.exception", "pharma.partner.stock.line", "pharma.raw.event"):
    M = env[model].sudo(); print(f"  {model}: total={M.search_count([])} demo={M.search_count([('is_demo', '=', True)])}")
P = env["ir.config_parameter"].sudo()
before = P.get_param("pharma.mode")
P.set_param("pharma.mode", "production")
p = env["product.product"].search([("default_code", "=", "DEMO-SKU-A")], limit=1)
res = env["pharma.tax.rule"].resolve(p, date(2026, 11, 3), 1000.0, "SALES_TAX_OUTPUT")
print("  in production mode:", res["resolution"], "|", res["reason"])
assert res["resolution"] != "resolved" and "DEMO-only" in res["reason"], "DEMO rule was NOT refused"
env.cr.rollback()
env.cr.execute("select value from ir_config_parameter where key='pharma.mode'")
after = env.cr.fetchone()[0]
print(f"  rolled back; pharma.mode in the database (SQL, not cache): {after} (was {before})")
assert after == before == "demo", "pharma.mode did not come back to demo after rollback"
PY
}

case "${1:-}" in
  preflight)      guards; preflight ;;
  backup)         guards; cmd_backup ;;
  install)        cmd_install ;;
  verify)         guards; cmd_verify ;;
  admin-login)    cmd_admin_login "${2:-}" ;;
  test)           cmd_test ;;
  service)        cmd_service ;;
  upgrade)        cmd_upgrade ;;
  demo-passwords) cmd_demo_passwords ;;
  neutralize)     cmd_neutralize ;;
  service-remove) cmd_service_remove ;;
  smoke-local)    guards; smoke_common "http://127.0.0.1:$HTTP_PORT" "$DOMAIN" ;;
  smoke)          guards; smoke_common "https://$DOMAIN" "$DOMAIN" ;;
  *) sed -n '2,24p' "$0"; exit 2 ;;
esac
