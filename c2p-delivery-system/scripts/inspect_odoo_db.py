#!/usr/bin/env python3
"""Inspect a live Odoo database and print a readable report.

Read-only: every call is a search/read/search_count — nothing is created or
written. Reuses the delivery_api Odoo bridge, so credentials resolve exactly
the way the API resolves them (encrypted console connection first via
CONN_PROVIDER, then ODOO_URL/ODOO_USER/ODOO_PASSWORD from the env file).

Usage, on the VPS:

    cd /opt/mumtaz/c2p-delivery-system
    python3 scripts/inspect_odoo_db.py MUMTAZ_C2P
    python3 scripts/inspect_odoo_db.py MUMTAZ_C2P --json > /tmp/mumtaz_c2p.json

Env is read from delivery_api/.env (the service env file) when present.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_env(path: Path) -> None:
    """Minimal .env loader — existing environment always wins."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


# Counts worth knowing before touching anything, as (label, model, domain).
PROBES = [
    ("Companies", "res.company", []),
    ("Active users", "res.users", [("active", "=", True)]),
    ("Partners (companies)", "res.partner", [("is_company", "=", True)]),
    ("Partners (contacts)", "res.partner", [("is_company", "=", False)]),
    ("CRM leads/opportunities", "crm.lead", []),
    ("Sale orders", "sale.order", []),
    ("Customer invoices", "account.move", [("move_type", "=", "out_invoice")]),
    ("Vendor bills", "account.move", [("move_type", "=", "in_invoice")]),
    ("Journal entries", "account.move", []),
    ("Chart of accounts", "account.account", []),
    ("Products", "product.template", []),
    ("Projects", "project.project", []),
    ("Project tasks", "project.task", []),
    ("Employees", "hr.employee", []),
    ("Purchase orders", "purchase.order", []),
    ("Stock pickings", "stock.picking", []),
    ("Automation rules", "base.automation", []),
    ("Server actions", "ir.actions.server", []),
    ("Scheduled actions", "ir.cron", []),
    ("Studio customisations", "ir.model", [("state", "=", "manual")]),
]


def inspect(db: str) -> dict:
    from delivery_api.odoo import OdooClient  # noqa: E402  (after sys.path setup)

    client = OdooClient(db)
    report: dict = {"db": db, "url": client.url, "user": client.user}
    report["uid"] = client.uid  # raises PermissionError on bad credentials

    report["version"] = client._common.version()

    modules = client.installed_modules()
    report["installed_module_count"] = len(modules)
    report["installed_modules"] = modules
    # Modules not shipped by Odoo itself are the local footprint worth reviewing.
    report["custom_modules"] = sorted(
        m for m in modules if m.startswith(("mumtaz", "c2p", "zaki"))
    )

    report["companies"] = client.execute(
        "res.company", "search_read", [],
        fields=["name", "currency_id", "country_id", "vat"],
    )

    counts: dict = {}
    for label, model, domain in PROBES:
        try:
            counts[label] = client.execute(model, "search_count", domain)
        except Exception as exc:  # model absent when its app isn't installed
            counts[label] = f"n/a ({type(exc).__name__})"
    report["counts"] = counts

    return report


def render(report: dict) -> str:
    out = []
    add = out.append
    add(f"Odoo database : {report['db']}")
    add(f"Server        : {report['url']}")
    add(f"Authenticated : {report['user']} (uid {report['uid']})")
    ver = report.get("version", {})
    add(f"Version       : {ver.get('server_version', 'unknown')}")
    add("")

    add("Companies")
    for c in report["companies"]:
        currency = (c.get("currency_id") or [None, "?"])[1]
        country = (c.get("country_id") or [None, "—"])[1]
        add(f"  - {c['name']}  [{currency}, {country}, VAT {c.get('vat') or '—'}]")
    add("")

    add("Record counts")
    width = max(len(k) for k in report["counts"])
    for label, value in report["counts"].items():
        add(f"  {label.ljust(width)} : {value}")
    add("")

    add(f"Installed modules : {report['installed_module_count']}")
    custom = report["custom_modules"]
    add(f"Local/custom      : {', '.join(custom) if custom else 'none detected'}")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", help="Odoo database name, e.g. MUMTAZ_C2P")
    parser.add_argument("--json", action="store_true",
                        help="emit the full report as JSON instead of a summary")
    args = parser.parse_args()

    load_env(ROOT / "delivery_api" / ".env")

    try:
        report = inspect(args.db)
    except Exception as exc:
        print(f"Inspection failed for '{args.db}': {type(exc).__name__}: {exc}",
              file=sys.stderr)
        print("Check ODOO_URL / ODOO_USER / ODOO_PASSWORD in "
              "delivery_api/.env, or the console's Odoo Connection.",
              file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, default=str) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
