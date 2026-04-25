#!/usr/bin/env bash
# End-to-end smoke test for the Mumtaz platform.
# Run from your laptop or the VPS:
#     bash scripts/smoke-test.sh
#
# Verifies:
#   1. Marketing site (mumtaz.digital) — HTTP 200
#   2. Portal (app.mumtaz.digital) — HTTP 200, login page served
#   3. Portal API — auth/me returns 401 without token
#   4. Portal API — onboarding endpoint reachable
#   5. ZAKI app (zaki.mumtaz.digital) — HTTP 200
#   6. Signup → token → /me round-trip with a throwaway account
#
# Exit code 0 on success, 1 on any failure. Prints per-step pass/fail.

set -uo pipefail

PASS=0; FAIL=0
log() { echo "[$1] $2"; }
pass() { log "✅" "$1"; PASS=$((PASS+1)); }
fail() { log "❌" "$1"; FAIL=$((FAIL+1)); }

check_http() {
    local name="$1" url="$2" expected="${3:-200}"
    local code
    code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 10 "$url" || echo "000")
    if [ "$code" = "$expected" ]; then
        pass "$name → HTTP $code"
    else
        fail "$name → HTTP $code (expected $expected)  url=$url"
    fi
}

check_contains() {
    local name="$1" url="$2" needle="$3"
    local body
    body=$(curl -sk --max-time 10 "$url" || echo "")
    if echo "$body" | grep -qF "$needle"; then
        pass "$name → contains '$needle'"
    else
        fail "$name → missing '$needle'  url=$url"
    fi
}

echo
echo "── Mumtaz End-to-End Smoke Test ──"
echo

# 1. Marketing site
check_http     "marketing site"       "https://mumtaz.digital"
check_contains "marketing has hero"   "https://mumtaz.digital" "Mumtaz"

# 2. Portal pages
check_http     "portal /"             "https://app.mumtaz.digital/"
check_http     "portal /onboarding"   "https://app.mumtaz.digital/onboarding.html"
check_http     "portal /dashboard"    "https://app.mumtaz.digital/dashboard.html"
check_contains "portal login form"    "https://app.mumtaz.digital/" "Sign in"

# 3. Portal API auth gate
code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 10 https://app.mumtaz.digital/api/auth/me)
if [ "$code" = "401" ] || [ "$code" = "403" ]; then
    pass "portal /api/auth/me without token → $code (expected)"
else
    fail "portal /api/auth/me without token → $code (expected 401/403)"
fi

# 4. Onboarding endpoint reachable (should reject without token, but proxy must work)
code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 10 https://app.mumtaz.digital/api/onboarding)
if [ "$code" = "401" ] || [ "$code" = "403" ] || [ "$code" = "405" ]; then
    pass "portal /api/onboarding reachable → $code"
else
    fail "portal /api/onboarding → $code (expected 401/403/405, got something else — proxy may be broken)"
fi

# 5. Dashboard endpoint reachable
code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 10 https://app.mumtaz.digital/api/dashboard)
if [ "$code" = "401" ] || [ "$code" = "403" ]; then
    pass "portal /api/dashboard reachable → $code"
else
    fail "portal /api/dashboard → $code (proxy may be broken)"
fi

# 6. ZAKI app
check_http     "zaki.mumtaz.digital"  "https://zaki.mumtaz.digital/"

# 7. Full signup → /me round-trip with a throwaway account
EMAIL="smoke+$(date +%s)@example.com"
PASS_PW="SmokeTest!$(date +%s)"

echo
echo "── Auth round-trip (signup → token → /me) ──"
echo "    email: $EMAIL"

signup=$(curl -sk -X POST https://app.mumtaz.digital/api/auth/signup \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS_PW\",\"name\":\"Smoke Test\"}" \
    --max-time 15 || echo '{}')
TOKEN=$(echo "$signup" | grep -oE '"token"\s*:\s*"[^"]+"' | head -1 | cut -d'"' -f4)

if [ -n "$TOKEN" ]; then
    pass "signup returned a token"
    me=$(curl -sk https://app.mumtaz.digital/api/auth/me \
        -H "Authorization: Bearer $TOKEN" --max-time 10)
    if echo "$me" | grep -q "$EMAIL"; then
        pass "/me returned signed-up user"
    else
        fail "/me did not return user — got: $me"
    fi
else
    fail "signup failed — response: $signup"
fi

echo
echo "── Result ──"
echo "✅ $PASS passed   ❌ $FAIL failed"
echo

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
