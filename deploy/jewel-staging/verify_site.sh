#!/usr/bin/env bash
#
# Verify a published Jewel site, because "HTTP 200" proves nothing here.
#
# nginx is configured with a catch-all that serves the landing page for any
# path it does not recognise. That turns every MISSING page into a confident
# 200 with real-looking HTML. On 11 Nov 2026 /apps/ and /pricing/ had sat
# unpublished for days behind exactly that: six URLs all answered 200, a
# deliberately bogus URL answered 200 too, and only a byte comparison showed
# that three of them were the landing page wearing another name.
#
# So this script never trusts a status code. It:
#   1. fingerprints the catch-all by requesting a path that cannot exist
#   2. fails any expected page whose body is byte-identical to that
#   3. compares what is served against what is on disk
#   4. reports Cache-Control, because a correct file served with no cache
#      policy still shows a stale page to a real browser
#
# Usage:
#   deploy/jewel-staging/verify_site.sh                     # checks the default host
#   SITE_URL=https://jewel.mumtaz.digital verify_site.sh
#   SITE_ROOT=/opt/mumtaz/jewel-landing verify_site.sh      # also diff against disk
#
# Exit 0 = every expected page is really published. Exit 1 = at least one is
# not, and the output names it.
set -uo pipefail

SITE_URL="${SITE_URL:-https://jewel.mumtaz.digital}"
SITE_URL="${SITE_URL%/}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SITE_SRC="${SITE_SRC:-$REPO_ROOT/website/jewel}"
SITE_ROOT="${SITE_ROOT:-}"
TIMEOUT="${TIMEOUT:-25}"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
green(){ printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '\033[36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }

command -v curl >/dev/null 2>&1 || { red "curl is required."; exit 2; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

fetch() {  # fetch <path> <outfile>; echoes the status code
  curl -sL --max-time "$TIMEOUT" -o "$2" -w '%{http_code}' "$SITE_URL/$1" 2>/dev/null || echo 000
}

# -- 1. fingerprint the catch-all -------------------------------------------
# Any page identical to THIS is not a page; it is nginx's fallback.
BOGUS="verify-$(date +%s)-$$-does-not-exist"
bogus_code="$(fetch "$BOGUS/" "$tmp/bogus.html")"
if [ ! -s "$tmp/bogus.html" ]; then
  red "Could not reach $SITE_URL (bogus probe returned $bogus_code)."
  exit 2
fi
bogus_sha="$(sha256sum "$tmp/bogus.html" | cut -d' ' -f1)"
if [ "$bogus_code" = "200" ]; then
  info "Catch-all confirmed: a non-existent path returns 200 ($(stat -c%s "$tmp/bogus.html") bytes)."
  info "Status codes are therefore meaningless here; comparing bodies instead."
  CATCHALL=1
else
  info "No catch-all: a non-existent path returns $bogus_code."
  CATCHALL=0
fi

# -- 2. what should be published --------------------------------------------
# Every directory in website/jewel holding an index.html, plus the root.
pages=("")
if [ -d "$SITE_SRC" ]; then
  while IFS= read -r d; do pages+=("$(basename "$d")/"); done < <(
    find "$SITE_SRC" -mindepth 2 -maxdepth 2 -name index.html -printf '%h\n' | sort)
else
  warn "No $SITE_SRC on this machine; checking the known page list instead."
  pages+=("preview/" "apps/" "pricing/" "intelligence/")
fi

info "Checking ${#pages[@]} expected pages against $SITE_URL"
echo

fail=0
for p in "${pages[@]}"; do
  label="/${p}"
  out="$tmp/page.html"
  code="$(fetch "$p" "$out")"
  size="$(stat -c%s "$out" 2>/dev/null || echo 0)"
  sha="$(sha256sum "$out" 2>/dev/null | cut -d' ' -f1)"
  title="$(grep -oiP '<title>\K[^<]*' "$out" 2>/dev/null | head -1)"

  # The landing page legitimately equals itself; every other page must not.
  if [ -n "$p" ] && [ "$CATCHALL" = "1" ] && [ "$sha" = "$bogus_sha" ]; then
    red "  FAIL  $label  $code  serves the LANDING PAGE — not published"
    fail=$((fail + 1))
    continue
  fi
  if [ "$code" != "200" ]; then
    red "  FAIL  $label  HTTP $code"
    fail=$((fail + 1))
    continue
  fi

  # Compare against the repo copy where we have one.
  src="$SITE_SRC/${p}index.html"
  note=""
  if [ -f "$src" ]; then
    if cmp -s "$out" "$src"; then note="matches repo"; else note="DIFFERS from repo"; fi
  fi
  # And against what is actually on the web root, if we can see it.
  if [ -n "$SITE_ROOT" ] && [ -f "$SITE_ROOT/${p}index.html" ]; then
    if cmp -s "$out" "$SITE_ROOT/${p}index.html"; then note="$note; matches web root"
    else note="$note; DIFFERS from web root"; fi
  fi

  if printf '%s' "$note" | grep -q DIFFERS; then
    red "  STALE $label  ${size}B  ${title:-no title}  ($note)"
    fail=$((fail + 1))
  else
    green "  ok    $label  ${size}B  ${title:-no title}${note:+  ($note)}"
  fi
done

# -- 3. caching ---------------------------------------------------------------
# A correct file served with no cache policy still shows a browser the old one:
# with no Cache-Control, caches apply a heuristic of roughly 10% of the file's
# age, so a page can be served without revalidating for a long time.
echo
hdrs="$(curl -sSIL --max-time "$TIMEOUT" "$SITE_URL/" 2>/dev/null)"
cc="$(printf '%s' "$hdrs" | grep -i '^cache-control:' | head -1 | tr -d '\r')"
lm="$(printf '%s' "$hdrs" | grep -i '^last-modified:' | head -1 | tr -d '\r')"
if [ -z "$cc" ]; then
  warn "No Cache-Control on the landing page. Browsers will cache it heuristically,"
  warn "so a correct deploy can still look stale. ${lm:-}"
  warn "See deploy/jewel-staging/nginx-cache-headers.conf."
else
  info "$cc"
fi

echo
if [ "$fail" -eq 0 ]; then
  green "All ${#pages[@]} expected pages are really published."
  exit 0
fi
red "$fail of ${#pages[@]} expected pages are NOT correctly published (see above)."
exit 1
