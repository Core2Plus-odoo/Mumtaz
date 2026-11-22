#!/usr/bin/env python3
"""Register (or re-point) a delivery-system engagement at an Odoo database.

The pipeline drives a tenant through an Engagement record, and an engagement
with no `odoo_db` cannot reach Odoo at all — `sync` logs "Odoo unavailable" and
every live-write stage refuses. This registers one so the tenant is addressable.

Writes to the delivery system's own SQLite store only. It never touches Odoo or
PostgreSQL, and it verifies the database is reachable before recording it, so a
typo in the name is caught here rather than at the first stage run.

    python3 scripts/register_engagement.py Mumtaz_C2P "C2P Consultants FZC LLC"
    python3 scripts/register_engagement.py Mumtaz_C2P --list
    python3 scripts/register_engagement.py Mumtaz_C2P "C2P" --skip-check

Idempotent: an existing engagement for the same database is re-pointed rather
than duplicated, so re-running is safe.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "delivery_api"))

from inspect_odoo_db import load_env, wire_console_connection  # noqa: E402


def verify(db: str) -> str:
    """Confirm the database exists and authenticates. Returns a description."""
    from delivery_api.odoo import OdooClient

    client = OdooClient(db)
    uid = client.uid                      # raises on a bad name or credentials
    companies = client.execute("res.company", "search_read", [], fields=["name"])
    names = ", ".join(c["name"] for c in companies) or "(none)"
    return f"reachable as {client.user} (uid {uid}); companies: {names}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("db", help="Odoo database name, e.g. Mumtaz_C2P")
    ap.add_argument("company", nargs="?",
                    help="engagement name; defaults to the database name")
    ap.add_argument("--account-id", help="attach to an existing Account id")
    ap.add_argument("--list", action="store_true", dest="list_only",
                    help="show existing engagements for this database and exit")
    ap.add_argument("--skip-check", action="store_true",
                    help="record it without verifying Odoo is reachable")
    args = ap.parse_args()

    load_env(ROOT / "delivery_api" / ".env")
    wire_console_connection()

    import models as m
    from store import EngagementStore

    # main.py wraps this in tenancy.StoreProxy; for a single-operator CLI the
    # default store is the right one.
    st = EngagementStore()
    # EngagementStore.list() projects only id/company/account_id/stages — it
    # does not include odoo_db — so each record has to be fetched to match on
    # the database it targets.
    existing = [eng for eng in (st.get(row["id"]) for row in st.list())
                if eng and eng.odoo_db == args.db]

    if args.list_only:
        if not existing:
            print(f"No engagement is pointed at '{args.db}'.")
            return 0
        for eng in existing:
            print(f"{eng.id}  {eng.company}  (created {eng.created_at})")
        return 0

    if not args.skip_check:
        try:
            print(f"Checking '{args.db}' ... {verify(args.db)}")
        except Exception as exc:
            print(f"Refusing to register '{args.db}': {type(exc).__name__}: "
                  f"{str(exc).splitlines()[0] if str(exc) else exc}", file=sys.stderr)
            print("Run inspect_odoo_db.py --list to see the available databases, "
                  "or pass --skip-check to record it anyway.", file=sys.stderr)
            return 1

    company = args.company or args.db

    if existing:
        eng = existing[0]
        changed = []
        if eng.company != company:
            eng.company = company
            changed.append("company")
        if args.account_id and eng.account_id != args.account_id:
            eng.account_id = args.account_id
            changed.append("account_id")
        if changed:
            st.save(eng)
            print(f"Updated {eng.id} ({', '.join(changed)}).")
        else:
            print(f"{eng.id} already points at '{args.db}' as '{company}' — "
                  "nothing to change.")
        if len(existing) > 1:
            others = ", ".join(e.id for e in existing[1:])
            print(f"Note: {len(existing)} engagements share this database "
                  f"({others}); only the first was updated.", file=sys.stderr)
        return 0

    eng = st.create(company, args.db, account_id=args.account_id)
    print(f"Created {eng.id}: '{company}' -> {args.db}")
    print(f"Stages pending: {', '.join(m.STAGES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
