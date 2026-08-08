#!/usr/bin/env bash
#
# Verify the Faizy migrations against a real PostgreSQL instance — no Docker,
# no Supabase project, no network. Applies the Supabase shim, every migration in
# order, the seed, and the business-rule tests.
#
# Run it before every migration PR:   ./scripts/verify-db.sh
#
# Requires a running PostgreSQL 14+ and psql on PATH. Defaults target a standard
# local install (port 5432, libpq's default socket). Override for anything else:
#   PGHOST=/tmp PGPORT=55432 PGUSER=postgres ./scripts/verify-db.sh
#
# On a Debian/Ubuntu box where peer auth is in force, run it AS the postgres user
# from a path that user can read:
#   sudo -u postgres /tmp/faizy-check/scripts/verify-db.sh
#
# If you have no server running, start a throwaway cluster first:
#   /usr/lib/postgresql/16/bin/initdb -D /tmp/fzpg -U postgres --auth=trust
#   /usr/lib/postgresql/16/bin/pg_ctl -D /tmp/fzpg -o '-p 55432 -k /tmp' start
#   PGHOST=/tmp PGPORT=55432 ./scripts/verify-db.sh
#
# It creates and drops ONLY the database named below. Nothing else on the cluster
# is touched — but it is still a real cluster, so prefer a dev box over anything
# serving production.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="${FAIZY_CHECK_DB:-faizy_check}"

export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-postgres}"
# Left unset unless supplied, so libpq falls back to the platform's default
# socket directory (/var/run/postgresql on Debian/Ubuntu).
if [ -n "${PGHOST:-}" ]; then export PGHOST; fi

psql_q() { psql -v ON_ERROR_STOP=1 -q -d "$DB" "$@"; }

echo "==> Recreating $DB on ${PGHOST:-<default socket>}:$PGPORT as $PGUSER"
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
echo
# The database is left in place so you can inspect the result. It is dropped and
# recreated at the START of each run, so it never accumulates — but say so
# explicitly, since on a shared or production cluster a stray database that
# nobody remembers creating is exactly the kind of thing that worries people.
echo "    Database '$DB' was left in place for inspection."
echo "    Remove it with:  dropdb $DB"
