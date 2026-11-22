#!/usr/bin/env bash
#
# Put the repo's nginx server block for jewel.mumtaz.digital in place, safely.
#
#   * backs up the live file outside sites-enabled (nginx loads everything in
#     there, so a backup left inside it would be loaded too)
#   * copies the repo file into sites-available, keeps the sites-enabled symlink
#   * `nginx -t` BEFORE reload; on failure restores the backup, re-tests, exits 1
#   * then re-applies the cache headers (apply_cache_headers.sh is idempotent),
#     because that script edits the live file and a fresh copy loses its lines
#   * finally proves the four routes answer: /, /app/, /jawhar/v1/health, /odoo
#
# Usage (as root, on the VPS):
#   deploy/jewel-staging/install_nginx_conf.sh
#   DRY_RUN=1 deploy/jewel-staging/install_nginx_conf.sh   # show the diff only
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/nginx/jewel.mumtaz.digital.conf"
DEST="${SITE_CONF:-/etc/nginx/sites-available/jewel.mumtaz.digital.conf}"
LINK="/etc/nginx/sites-enabled/$(basename "$DEST")"
BACKUP_DIR="/var/backups/jewel-nginx"
HOST="${SERVER_NAME:-jewel.mumtaz.digital}"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
green(){ printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '\033[36m==> %s\033[0m\n' "$*"; }

[ "$(id -u)" = "0" ] || { red "Run this as root: it edits /etc/nginx."; exit 2; }
command -v nginx >/dev/null 2>&1 || { red "nginx not found."; exit 2; }
[ -f "$SRC" ] || { red "Missing $SRC"; exit 2; }

if [ -f "$DEST" ]; then
  info "Changes the repo file would make to $DEST:"
  diff -u "$DEST" "$SRC" && green "(none)"
fi
[ "${DRY_RUN:-0}" = "1" ] && { info "DRY_RUN: nothing applied."; exit 0; }

mkdir -p "$BACKUP_DIR"
if [ -f "$DEST" ]; then
  BACKUP="$BACKUP_DIR/$(basename "$DEST").$(date +%Y%m%d%H%M%S)"
  cp -p "$DEST" "$BACKUP"
  info "Backed up to $BACKUP"
fi
install -m 0644 "$SRC" "$DEST"
[ -e "$LINK" ] || ln -s "$DEST" "$LINK"

if ! nginx -t 2>&1; then
  red "nginx -t FAILED. Rolling back."
  [ -n "${BACKUP:-}" ] && cp -p "$BACKUP" "$DEST"
  nginx -t >/dev/null 2>&1 && red "Rolled back; the previous configuration is valid and still live." \
                            || red "ROLLBACK DID NOT RESTORE A VALID CONFIG. Do not reload. Restore from $BACKUP_DIR by hand."
  exit 1
fi
systemctl reload nginx || { red "Reload failed; the old configuration is still serving."; exit 1; }
green "Installed and reloaded."

if [ -f "$HERE/apply_cache_headers.sh" ]; then
  info "Re-applying the cache headers (the fresh copy does not carry them)"
  bash "$HERE/apply_cache_headers.sh" || { red "apply_cache_headers.sh failed; see above."; exit 1; }
fi

info "Proving the routes"
rc=0
for path in / /app/ /jawhar/v1/health /odoo; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "https://$HOST$path" 2>/dev/null || echo 000)"
  case "$path" in
    /)       want="200" ;;
    *)       want="401" ;;   # restricted: either the password or a listed address
  esac
  if [ "$code" = "$want" ]; then green "  $path -> $code"; else red "  $path -> $code (expected $want)"; rc=1; fi
done
[ "$rc" = "0" ] && green "Every route answers as expected." || red "A route is not answering as expected; see above."
exit $rc
