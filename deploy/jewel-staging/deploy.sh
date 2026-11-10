#!/usr/bin/env bash
#
# Deploy the Mumtaz Jewel staging/demo stack for jewel.mumtaz.digital.
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
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
PROJECT="mumtaz-jewel-staging"
MODULES="mumtaz_jewellery,mumtaz_jewellery_vip,mumtaz_jewellery_owner"
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
for arg in "$@"; do
  case "$arg" in
    --no-pull) DO_PULL=0 ;;
    --install) DO_INSTALL=1 ;;
    --seed)    DO_SEED=1 ;;
    *) red "Unknown option: $arg"; exit 2 ;;
  esac
done

# -- guard rails -------------------------------------------------------------
if [ ! -f "$HERE/.env" ]; then
  red "No $HERE/.env. Copy .env.example to .env and set the passwords."
  exit 2
fi
# shellcheck disable=SC1091
set -a; . "$HERE/.env"; set +a

for required in POSTGRES_USER POSTGRES_PASSWORD ADMIN_PASSWORD JEWEL_BRANCH; do
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
if [ "$BRANCH" = "main" ]; then
  red "Refusing to run on 'main': that branch auto-deploys to production."
  red "This script deploys the Jewel staging host only."
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
  else
    red "Cannot write $LANDING_DIR, so the site was NOT updated."
    red "nginx is still serving the previous copy. As root, run:"
    red "  rsync -a --delete $LANDING_SRC/. $LANDING_DIR/"
  fi
fi

# -- 2. render odoo.conf from the template ----------------------------------
# The template is in git and holds no secret; the rendered file is gitignored.
info "Rendering odoo.rendered.conf"
sed -e "s|__ADMIN_PASSWORD__|${ADMIN_PASSWORD}|" \
    -e "s|__POSTGRES_USER__|${POSTGRES_USER}|" \
    -e "s|__POSTGRES_PASSWORD__|${POSTGRES_PASSWORD}|" \
    "$HERE/odoo.conf.tmpl" > "$HERE/odoo.rendered.conf"
chmod 600 "$HERE/odoo.rendered.conf"

cd "$HERE"
compose() { docker compose -p "$PROJECT" "$@"; }

# -- 3. bring the stack up --------------------------------------------------
if [ "$DO_INSTALL" = "1" ]; then
  info "First run: installing $MODULES into a fresh database '$DEMO_DB'"
  compose up -d db
  compose run --rm --no-deps odoo odoo \
    -c /etc/odoo/odoo.conf -d "$DEMO_DB" -i "$MODULES" \
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
