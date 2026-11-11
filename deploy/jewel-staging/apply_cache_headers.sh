#!/usr/bin/env bash
#
# Install the Jewel cache policy into nginx, safely.
#
# Editing a live web server's config by hand is how sites go down, so this
# script refuses to leave a broken config behind:
#
#   * it backs up the server block before touching it
#   * it runs `nginx -t` BEFORE reloading
#   * if the test fails it restores the backup, re-tests, and exits non-zero
#   * it is idempotent: run it twice and the second run changes nothing
#
# It never runs `systemctl reload` unless `nginx -t` passed.
#
# Usage (as root, on the VPS):
#   deploy/jewel-staging/apply_cache_headers.sh                # find the site automatically
#   SITE_CONF=/etc/nginx/sites-enabled/jewel apply_cache_headers.sh
#   DRY_RUN=1 deploy/jewel-staging/apply_cache_headers.sh      # show the change, apply nothing
set -uo pipefail

SERVER_NAME="${SERVER_NAME:-jewel.mumtaz.digital}"
SITE_CONF="${SITE_CONF:-}"
MAP_DEST="${MAP_DEST:-/etc/nginx/conf.d/jewel-cache-map.conf}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAP_SRC="$HERE/nginx-cache-headers.conf"
ADD_LINE='    add_header Cache-Control $jewel_cache always;'
MARKER='$jewel_cache'

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
green(){ printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '\033[36m==> %s\033[0m\n' "$*"; }

[ "$(id -u)" = "0" ] || { red "Run this as root: it edits /etc/nginx."; exit 2; }
command -v nginx >/dev/null 2>&1 || { red "nginx not found."; exit 2; }
[ -f "$MAP_SRC" ] || { red "Missing $MAP_SRC (is the repo checked out?)"; exit 2; }

# -- find the server block ---------------------------------------------------
# Three ways, cheapest first. The first version of this looked only in
# sites-enabled and conf.d and failed on a real host whose config lives
# elsewhere -- a server block can be included from any path.
if [ -z "$SITE_CONF" ]; then
  # 1. the conventional locations
  SITE_CONF="$(grep -rlE "server_name[[:space:]]+[^;]*${SERVER_NAME//./\\.}" \
      /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null | head -1)"
fi
if [ -z "$SITE_CONF" ]; then
  # 2. anywhere under /etc/nginx
  SITE_CONF="$(grep -rlE "server_name[[:space:]]+[^;]*${SERVER_NAME//./\\.}" \
      /etc/nginx 2>/dev/null | grep -v '\.bak\.' | head -1)"
fi
if [ -z "$SITE_CONF" ]; then
  # 3. ask nginx itself. `nginx -T` resolves every include and prints
  #    "# configuration file <path>:" before each file's contents, so it
  #    finds the block wherever it actually lives.
  SITE_CONF="$(nginx -T 2>/dev/null | awk -v name="$SERVER_NAME" '
      /^# configuration file / { f = $4; sub(/:$/, "", f) }
      $0 ~ /server_name/ && index($0, name) { print f; exit }')"
fi
if [ -z "$SITE_CONF" ] || [ ! -f "$SITE_CONF" ]; then
  red "Could not find the server block for $SERVER_NAME."
  red "Find it with:"
  red "  grep -rl '$SERVER_NAME' /etc/nginx/"
  red "then pass it:  SITE_CONF=<that file> $0"
  exit 2
fi
info "Site config: $SITE_CONF"

# -- 1. the map (http context, no locations, cannot collide) -----------------
if [ "${DRY_RUN:-0}" = "1" ]; then
  info "DRY_RUN: would install $MAP_SRC -> $MAP_DEST"
else
  install -m 0644 "$MAP_SRC" "$MAP_DEST"
  green "Installed $MAP_DEST"
fi

# -- 2. one add_header line in the server block ------------------------------
if grep -qF "$MARKER" "$SITE_CONF"; then
  green "add_header already present in $SITE_CONF — nothing to change."
  ALREADY=1
else
  ALREADY=0
  if [ "${DRY_RUN:-0}" = "1" ]; then
    info "DRY_RUN: would insert after the server_name line:"
    printf '%s\n' "$ADD_LINE"
  else
    BACKUP="$SITE_CONF.bak.$(date +%Y%m%d%H%M%S)"
    cp -p "$SITE_CONF" "$BACKUP"
    info "Backed up to $BACKUP"
    # Insert after server_name, but ONLY in the block that actually serves
    # the site. A naive "first server_name wins" lands in the port-80
    # redirect block, where the header is never sent on a real page — tested,
    # and that is exactly what the first version of this script did.
    #
    # So buffer each server block, then require: it names this host, it is
    # not a pure redirect, and it either listens on 443 or has a root.
    awk -v name="$SERVER_NAME" -v line="$ADD_LINE" '
      function flush_block(   i, ok, out) {
        ok = (has_name && !is_redirect && (has_443 || has_root) && !done)
        for (i = 1; i <= n; i++) {
          print buf[i]
          if (ok && buf[i] ~ /server_name/ && index(buf[i], name)) {
            print line
            done = 1
          }
        }
        n = 0; has_name = 0; has_443 = 0; has_root = 0; is_redirect = 0
      }
      /^[[:space:]]*server[[:space:]]*\{/ && depth == 0 { in_block = 1 }
      {
        if (in_block) {
          buf[++n] = $0
          if ($0 ~ /server_name/ && index($0, name)) has_name = 1
          if ($0 ~ /listen[^;]*443/)                 has_443  = 1
          if ($0 ~ /^[[:space:]]*root[[:space:]]/)   has_root = 1
          if ($0 ~ /return[[:space:]]+30[12]/)       is_redirect = 1
        } else {
          print
        }
        depth += gsub(/\{/, "{")
        depth -= gsub(/\}/, "}")
        if (in_block && depth == 0) { flush_block(); in_block = 0 }
      }
      END { if (n) flush_block() }
    ' "$BACKUP" > "$SITE_CONF"
    if ! grep -qF "$MARKER" "$SITE_CONF"; then
      red "Could not place the add_header line; restoring and leaving config untouched."
      cp -p "$BACKUP" "$SITE_CONF"
      exit 1
    fi
    green "Inserted the add_header line."
  fi
fi

[ "${DRY_RUN:-0}" = "1" ] && { info "DRY_RUN: nothing applied."; exit 0; }

# -- 3. test, and roll back if the test fails --------------------------------
info "Testing the configuration"
if nginx -t 2>&1; then
  green "nginx -t passed."
else
  red "nginx -t FAILED. Rolling back."
  rm -f "$MAP_DEST"
  [ "${ALREADY:-0}" = "0" ] && [ -n "${BACKUP:-}" ] && cp -p "$BACKUP" "$SITE_CONF"
  if nginx -t >/dev/null 2>&1; then
    red "Rolled back; the previous configuration is valid and still live."
  else
    red "ROLLBACK DID NOT RESTORE A VALID CONFIG. Do not reload."
    red "Restore by hand from: ${BACKUP:-<no backup taken>}"
  fi
  exit 1
fi

info "Reloading nginx"
if systemctl reload nginx; then
  green "Reloaded."
else
  red "Reload failed; the old configuration is still serving."
  exit 1
fi

# -- 4. prove it --------------------------------------------------------------
sleep 1
cc="$(curl -sSI --max-time 20 "https://$SERVER_NAME/" 2>/dev/null \
      | grep -i '^cache-control:' | tr -d '\r')"
if [ -n "$cc" ]; then
  green "Verified: $cc"
else
  red "No Cache-Control came back. The reload succeeded but the header is not"
  red "being sent — check that the add_header landed inside the right server block."
  exit 1
fi
