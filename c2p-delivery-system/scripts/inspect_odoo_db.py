#!/usr/bin/env python3
"""Inspect a live Odoo database and print a readable report.

Read-only: every call is a search/read/search_count — nothing is created or
written. Reuses the delivery_api Odoo bridge.

Credentials: ODOO_URL/ODOO_USER/ODOO_PASSWORD from the environment or
delivery_api/.env win, and anything they leave unset falls back to the
console's encrypted Odoo Connection. That is deliberately the reverse of the
API, which lets the stored connection override env — on a command line the
operator typing a credential should get the credential they typed.

Usage, on the VPS:

    cd /opt/mumtaz/c2p-delivery-system
    python3 scripts/inspect_odoo_db.py MUMTAZ_C2P
    python3 scripts/inspect_odoo_db.py MUMTAZ_C2P --json > /tmp/mumtaz_c2p.json
    python3 scripts/inspect_odoo_db.py --list
    python3 scripts/inspect_odoo_db.py Mumtaz_C2P --leads

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


def wire_console_connection() -> None:
    """Let the console's encrypted Odoo Connection fill in credentials the
    environment does not supply.

    `delivery_api.odoo` only consults a connection store through its module
    global CONN_PROVIDER, which `main.py` installs at app startup. A standalone
    script never gets that, so without this the stored connection is invisible
    here and env is the only source. Anything already in the environment is
    left alone, so an explicit credential on the command line still wins.
    """
    try:
        from delivery_api import odoo as odoo_mod, store, tenancy
    except Exception:
        return  # store unavailable (no DB, no key) — env-only is still fine

    def resolver(_db: str):
        try:
            s = store.get_setting("odoo_connection") or {}
        except Exception:
            return None
        url = os.environ.get("ODOO_URL") or s.get("url")
        user = os.environ.get("ODOO_USER") or s.get("user")
        pw = os.environ.get("ODOO_PASSWORD")
        if not pw and s.get("key_enc"):
            try:
                pw = tenancy.dec_secret(s["key_enc"])
            except Exception:
                pw = None
        return (url, user, pw) if url and user and pw else None

    odoo_mod.CONN_PROVIDER = resolver


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


# How the lead pile breaks down, as (heading, grouping field).
LEAD_GROUPINGS = [
    ("By type", "type"),
    ("By stage", "stage_id"),
    ("By source", "source_id"),
    ("By medium", "medium_id"),
    ("By sales team", "team_id"),
    ("By salesperson", "user_id"),
    ("By company", "company_id"),
]


def analyse_leads(db: str, top: int = 12) -> dict:
    """Break the CRM pile down server-side. read_group does the counting in
    PostgreSQL, so this stays cheap even at ~12k leads."""
    from delivery_api.odoo import OdooClient

    client = OdooClient(db)
    out: dict = {"db": db, "total": client.execute("crm.lead", "search_count", [])}

    groups: dict = {}
    for heading, field in LEAD_GROUPINGS:
        try:
            rows = client.execute("crm.lead", "read_group", [], [field], [field],
                                  lazy=False)
        except Exception as exc:
            groups[heading] = [("n/a", f"{type(exc).__name__}")]
            continue
        counted = []
        for r in rows:
            value = r.get(field)
            if isinstance(value, (list, tuple)):   # many2one -> (id, label)
                label = value[1]
            elif value in (False, None):
                label = "— not set —"
            else:
                label = str(value)
            counted.append((label, r.get("__count") or r.get(f"{field}_count") or 0))
        counted.sort(key=lambda kv: kv[1], reverse=True)
        groups[heading] = counted[:top]
    out["groups"] = groups

    # Contactability: a scraped lead with neither email nor phone is not
    # actionable, which is the main thing to know about a bulk-imported pile.
    probes = {
        "Won": [("stage_id.is_won", "=", True)],
        "Lost (inactive)": [("active", "=", False)],
        "No email": [("email_from", "in", [False, ""])],
        "No phone": [("phone", "in", [False, ""])],
        "No email and no phone": [("email_from", "in", [False, ""]),
                                  ("phone", "in", [False, ""])],
        "Has an expected revenue": [("expected_revenue", ">", 0)],
        "Never contacted (no activity)": [("activity_ids", "=", False)],
    }
    quality: dict = {}
    for label, domain in probes.items():
        try:
            quality[label] = client.execute("crm.lead", "search_count", domain)
        except Exception as exc:
            quality[label] = f"n/a ({type(exc).__name__})"
    out["quality"] = quality

    # Age span: when this pile arrived says whether it is one import or ongoing.
    for label, order in (("oldest", "create_date asc"), ("newest", "create_date desc")):
        try:
            rec = client.execute("crm.lead", "search_read", [], fields=["create_date"],
                                 limit=1, order=order)
            out[label] = rec[0]["create_date"] if rec else None
        except Exception:
            out[label] = None

    return out


def render_leads(rep: dict) -> str:
    out = [f"CRM leads in {rep['db']} : {rep['total']}"]
    if rep.get("oldest") or rep.get("newest"):
        out.append(f"Created between      : {rep.get('oldest')}  ..  {rep.get('newest')}")
    out.append("")

    out.append("Quality / actionability")
    width = max(len(k) for k in rep["quality"])
    for label, value in rep["quality"].items():
        share = ""
        if isinstance(value, int) and rep["total"]:
            share = f"  ({value * 100 // rep['total']}%)"
        out.append(f"  {label.ljust(width)} : {value}{share}")

    for heading, rows in rep["groups"].items():
        out.append("")
        out.append(heading)
        if not rows:
            out.append("  (none)")
            continue
        width = min(48, max(len(str(r[0])) for r in rows))
        for label, count in rows:
            out.append(f"  {str(label)[:48].ljust(width)} : {count}")
    return "\n".join(out)


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


def error_text(exc: Exception) -> str:
    """The human-readable text of an exception. An XML-RPC Fault's str() is a
    repr with the newlines escaped, so the real server message only comes out
    of faultString."""
    return getattr(exc, "faultString", None) or str(exc)


def summarise_error(exc: Exception) -> str:
    """One line out of an exception. Odoo wraps server errors in a Fault
    carrying a full server traceback; its last non-empty line is the actual
    cause, so surface that instead of 40 lines of frames."""
    text = error_text(exc)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if "Traceback" in text and lines:
        return f"{type(exc).__name__}: {lines[-1]}"
    return f"{type(exc).__name__}: {text}"


def server_databases(url: str) -> list[str] | None:
    """Databases the server admits to, or None when the db service is blocked
    (the common case on a hardened instance: list_db = False)."""
    from delivery_api.odoo import list_databases

    try:
        return list_databases(url)
    except Exception:
        return None


def hint_for(exc: Exception, db: str) -> str:
    """Point at the actual cause rather than guessing credentials."""
    text = error_text(exc)

    if "does not exist" in text:
        url = os.getenv("ODOO_URL", "http://localhost:8069")
        msg = [f"The server is reachable, but it has no database named '{db}'.",
               "Database names are case-sensitive."]
        names = server_databases(url)
        if names:
            msg.append("Databases this server serves: " + ", ".join(names))
        elif names is None:
            msg.append("The server will not list its databases (list_db = False); "
                       "on the host try:  sudo -u postgres psql -lqt | cut -d'|' -f1")
        else:
            msg.append("The server reports no databases at all.")
        return "\n".join(msg)

    if isinstance(exc, PermissionError) or "AccessDenied" in text:
        return ("Reached the database but authentication was refused. Check "
                "ODOO_USER / ODOO_PASSWORD in delivery_api/.env, or the "
                "console's Odoo Connection.")

    if isinstance(exc, (ConnectionError, OSError)):
        return (f"Could not reach the Odoo server at "
                f"{os.getenv('ODOO_URL', 'http://localhost:8069')}. Check "
                "ODOO_URL and that the service is up.")

    return ("Check ODOO_URL / ODOO_USER / ODOO_PASSWORD in delivery_api/.env, "
            "or the console's Odoo Connection.")


def report_databases() -> int:
    url = os.getenv("ODOO_URL", "http://localhost:8069")
    names = server_databases(url)
    if names is None:
        print(f"{url} will not list its databases (list_db = False).",
              file=sys.stderr)
        print("On the host try:  sudo -u postgres psql -lqt | cut -d'|' -f1",
              file=sys.stderr)
        return 1
    if not names:
        print(f"{url} reports no databases.", file=sys.stderr)
        return 1
    print(f"Databases served by {url}:")
    for name in names:
        print(f"  - {name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", nargs="?",
                        help="Odoo database name, e.g. MUMTAZ_C2P")
    parser.add_argument("--list", action="store_true", dest="list_dbs",
                        help="list the databases this server serves, then exit")
    parser.add_argument("--leads", action="store_true",
                        help="break the CRM lead pile down instead of the "
                             "whole-database report")
    parser.add_argument("--json", action="store_true",
                        help="emit the full report as JSON instead of a summary")
    args = parser.parse_args()
    if not args.db and not args.list_dbs:
        parser.error("give a database name, or --list to see what is available")

    load_env(ROOT / "delivery_api" / ".env")
    wire_console_connection()

    if args.list_dbs:
        return report_databases()

    try:
        report = analyse_leads(args.db) if args.leads else inspect(args.db)
    except Exception as exc:
        print(f"Inspection failed for '{args.db}': {summarise_error(exc)}",
              file=sys.stderr)
        print(hint_for(exc, args.db), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(render_leads(report) if args.leads else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
