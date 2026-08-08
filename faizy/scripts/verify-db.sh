#!/usr/bin/env bash
#
# Verify the Faizy migrations against a real PostgreSQL instance — no Docker,
# no Supabase project, no network. Applies the Supabase shim, every migration in
# order, the seed, and the business-rule tests.
#
# Run it before every migration PR:   ./scripts/verify-db.sh
#
# Requires a running PostgreSQL 14+ and psql on PATH. Point it at any instance:
#   PGHOST=/tmp PGPORT=55432 PGUSER=postgres ./scripts/verify-db.sh
#
# If you have no server running, start a throwaway cluster first:
#   /usr/lib/postgresql/16/bin/initdb -D /tmp/fzpg -U postgres --auth=trust
#   /usr/lib/postgresql/16/bin/pg_ctl -D /tmp/fzpg -o '-p 55432 -k /tmp' start

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="${FAIZY_CHECK_DB:-faizy_check}"

export PGHOST="${PGHOST:-/tmp}"
export PGPORT="${PGPORT:-55432}"
export PGUSER="${PGUSER:-postgres}"

psql_q() { psql -v ON_ERROR_STOP=1 -q -d "$DB" "$@"; }

echo "==> Recreating $DB on $PGHOST:$PGPORT"
psql -v ON_ERROR_STOP=1 -q -d postgres \
  -c "drop database if exists $DB;" \
  -c "create database $DB;" >/dev/null

echo "==> Applying Supabase shim (auth + storage stand-ins)"
psql_q -f "$ROOT/supabase/tests/00_supabase_shim.sql" >/dev/null

echo "==> Applying migrations"
for f in "$ROOT"/supabase/migrations/*.sql; do
  printf '    %s\n' "$(basename "$f")"
  psql_q -f "$f" >/dev/null
done

echo "==> Applying seed"
psql_q -f "$ROOT/supabase/seed.sql" >/dev/null

echo "==> Running business-rule tests"
# NOTICEs carry the PASS lines; surface them and let ON_ERROR_STOP catch failures.
psql -v ON_ERROR_STOP=1 -d "$DB" -f "$ROOT/supabase/tests/01_business_rules.sql" 2>&1 \
  | sed -n 's/^psql:[^ ]* NOTICE:  //p'

echo
echo "==> OK — schema applies cleanly and all business rules hold."
