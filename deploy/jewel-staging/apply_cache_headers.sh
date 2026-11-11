#!/usr/bin/env bash
#
# Make nginx actually send the Jawhar response headers.
#
# This script exists because of a trap that `nginx -t` cannot catch, and that
# three earlier attempts at this walked straight into.
#
# nginx does NOT merge `add_header` across configuration levels. A level
# inherits the parent's add_header directives ONLY IF it defines none of its
# own. So a single `add_header` inside a `location` silently discards every
# `add_header` from the enclosing `server` block, for every request that
# location handles. The configuration stays valid, the reload succeeds, and
# the headers are simply absent.
#
# On jewel.mumtaz.digital that was dropping four headers from every HTML page
# -- a Cache-Control, and three security headers that had never once been
# sent:
#
#     X-Content-Type-Options, X-Frame-Options, Referrer-Policy
#
# because `location = /` and `location /` each carried one
# `add_header X-Robots-Tag`.
#
# The fix is to give each level its own copy: the server-level headers go
# into a snippet, and the snippet is included in the locations that need it.
#
# Safety: backs up outside nginx's include path, runs `nginx -t` BEFORE
# reloading, restores and re-tests if the test fails, and finishes by
# FETCHING THE SITE to confirm each header is really being sent. A reload
# that succeeds while the headers stay missing is a failure and is reported
# as one -- that is how the original bug was caught.
#
# Usage (as root, on the VPS):
#   deploy/jewel-staging/apply_cache_headers.sh
#   DRY_RUN=1 deploy/jewel-staging/apply_cache_headers.sh    # show the plan
#   SITE_CONF=/etc/nginx/sites-enabled/x.conf  ...           # skip discovery
set -uo pipefail

SERVER_NAME="${SERVER_NAME:-jewel.mumtaz.digital}"
SITE_CONF="${SITE_CONF:-}"
MAP_DEST="${MAP_DEST:-/etc/nginx/conf.d/jewel-cache-map.conf}"
SNIPPET_DIR="${SNIPPET_DIR:-/etc/nginx/snippets}"
SNIPPET_NAME="jewel-headers.conf"
INCLUDE_PATH="snippets/$SNIPPET_NAME"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/jewel-nginx}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAP_SRC="$HERE/nginx-cache-headers.conf"
FIXER="$HERE/nginx_header_fix.py"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
green(){ printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '\033[36m==> %s\033[0m\n' "$*"; }

[ "$(id -u)" = "0" ] || { red "Run as root: this edits /etc/nginx."; exit 2; }
command -v nginx   >/dev/null || { red "nginx not found.";   exit 2; }
command -v python3 >/dev/null || { red "python3 not found."; exit 2; }
[ -f "$MAP_SRC" ] || { red "Missing $MAP_SRC"; exit 2; }
[ -f "$FIXER" ]   || { red "Missing $FIXER";   exit 2; }

# -- 1. which file does nginx actually serve this host from? -----------------
# `nginx -T` first: it dumps the loaded configuration with includes resolved
# and names each directive's source file. A filename search can find a config
# nginx never loaded -- this host has two candidates and only one is enabled.
# The filesystem fallback uses -R, not -r: -r does NOT follow symlinks, and a
# Debian nginx fills sites-enabled with symlinks.
if [ -z "$SITE_CONF" ]; then
  SITE_CONF="$(nginx -T 2>/dev/null | awk -v n="$SERVER_NAME" '
      /^# configuration file / { f = $4; sub(/:$/, "", f) }
      $0 ~ /server_name/ && index($0, n) { print f; exit }')"
  [ -n "$SITE_CONF" ] && info "Found via nginx -T (the loaded configuration)"
fi
if [ -z "$SITE_CONF" ]; then
  for dir in /etc/nginx/sites-enabled /etc/nginx/conf.d /etc/nginx; do
    SITE_CONF="$(grep -RlE "server_name[[:space:]]+[^;]*${SERVER_NAME//./\\.}" \
        "$dir" 2>/dev/null | grep -v '\.bak\.' | head -1)"
    [ -n "$SITE_CONF" ] && { info "Found by searching $dir"; break; }
  done
fi
[ -n "$SITE_CONF" ] && [ -f "$SITE_CONF" ] || {
  red "Could not find the server block for $SERVER_NAME."
  red "Find the file nginx loaded with:"
  red "  nginx -T 2>/dev/null | grep -B40 'server_name.*$SERVER_NAME' | grep 'configuration file'"
  exit 2; }

nginx -T 2>/dev/null | grep -q "^# configuration file $SITE_CONF:" || {
  red "nginx has not loaded $SITE_CONF -- editing it would change nothing."
  red "Check which site is enabled:  ls -l /etc/nginx/sites-enabled/"
  exit 2; }
info "Site config: $SITE_CONF"

# -- 2. the plan -------------------------------------------------------------
if ! PLAN="$(python3 "$FIXER" "$SITE_CONF" "$INCLUDE_PATH" --check 2>&1)"; then
  red "Could not read the configuration:"; printf '%s\n' "$PLAN"; exit 1
fi
printf '%s\n' "$PLAN"
TARGETS="$(printf '%s' "$PLAN" | sed -n 's/.*TARGETS=\([0-9]*\).*/\1/p')"

if [ "${DRY_RUN:-0}" = "1" ]; then
  info "DRY_RUN=1: nothing applied."
  exit 0
fi

# -- 3. the content-type map (http context, no locations, cannot collide) ----
install -m 0644 "$MAP_SRC" "$MAP_DEST"
green "Installed $MAP_DEST"

# -- 4. edit, with a backup nginx will not load ------------------------------
mkdir -p "$BACKUP_DIR" "$SNIPPET_DIR"
BACKUP="$BACKUP_DIR/$(basename "$SITE_CONF").bak.$(date +%Y%m%d%H%M%S)"
cp -pL "$SITE_CONF" "$BACKUP"
info "Backed up to $BACKUP"

SNIPPET_TMP="$(mktemp)"
CONF_TMP="$(mktemp)"
trap 'rm -f "$SNIPPET_TMP" "$CONF_TMP"' EXIT

if [ "${TARGETS:-0}" = "0" ]; then
  info "Every location already includes the snippet; refreshing it only."
  python3 "$FIXER" "$SITE_CONF" "$INCLUDE_PATH" > "$CONF_TMP" 2>"$SNIPPET_TMP"
else
  python3 "$FIXER" "$SITE_CONF" "$INCLUDE_PATH" > "$CONF_TMP" 2>"$SNIPPET_TMP" || {
    red "The rewrite failed; nothing was changed."; exit 1; }
fi
[ -s "$CONF_TMP" ]    || { red "Rewrite produced an empty file; aborting."; exit 1; }
[ -s "$SNIPPET_TMP" ] || { red "No headers to put in the snippet; aborting."; exit 1; }

{ echo "# Written by deploy/jewel-staging/apply_cache_headers.sh."
  echo "# nginx does not merge add_header across levels: a location with any"
  echo "# add_header of its own discards every one from the server block. So"
  echo "# these are included INTO the locations that need them."
  cat "$SNIPPET_TMP"
} > "$SNIPPET_DIR/$SNIPPET_NAME"
chmod 0644 "$SNIPPET_DIR/$SNIPPET_NAME"
green "Wrote $SNIPPET_DIR/$SNIPPET_NAME"
sed 's/^/    /' "$SNIPPET_TMP"

# cat, not mv: $SITE_CONF may be a symlink into sites-available and the
# target is what nginx reads. This writes through the link.
cat "$CONF_TMP" > "$SITE_CONF"
green "Updated $SITE_CONF"

# -- 5. test, and roll back if the test fails --------------------------------
info "Testing the configuration"
if nginx -t 2>&1; then
  green "nginx -t passed."
else
  red "nginx -t FAILED. Rolling back."
  cat "$BACKUP" > "$SITE_CONF"
  rm -f "$MAP_DEST" "$SNIPPET_DIR/$SNIPPET_NAME"
  if nginx -t >/dev/null 2>&1; then
    red "Rolled back; the previous configuration is valid and still live."
  else
    red "ROLLBACK DID NOT RESTORE A VALID CONFIG. Do not reload."
    red "Restore by hand from: $BACKUP"
  fi
  exit 1
fi

info "Reloading nginx"
systemctl reload nginx || { red "Reload failed; the old config is still serving."; exit 1; }
green "Reloaded."

# -- 6. prove it, header by header -------------------------------------------
# The whole point. A reload that succeeds while the headers stay missing is
# exactly the bug this script was written to fix, so it is checked, not
# assumed.
sleep 1
HDRS="$(curl -sSI --max-time 20 "https://$SERVER_NAME/" 2>/dev/null)"
missing=0
for h in Cache-Control X-Content-Type-Options X-Frame-Options Referrer-Policy; do
  v="$(printf '%s' "$HDRS" | grep -i "^$h:" | tr -d '\r')"
  if [ -n "$v" ]; then green "  $v"
  else red "  $h MISSING"; missing=$((missing + 1)); fi
done
if [ "$missing" -gt 0 ]; then
  red "$missing header(s) are still not being sent."
  red "The configuration is valid and the site is serving; nothing is broken,"
  red "but the headers did not take. Backup: $BACKUP"
  exit 1
fi
green "Every header is being sent."
