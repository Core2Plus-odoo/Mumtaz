#!/usr/bin/env bash
#
# Deploy the Jawhar staging/demo stack for jewel.mumtaz.digital.
#
# This script deploys STAGING ONLY. By design it:
#   * refuses to run from `main`, which auto-deploys to the production VPS;
#   * refuses any branch but the one named in .env (JEWEL_BRANCH);
#   * never calls c2p-delivery-system/deploy/update.sh;
#   * never touches docker-compose.production.yml, the shared Postgres, the
#     CRM database, or nginx config for any other site;
#   * only ever acts on the compose project `mumtaz-jewel-staging`.
#
# The first run on the VPS is an APPROVAL gate
# (docs/mumtaz-jewel/CLAUDE_CODE_HANDOFF.md, section 3). Nothing in this
# directory has been run on any server.
#
# Usage, from the branch checkout (NOT /opt/mumtaz, which is the production
# checkout that tracks main):
#   deploy/jewel-staging/deploy.sh                 # pull, render, restart
#   deploy/jewel-staging/deploy.sh --no-pull       # restart only
#   deploy/jewel-staging/deploy.sh --install       # first run: install addons
#   deploy/jewel-staging/deploy.sh --seed          # add the DEMO data
#   deploy/jewel-staging/deploy.sh --modules       # install modules newly
#                                                  # listed in MODULES into
#                                                  # the existing database
#   deploy/jewel-staging/deploy.sh --upgrade       # apply code changes to the
#                                                  # installed Jawhar modules
#                                                  # (new fields, views, data)
#   deploy/jewel-staging/deploy.sh --site-only     # landing page + interface
#
# Every run also builds the Jawhar interface (apps/jawhar-web) in a Node
# container and publishes it to /opt/mumtaz/jewel-app; SKIP_WEB=1 skips it.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
PROJECT="mumtaz-jewel-staging"
MODULES="mumtaz_jewellery,mumtaz_jewellery_vip,mumtaz_jewellery_owner,mumtaz_jewellery_sale,mumtaz_jewellery_crm,mumtaz_jewellery_ai,mumtaz_jewellery_kiosk,mumtaz_jewellery_api,mumtaz_jewellery_outreach,mumtaz_jewellery_aml,mumtaz_jewellery_stores"
SEED_MODULE="mumtaz_jewellery_demo"
DEMO_DB="${DEMO_DB:-jewel_demo}"
LANDING_SRC="$REPO_ROOT/website/jewel"
LANDING_DIR="${JEWEL_LANDING_DIR:-/opt/mumtaz/jewel-landing}"

red()  { printf '\033[31m%s\033[0m\n' "$*" >&2; }
info() { printf '\033[36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[32m%s\033[0m\n' "$*"; }

DO_PULL=1
DO_INSTALL=0
DO_SEED=0
DO_MODULES=0
DO_UPGRADE=0
SITE_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --no-pull)   DO_PULL=0 ;;
    --install)   DO_INSTALL=1 ;;
    --seed)      DO_SEED=1 ;;
    --site-only) SITE_ONLY=1 ;;
    --modules)   DO_MODULES=1 ;;
    --upgrade)   DO_UPGRADE=1 ;;
    *) red "Unknown option: $arg"; exit 2 ;;
  esac
done

# -- guard rails -------------------------------------------------------------
# Whether JEWEL_BRANCH was set on purpose (environment or .env), as opposed to
# falling back to whatever is checked out. The main guard below turns on this.
JEWEL_BRANCH_EXPLICIT="${JEWEL_BRANCH:-}"
# Publishing the static site touches no database and needs no password, so
# --site-only skips the .env requirement entirely. Only the Odoo stack needs
# credentials; making a page update wait on them was the wrong coupling.
if [ ! -f "$HERE/.env" ]; then
  if [ "$SITE_ONLY" = "1" ]; then
    info "No .env — fine for --site-only; the Odoo stack is not touched."
    JEWEL_BRANCH="${JEWEL_BRANCH:-$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)}"
  else
    red "No $HERE/.env. Copy .env.example to .env and set the passwords."
    red "To publish only the landing page and prototype, which need no"
    red "database at all, re-run with --site-only."
    exit 2
  fi
fi
if [ -f "$HERE/.env" ]; then
# shellcheck disable=SC1091
  set -a; . "$HERE/.env"; set +a
  JEWEL_BRANCH_EXPLICIT="${JEWEL_BRANCH:-}"
fi

REQUIRED_VARS="POSTGRES_USER POSTGRES_PASSWORD ADMIN_PASSWORD JEWEL_BRANCH"
# ADMIN_PASSWORD guards the database manager. It does NOT set the admin
# user's login, so a fresh database would accept admin/admin until this is
# set. On a host reachable from the internet that is not acceptable.
[ "$DO_INSTALL" = "1" ] && REQUIRED_VARS="$REQUIRED_VARS DEMO_LOGIN_PASSWORD"
[ "$SITE_ONLY" = "1" ] && REQUIRED_VARS="JEWEL_BRANCH"
for required in $REQUIRED_VARS; do
  if [ -z "${!required:-}" ]; then
    red "$required is not set in .env"; exit 2
  fi
  case "${!required}" in
    CHANGE_ME*) red "$required still holds the placeholder from .env.example."; exit 2 ;;
  esac
done
: "${JEWEL_HTTP_PORT:=8072}"
: "${JEWEL_POLL_PORT:=8073}"

BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"
# Earlier versions refused 'main' outright, on the stated belief that main
# auto-deploys to production. It does not: .github/workflows/deploy-production
# is workflow_dispatch (manual) and deploy-staging triggers on 'develop'. The
# guard that actually matters is the one below, on the production checkout.
# Running main here is allowed, but only when .env says so deliberately, so it
# can never happen by leaving a checkout on main by accident.
if [ "$BRANCH" = "main" ] && [ "$JEWEL_BRANCH_EXPLICIT" != "main" ]; then
  red "This checkout is on 'main' but .env does not name 'main' as the"
  red "branch this host serves, so refusing rather than guessing."
  red "Either set JEWEL_BRANCH=main deliberately, or track a staging branch:"
  red "  git checkout -B jewel-staging origin/main"
  exit 2
fi
if [ "$BRANCH" != "$JEWEL_BRANCH" ]; then
  red "On branch '$BRANCH' but .env allows only '$JEWEL_BRANCH'."
  red "Check out that branch, or change JEWEL_BRANCH deliberately."
  exit 2
fi
if [ "$REPO_ROOT" = "/opt/mumtaz" ]; then
  red "/opt/mumtaz is the production checkout that tracks main."
  red "Run this from a separate staging checkout of the branch."
  exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
  red "docker is not installed or not on PATH."; exit 2
fi

info "Repo:    $REPO_ROOT"
info "Branch:  $BRANCH"
info "Project: $PROJECT  (ports 127.0.0.1:$JEWEL_HTTP_PORT and :$JEWEL_POLL_PORT)"

# -- 1. pull the staging branch only ----------------------------------------
if [ "$DO_PULL" = "1" ]; then
  info "Fetching origin/$JEWEL_BRANCH"
  attempt=1; delay=2
  until git -C "$REPO_ROOT" fetch origin "$JEWEL_BRANCH"; do
    if [ "$attempt" -ge 4 ]; then red "fetch failed after $attempt attempts"; exit 1; fi
    sleep "$delay"; delay=$((delay * 2)); attempt=$((attempt + 1))
  done
  git -C "$REPO_ROOT" merge --ff-only "origin/$JEWEL_BRANCH"
  ok "Checkout is at $(git -C "$REPO_ROOT" rev-parse --short HEAD)"
fi

# -- 1b. re-publish the static site -----------------------------------------
# finish.sh copies website/jewel once, at first bring-up. Without this step a
# pull updates the checkout and nginx keeps serving the old copy, which is the
# "a plain copy goes stale silently" trap the repo CLAUDE.md warns about: the
# landing page and the prototype would never change. --delete matters too,
# because files removed from the repo must disappear from the web root.
if [ -d "$LANDING_SRC" ]; then
  if [ -w "$(dirname "$LANDING_DIR")" ] || [ -w "$LANDING_DIR" ]; then
    info "Publishing website/jewel to $LANDING_DIR"
    mkdir -p "$LANDING_DIR"
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --delete "$LANDING_SRC/." "$LANDING_DIR/"
    else
      # No rsync: rebuild the directory so removed files do not linger.
      tmp="$(mktemp -d "${LANDING_DIR%/}.new.XXXXXX")"
      cp -r "$LANDING_SRC/." "$tmp/"
      old="$(mktemp -d "${LANDING_DIR%/}.old.XXXXXX")"
      mv "$LANDING_DIR" "$old/prev" 2>/dev/null || true
      mv "$tmp" "$LANDING_DIR"
      rm -rf "$old"
    fi
    ok "Site published at $(date -u +%H:%M:%SZ) — hard-refresh the browser"
    published=1

    # Publishing is not the same as serving. nginx answers 200 with the
    # landing page for any path it does not know, so a page that was never
    # published is indistinguishable from one that was until you compare
    # bytes. Verify, and say plainly if it could not be done.
    verify="$(dirname "${BASH_SOURCE[0]}")/verify_site.sh"
    if [ "${SKIP_VERIFY:-0}" = "1" ]; then
      info "SKIP_VERIFY=1, not checking what is actually served."
    elif [ -x "$verify" ] || [ -f "$verify" ]; then
      info "Verifying what is actually served"
      if SITE_ROOT="$LANDING_DIR" SITE_SRC="$LANDING_SRC" bash "$verify"; then
        ok "Verified: every expected page is really published."
      else
        red "The files were copied, but the site does NOT serve them all."
        red "See the failures above. Nothing was rolled back."
        exit 1
      fi
    fi
  else
    red "Cannot write $LANDING_DIR, so the site was NOT updated."
    red "nginx is still serving the previous copy. As root, run:"
    red "  rsync -a --delete $LANDING_SRC/. $LANDING_DIR/"
  fi
fi

# -- 1b. the Jawhar interface --------------------------------------------------
# Built here, not committed: a built bundle in git goes stale the moment the
# source changes. The host has no Node, so the build runs in a container
# against the checkout; only dist/ is published. Same rebuild-the-directory
# publish as the landing page, so removed files do not linger.
WEB_SRC="$REPO_ROOT/apps/jawhar-web"
WEB_DIR="${JEWEL_APP_DIR:-/opt/mumtaz/jewel-app}"
if [ "${SKIP_WEB:-0}" = "1" ]; then
  info "SKIP_WEB=1, not building the interface."
elif [ -f "$WEB_SRC/package.json" ]; then
  info "Building the Jawhar interface (apps/jawhar-web) in a Node container"
  if ! docker run --rm -v "$WEB_SRC:/w" -w /w node:22-alpine \
        sh -c 'npm ci --no-audit --no-fund --loglevel=error && npx vite build' ; then
    red "The interface build failed; nothing was published to $WEB_DIR."
    exit 1
  fi
  [ -s "$WEB_SRC/dist/index.html" ] || { red "Build produced no dist/index.html"; exit 1; }
  if mkdir -p "$(dirname "$WEB_DIR")" 2>/dev/null && [ -w "$(dirname "$WEB_DIR")" ]; then
    tmp="$(mktemp -d "${WEB_DIR%/}.new.XXXXXX")"
    cp -r "$WEB_SRC/dist/." "$tmp/"
    chmod -R a+rX "$tmp"
    old="$(mktemp -d "${WEB_DIR%/}.old.XXXXXX")"
    mv "$WEB_DIR" "$old/prev" 2>/dev/null || true
    mv "$tmp" "$WEB_DIR"
    rm -rf "$old"
    ok "Interface published to $WEB_DIR at $(date -u +%H:%M:%SZ)"
    # Served, not just copied: compare bytes, because the catch-all answers
    # 200 with the landing page for any unknown path.
    site="${JEWEL_SITE_URL:-https://jewel.mumtaz.digital}"
    if command -v curl >/dev/null 2>&1; then
      served="$(mktemp)"
      if [ -n "${JEWEL_SITE_AUTH:-}" ]; then
        code="$(curl -sS --max-time 20 -o "$served" -w '%{http_code}' -u "$JEWEL_SITE_AUTH" "${site%/}/app/" 2>/dev/null || echo 000)"
      else
        code="$(curl -sS --max-time 20 -o "$served" -w '%{http_code}' "${site%/}/app/" 2>/dev/null || echo 000)"
      fi
      if cmp -s "$served" "$WEB_SRC/dist/index.html"; then
        ok "Verified: ${site%/}/app/ serves the build just published."
      elif [ "$code" = "401" ]; then
        info "${site%/}/app/ is password-protected (401); cannot compare bytes without"
        info "JEWEL_SITE_AUTH=demo:<password> in .env. The files are in place."
      else
        red "${site%/}/app/ answered $code but NOT with the build just published."
        red "Is the /app/ location in nginx? See deploy/jewel-staging/install_nginx_conf.sh."
      fi
      rm -f "$served"
    fi
  else
    red "Cannot write $WEB_DIR; the interface was built but NOT published."
  fi
else
  info "No apps/jawhar-web in this checkout; interface not built."
fi

if [ "$SITE_ONLY" = "1" ]; then
  if [ "${published:-0}" = "1" ]; then
    ok "--site-only: landing page and prototype published. Odoo untouched."
    exit 0
  fi
  red "--site-only: nothing was published. See the error above."
  exit 1
fi

# -- 2. render odoo.conf from the template ----------------------------------
# The template is in git and holds no secret; the rendered file is gitignored.
info "Rendering odoo.rendered.conf"
sed -e "s|__ADMIN_PASSWORD__|${ADMIN_PASSWORD}|" \
    -e "s|__POSTGRES_USER__|${POSTGRES_USER}|" \
    -e "s|__POSTGRES_PASSWORD__|${POSTGRES_PASSWORD}|" \
    "$HERE/odoo.conf.tmpl" > "$HERE/odoo.rendered.conf"
cd "$HERE"
compose() { docker compose -p "$PROJECT" "$@"; }

# The rendered file holds the admin and database passwords, so it must not
# be world-readable -- but a root-owned mode-600 file is unreadable INSIDE
# the container, where Odoo runs as its own unprivileged user. The first
# bring-up on the VPS died exactly there: the image's wait-for-psql.py got
# "Permission denied" on /etc/odoo/odoo.conf and then "No section: options".
#
# So ask the image which uid it runs as, and give that uid -- and only that
# uid -- read access. Root on the host can chown to any uid, and the bind
# mount carries the numeric owner through unchanged.
ODOO_UID="$(compose run --rm --no-deps --entrypoint id odoo -u 2>/dev/null | tr -d '[:space:]')"
if [ -z "$ODOO_UID" ] || ! [ "$ODOO_UID" -eq "$ODOO_UID" ] 2>/dev/null; then
  red "Could not learn the uid Odoo runs as inside the image (got '$ODOO_UID')."
  red "Without it the rendered config is unreadable in the container."
  exit 1
fi
chown "$ODOO_UID" "$HERE/odoo.rendered.conf"
chmod 400 "$HERE/odoo.rendered.conf"
ok "odoo.rendered.conf readable only by the container's user (uid $ODOO_UID)"

# The addons are bind-mounted read-only, but read-only is not the same as
# readable: a directory created under a restrictive umask (a root shell with
# umask 077, as happened on the VPS) is mode 700, and Odoo -- uid $ODOO_UID in
# the container -- silently skips any module it cannot read. The only trace is
# a WARNING "invalid module names, ignored: ..." buried in Odoo's own log, and
# the seed step then "succeeds" having seeded nothing. So check, as that uid,
# that every module we are about to name can actually be read, and refuse
# loudly if not.
unreadable=""
for mod in $(printf '%s' "$MODULES,$SEED_MODULE" | tr ',' ' '); do
  if ! compose run --rm --no-deps --user "$ODOO_UID" --entrypoint sh odoo \
        -c "test -r /mnt/extra-addons/$mod/__manifest__.py" >/dev/null 2>&1; then
    unreadable="$unreadable $mod"
  fi
done
if [ -n "$unreadable" ]; then
  red "These modules are NOT readable by uid $ODOO_UID inside the container:$unreadable"
  red "Odoo would skip them silently. Fix the permissions on the host, e.g.:"
  red "  chmod -R a+rX $(cd "$HERE/../.." && pwd)/addons"
  red "and check your shell's umask (a root shell with umask 077 creates 700 dirs)."
  exit 1
fi
ok "all $(printf '%s\n' "$MODULES,$SEED_MODULE" | tr ',' '\n' | wc -l | tr -d ' ') modules readable by uid $ODOO_UID"

# -- 3. bring the stack up --------------------------------------------------
if [ "$DO_INSTALL" = "1" ]; then
  info "First run: installing $MODULES into a fresh database '$DEMO_DB'"
  compose up -d db
  compose run --rm --no-deps odoo odoo \
    -c /etc/odoo/odoo.conf -d "$DEMO_DB" -i "$MODULES" \
    --without-demo=True --no-http --stop-after-init
fi

if [ "$DO_INSTALL" = "1" ]; then
  info "Setting the admin user's login password on '$DEMO_DB'"
  # Look the user up by login rather than by xmlid, so this does not depend on
  # an internal name. Require the sentinel in the output: odoo shell can exit 0
  # even when the snippet raised, and a password we only assumed was set is
  # worse than one we know failed.
  set_pw_out="$(printf '%s\n' \
      "import os" \
      "u = env['res.users'].search([('login', '=', 'admin')], limit=1)" \
      "assert u, 'no user with login admin'" \
      "u.write({'password': os.environ['DEMO_LOGIN_PASSWORD']})" \
      "env.cr.commit()" \
      "print('JEWEL_PW_SET_OK')" \
    | compose run --rm --no-deps -e DEMO_LOGIN_PASSWORD="$DEMO_LOGIN_PASSWORD" \
        odoo odoo shell -c /etc/odoo/odoo.conf -d "$DEMO_DB" --no-http 2>&1 || true)"

  if printf '%s' "$set_pw_out" | grep -q JEWEL_PW_SET_OK; then
    ok "admin login password set from DEMO_LOGIN_PASSWORD"
  else
    red "FAILED to set the admin login password."
    red "The database may still accept admin/admin. Do NOT expose it until"
    red "this is fixed. Last output follows:"
    printf '%s\n' "$set_pw_out" | tail -15 >&2
    red "To fix by hand:"
    red "  docker compose -p $PROJECT run --rm --no-deps odoo \\"
    red "    odoo shell -c /etc/odoo/odoo.conf -d $DEMO_DB --no-http"
    red "  >>> u = env['res.users'].search([('login','=','admin')], limit=1)"
    red "  >>> u.write({'password': '<your password>'}); env.cr.commit()"
    exit 1
  fi
fi

if [ "$DO_MODULES" = "1" ] && [ "$DO_INSTALL" != "1" ]; then
  # `-i` on a module that is already installed does nothing, so this is safe
  # to run on every deploy that adds a module to MODULES.
  info "Installing modules missing from '$DEMO_DB': $MODULES"
  compose up -d db
  compose run --rm --no-deps odoo odoo \
    -c /etc/odoo/odoo.conf -d "$DEMO_DB" -i "$MODULES" \
    --without-demo=True --no-http --stop-after-init
fi

if [ "$DO_UPGRADE" = "1" ] && [ "$DO_INSTALL" != "1" ]; then
  # A pull that changes a module's fields, views or data needs `-u`; a
  # restart alone leaves the database on the old schema. Idempotent: an
  # upgrade of an unchanged module rewrites nothing. The seed module is not
  # upgraded -- its hook runs once by design and an upgrade must not re-seed.
  info "Upgrading the installed Jawhar modules in '$DEMO_DB': $MODULES"
  compose up -d db
  compose run --rm --no-deps odoo odoo \
    -c /etc/odoo/odoo.conf -d "$DEMO_DB" -u "$MODULES" \
    --without-demo=True --no-http --stop-after-init
fi

if [ "$DO_SEED" = "1" ]; then
  info "Seeding synthetic DEMO data into '$DEMO_DB'"
  compose run --rm --no-deps odoo odoo \
    -c /etc/odoo/odoo.conf -d "$DEMO_DB" -i "$SEED_MODULE" \
    --without-demo=True --no-http --stop-after-init
fi

info "Starting the stack"
compose up -d
compose ps

# -- 4. health check --------------------------------------------------------
info "Waiting for Odoo to answer on 127.0.0.1:$JEWEL_HTTP_PORT"
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null "http://127.0.0.1:${JEWEL_HTTP_PORT}/web/health"; then
    ok "Jewel staging is up on 127.0.0.1:${JEWEL_HTTP_PORT}"
    exit 0
  fi
  sleep 5
done
red "Odoo did not answer within 150s. Recent logs:"
compose logs --tail=40 odoo
exit 1
