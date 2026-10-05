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
    python3 scripts/inspect_odoo_db.py Mumtaz_C2P --diagnose

Env is read from delivery_api/.env (the service env file) when present.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# delivery_api's modules import each other flatly (`from models import ...`),
# which only resolves with that directory itself on the path — the service runs
# with it as its working directory. Both entries are needed: `delivery_api.odoo`
# for the client, and the flat path for whatever `store` and `tenancy` import.
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "delivery_api"))


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
        import tenancy
        from store import EngagementStore
        from delivery_api import odoo as odoo_mod
        # `store` in main.py is an instance, not the module, so build the
        # default one here rather than calling module-level functions.
        st = EngagementStore()
    except Exception as exc:
        # Env-only is a valid setup, but say so rather than vanishing: this
        # swallowed a ModuleNotFoundError once and the fallback silently
        # no-opped in production.
        print(f"note: console connection unavailable "
              f"({type(exc).__name__}: {exc}); using environment only",
              file=sys.stderr)
        return

    def resolver(_db: str):
        try:
            s = st.get_setting("odoo_connection") or {}
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
    # Odoo's search drops archived records unless the domain names `active`,
    # and a lost lead is archived — so an unqualified count hides the losses.
    ("CRM leads (active)", "crm.lead", []),
    ("CRM leads (archived/lost)", "crm.lead", [("active", "=", False)]),
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


# Odoo hides archived records unless asked. A lost lead IS archived, so every
# count here must opt in or the lost population vanishes from the report.
ALL_RECORDS = {"active_test": False}


def analyse_leads(db: str, top: int = 12) -> dict:
    """Break the CRM pile down server-side. read_group does the counting in
    PostgreSQL, so this stays cheap even at tens of thousands of leads."""
    from delivery_api.odoo import OdooClient

    client = OdooClient(db)
    total = client.execute("crm.lead", "search_count", [], context=ALL_RECORDS)
    live = client.execute("crm.lead", "search_count", [("active", "=", True)],
                          context=ALL_RECORDS)
    out: dict = {"db": db, "total": total, "active": live,
                 "archived": total - live}

    groups: dict = {}
    for heading, field in LEAD_GROUPINGS:
        try:
            rows = client.execute("crm.lead", "read_group", [], [field], [field],
                                  lazy=False, context=ALL_RECORDS)
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
        "Archived (lost)": [("active", "=", False)],
        "No email": [("email_from", "in", [False, ""])],
        "No phone": [("phone", "in", [False, ""])],
        "No email and no phone": [("email_from", "in", [False, ""]),
                                  ("phone", "in", [False, ""])],
        "Has an expected revenue": [("expected_revenue", ">", 0)],
        # The archive sweep's only live condition, and its overlap with the
        # archived population — the two numbers that say whether that cron
        # actually produced the archives attributed to it.
        "Bounced (message_bounce > 0)": [("message_bounce", ">", 0)],
        "Bounced AND archived": [("message_bounce", ">", 0),
                                 ("active", "=", False)],
        "Archived but never bounced": [("message_bounce", "=", 0),
                                       ("active", "=", False)],
        "Never contacted (no activity)": [("activity_ids", "=", False)],
    }
    quality: dict = {}
    for label, domain in probes.items():
        try:
            quality[label] = client.execute("crm.lead", "search_count", domain,
                                            context=ALL_RECORDS)
        except Exception as exc:
            quality[label] = f"n/a ({type(exc).__name__})"
    out["quality"] = quality

    # Age span: when this pile arrived says whether it is one import or ongoing.
    for label, order in (("oldest", "create_date asc"), ("newest", "create_date desc")):
        try:
            rec = client.execute("crm.lead", "search_read", [], fields=["create_date"],
                                 limit=1, order=order, context=ALL_RECORDS)
            out[label] = rec[0]["create_date"] if rec else None
        except Exception:
            out[label] = None

    return out


def diagnose(db: str) -> dict:
    """Answer two questions the breakdown raised: is the Leads stage gate
    switched on, and what is archiving leads in bulk."""
    from delivery_api.odoo import OdooClient

    client = OdooClient(db)
    out: dict = {"db": db}

    # ── 1. Is the Leads feature on? ──────────────────────────────────────
    # crm.lead.type defaults to 'lead' only when the user has
    # crm.group_use_lead; otherwise every created record is an opportunity.
    # Resolve the group through ir.model.data since xml_ids are not fields.
    try:
        ref = client.execute("ir.model.data", "search_read",
                             [("module", "=", "crm"), ("name", "=", "group_use_lead")],
                             fields=["res_id"], limit=1)
        if ref:
            # The members field is `user_ids` on modern Odoo and `users` on
            # older releases; try both rather than guess the version.
            members = None
            for field in ("user_ids", "users"):
                try:
                    grp = client.execute("res.groups", "read", [ref[0]["res_id"]],
                                         fields=[field])
                    members = len(grp[0].get(field) or []) if grp else 0
                    break
                except Exception:
                    continue
            out["leads_feature"] = {"group_found": True, "members": members,
                                    "enabled": bool(members)}
        else:
            out["leads_feature"] = {"group_found": False}
    except Exception as exc:
        out["leads_feature"] = {"error": f"{type(exc).__name__}: {exc}"}

    # What a new lead would actually default to, straight from the field.
    try:
        out["type_default"] = client.execute("crm.lead", "default_get", ["type"])
    except Exception as exc:
        out["type_default"] = {"error": type(exc).__name__}

    # ── 2. Who or what is archiving leads ────────────────────────────────
    # write_uid on the archived rows names the actor; a single user behind
    # tens of thousands of writes means an automation running as that user.
    try:
        rows = client.execute("crm.lead", "read_group",
                              [("active", "=", False)], ["write_uid"], ["write_uid"],
                              lazy=False, context=ALL_RECORDS)
        actors = []
        for r in rows:
            who = r.get("write_uid")
            label = who[1] if isinstance(who, (list, tuple)) else "— unknown —"
            actors.append((label, r.get("__count") or 0))
        actors.sort(key=lambda kv: kv[1], reverse=True)
        out["archived_by"] = actors[:12]
    except Exception as exc:
        out["archived_by"] = [("n/a", type(exc).__name__)]

    # Lost reasons say whether the archiving was a judgement or a sweep.
    try:
        rows = client.execute("crm.lead", "read_group",
                              [("active", "=", False)], ["lost_reason_id"],
                              ["lost_reason_id"], lazy=False, context=ALL_RECORDS)
        reasons = []
        for r in rows:
            v = r.get("lost_reason_id")
            label = v[1] if isinstance(v, (list, tuple)) else "— none given —"
            reasons.append((label, r.get("__count") or 0))
        reasons.sort(key=lambda kv: kv[1], reverse=True)
        out["lost_reasons"] = reasons[:12]
    except Exception as exc:
        out["lost_reasons"] = [("n/a", type(exc).__name__)]

    # ── 3. Automation touching crm.lead ──────────────────────────────────
    automation: dict = {}
    try:
        automation["Scheduled actions (crons)"] = client.execute(
            "ir.cron", "search_read", [], context=ALL_RECORDS,
            fields=["name", "active", "interval_type", "interval_number", "nextcall"])
    except Exception as exc:
        automation["Scheduled actions (crons)"] = [{"error": type(exc).__name__}]
    for label, model, domain in [
        ("Automation rules on crm.lead", "base.automation",
         [("model_id.model", "=", "crm.lead")]),
        ("Server actions on crm.lead", "ir.actions.server",
         [("model_id.model", "=", "crm.lead")]),
    ]:
        try:
            automation[label] = client.execute(
                model, "search_read", domain, context=ALL_RECORDS,
                fields=["name", "state"] if "server" in model
                else ["name", "trigger", "active"])
        except Exception as exc:
            automation[label] = [{"error": f"{type(exc).__name__}: {exc}"}]
    out["automation"] = automation

    return out


def render_diagnose(rep: dict) -> str:
    out = [f"Diagnostics for {rep['db']}", ""]

    lf = rep.get("leads_feature", {})
    out.append("Leads stage gate")
    td = rep.get("type_default")
    default_type = td.get("type") if isinstance(td, dict) else None
    if default_type:
        out.append(f"  a new crm.lead defaults to type {default_type!r}")
        if default_type == "lead":
            out.append("  -> the gate is ON. Records arriving as 'opportunity'")
            out.append("     are being set or converted by something else;")
            out.append("     check the automation listed below.")
        else:
            out.append("  -> the gate is OFF, so everything created skips")
            out.append("     qualification. Fix: CRM > Settings > enable Leads.")
    lf = rep.get("leads_feature", {})
    if lf.get("error"):
        out.append(f"  (group lookup failed: {lf['error'][:120]})")
    elif lf.get("group_found"):
        out.append(f"  crm.group_use_lead members: {lf.get('members')}")
    out.append("")

    out.append("Archived leads by last writer")
    for label, count in rep.get("archived_by", []):
        out.append(f"  {str(label)[:48].ljust(34)} : {count}")
    out.append("")

    out.append("Archived leads by lost reason")
    for label, count in rep.get("lost_reasons", []):
        out.append(f"  {str(label)[:48].ljust(34)} : {count}")

    for heading, rows in rep.get("automation", {}).items():
        out.append("")
        out.append(f"{heading} ({len(rows)})")
        for r in rows:
            if r.get("error"):
                out.append(f"  n/a ({r['error']})")
                continue
            bits = [str(r.get("name", "?"))[:46]]
            if "trigger" in r:
                bits.append(f"trigger={r['trigger']}")
            if "state" in r:
                bits.append(f"state={r['state']}")
            if "interval_type" in r:
                bits.append(f"every {r.get('interval_number')} {r.get('interval_type')}")
            if r.get("nextcall"):
                bits.append(f"next {r['nextcall']}")
            if r.get("active") is False:
                bits.append("INACTIVE")
            out.append("  " + "  ".join(bits))
    return "\n".join(out)


def show_schema(db: str, model: str) -> dict:
    """Field list for a model, so a module is written against the real schema
    rather than remembered version differences."""
    from delivery_api.odoo import OdooClient

    client = OdooClient(db)
    fields = client.execute(
        "ir.model.fields", "search_read", [("model", "=", model)],
        fields=["name", "ttype", "required", "store", "relation", "field_description"],
        context=ALL_RECORDS, order="name")
    return {"db": db, "model": model, "fields": fields}


def render_schema(rep: dict) -> str:
    if not rep["fields"]:
        return (f"Model {rep['model']!r} has no fields in {rep['db']} — "
                "the model does not exist or its module is not installed.")
    out = [f"{rep['model']} — {len(rep['fields'])} fields in {rep['db']}", "-" * 78]
    for f in rep["fields"]:
        bits = [f["name"].ljust(32), (f.get("ttype") or "?").ljust(12)]
        if f.get("relation"):
            bits.append(f"-> {f['relation']}")
        flags = []
        if f.get("required"):
            flags.append("required")
        if f.get("store") is False:
            flags.append("not stored")
        if flags:
            bits.append("[" + ", ".join(flags) + "]")
        out.append("  " + " ".join(bits))
    return "\n".join(out)


def show_projects(db: str) -> dict:
    """The project/task/milestone/group landscape, with ids, for planning a
    module against an existing structure."""
    from delivery_api.odoo import OdooClient

    client = OdooClient(db)
    out: dict = {"db": db}

    out["projects"] = client.execute(
        "project.project", "search_read", [],
        fields=["id", "name", "company_id", "partner_id", "active"],
        context=ALL_RECORDS, order="id")
    for proj in out["projects"]:
        for label, model, domain in (
                ("tasks", "project.task", [("project_id", "=", proj["id"])]),
                ("milestones", "project.milestone",
                 [("project_id", "=", proj["id"])])):
            try:
                proj[label] = client.execute(model, "search_count", domain,
                                             context=ALL_RECORDS)
            except Exception as exc:
                proj[label] = f"n/a ({type(exc).__name__})"

    out["stages"] = client.execute(
        "project.task.type", "search_read", [],
        fields=["id", "name", "sequence", "project_ids", "fold"],
        context=ALL_RECORDS, order="sequence, id")

    try:
        out["milestones"] = client.execute(
            "project.milestone", "search_read", [],
            fields=["id", "name", "project_id", "deadline", "is_reached"],
            context=ALL_RECORDS, order="project_id, name")
    except Exception as exc:
        out["milestones"] = [{"error": type(exc).__name__}]

    out["companies"] = client.execute(
        "res.company", "search_read", [],
        fields=["id", "name", "currency_id", "parent_id"], context=ALL_RECORDS)

    # Groups and users are needed to wire security without guessing ids.
    out["groups"] = client.execute(
        "res.groups", "search_read",
        ["|", ("name", "ilike", "project"), ("name", "ilike", "tracker")],
        fields=["id", "name", "category_id"], context=ALL_RECORDS)
    out["users"] = client.execute(
        "res.users", "search_read", [("active", "=", True)],
        fields=["id", "login", "name", "company_id"],
        context=ALL_RECORDS, order="id")

    # Does standard Project Updates exist here? It decides whether a custom
    # status-report model is needed at all.
    for model in ("project.update", "project.milestone"):
        try:
            out[f"has_{model.replace('.', '_')}"] = client.execute(
                "ir.model", "search_count", [("model", "=", model)],
                context=ALL_RECORDS) > 0
        except Exception:
            out[f"has_{model.replace('.', '_')}"] = "?"
    return out


def render_projects(rep: dict) -> str:
    out = [f"Companies in {rep['db']}"]
    for c in rep["companies"]:
        cur = (c.get("currency_id") or [None, "?"])[1]
        parent = (c.get("parent_id") or [None, "—"])[1]
        out.append(f"  {c['id']:>3}  {c['name'][:40]:<40} {cur}  parent: {parent}")

    out += ["", "Projects (id, company, partner, tasks, milestones)"]
    for p in rep["projects"]:
        co = (p.get("company_id") or [None, "—"])[1]
        pt = (p.get("partner_id") or [None, "—"])[1]
        flag = "" if p.get("active", True) else "  [ARCHIVED]"
        out.append(f"  {p['id']:>3}  {p['name'][:46]:<46} co={str(co)[:22]:<22} "
                   f"partner={str(pt)[:22]:<22} t={p.get('tasks')} m={p.get('milestones')}{flag}")

    out += ["", "Task stages (id, sequence, name, projects, folded)"]
    for st in rep["stages"]:
        pids = st.get("project_ids") or []
        out.append(f"  {st['id']:>3}  seq={st.get('sequence'):>3}  "
                   f"{str(st['name'])[:34]:<34} projects={pids} fold={st.get('fold')}")

    out += ["", "project.milestone records"]
    for m in rep["milestones"]:
        if m.get("error"):
            out.append(f"  n/a ({m['error']})")
            continue
        pr = (m.get("project_id") or [None, "—"])[1]
        out.append(f"  {m['id']:>4}  {str(m['name'])[:38]:<38} "
                   f"project={str(pr)[:34]:<34} deadline={m.get('deadline')} "
                   f"reached={m.get('is_reached')}")

    out += ["", "Groups matching project/tracker"]
    for g in rep["groups"]:
        cat = (g.get("category_id") or [None, "—"])[1]
        out.append(f"  {g['id']:>4}  {str(g['name'])[:40]:<40} category={cat}")

    out += ["", "Active users (id, login, company)"]
    for u in rep["users"]:
        co = (u.get("company_id") or [None, "—"])[1]
        out.append(f"  {u['id']:>3}  {str(u['login'])[:34]:<34} "
                   f"{str(u['name'])[:26]:<26} {co}")

    out += ["", "Standard models present"]
    for key in ("has_project_update", "has_project_milestone"):
        out.append(f"  {key.replace('has_', '').replace('_', '.')}: {rep.get(key)}")
    return "\n".join(out)


def show_tags(db: str, ids: list[int] | None = None, top: int = 25) -> dict:
    """Resolve crm.tag ids to names with how many leads carry each.

    The archive sweep keys off hardcoded tag ids, so the names and volumes
    behind those ids decide whether it is a precise rule or a mass sweep.
    """
    from delivery_api.odoo import OdooClient

    client = OdooClient(db)
    domain = [("id", "in", ids)] if ids else []
    tags = client.execute("crm.tag", "search_read", domain,
                          fields=["id", "name"], context=ALL_RECORDS)
    rows = []
    for t in tags:
        counts = {}
        for label, extra in (("all", []), ("archived", [("active", "=", False)])):
            try:
                counts[label] = client.execute(
                    "crm.lead", "search_count",
                    [("tag_ids", "in", [t["id"]])] + extra, context=ALL_RECORDS)
            except Exception:
                counts[label] = "?"
        rows.append((t["id"], t["name"], counts["all"], counts["archived"]))
    # Without an explicit id list, show only the tags that actually matter.
    if not ids:
        rows.sort(key=lambda r: (r[2] if isinstance(r[2], int) else 0), reverse=True)
        rows = rows[:top]
    else:
        rows.sort(key=lambda r: r[0])
    return {"db": db, "rows": rows, "explicit": bool(ids)}


def render_tags(rep: dict) -> str:
    if not rep["rows"]:
        return f"No matching crm.tag records in {rep['db']}."
    out = [f"{'id':>6}  {'tag':<40} {'leads':>8} {'archived':>9}", "-" * 68]
    for tid, name, total, archived in rep["rows"]:
        out.append(f"{tid:>6}  {str(name)[:40]:<40} {total:>8} {archived:>9}")
    return "\n".join(out)


def show_action(db: str, needle: str) -> dict:
    """Print the code of server actions whose name matches, so a sweep can be
    read rather than guessed at. Reading ir.actions.server.code is a read."""
    from delivery_api.odoo import OdooClient

    client = OdooClient(db)
    rows = client.execute("ir.actions.server", "search_read",
                          [("name", "ilike", needle)],
                          fields=["name", "state", "model_id", "code"],
                          context=ALL_RECORDS)
    return {"db": db, "needle": needle, "actions": rows}


def render_action(rep: dict) -> str:
    rows = rep["actions"]
    if not rows:
        return f"No server action matching {rep['needle']!r} in {rep['db']}."
    out = []
    for r in rows:
        model = r.get("model_id")
        model = model[1] if isinstance(model, (list, tuple)) else "?"
        out.append("=" * 72)
        out.append(f"{r['name']}   [model: {model}, state: {r.get('state')}]")
        out.append("=" * 72)
        out.append(r.get("code") or "(no code on this action)")
        out.append("")
    return "\n".join(out)


def render_leads(rep: dict) -> str:
    out = [f"CRM leads in {rep['db']} : {rep['total']}"
           f"  ({rep['active']} active, {rep['archived']} archived)"]
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
    parser.add_argument("--diagnose", action="store_true",
                        help="check the Leads stage gate and find what is "
                             "archiving leads in bulk")
    parser.add_argument("--schema", metavar="MODEL",
                        help="list a model's fields (name, type, relation, "
                             "required, stored)")
    parser.add_argument("--projects", action="store_true",
                        help="projects, stages, milestones, companies, groups "
                             "and users with their ids, for module planning")
    parser.add_argument("--tags", metavar="IDS", nargs="?", const="",
                        help="resolve crm.tag ids (comma-separated) to names "
                             "with lead counts; bare --tags lists the biggest")
    parser.add_argument("--action", metavar="NAME",
                        help="print the code of server actions whose name "
                             "matches NAME (substring, case-insensitive)")
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
        if args.schema:
            report = show_schema(args.db, args.schema)
        elif args.projects:
            report = show_projects(args.db)
        elif args.tags is not None:
            ids = [int(x) for x in args.tags.split(",") if x.strip()] or None
            report = show_tags(args.db, ids)
        elif args.action:
            report = show_action(args.db, args.action)
        elif args.diagnose:
            report = diagnose(args.db)
        elif args.leads:
            report = analyse_leads(args.db)
        else:
            report = inspect(args.db)
    except Exception as exc:
        print(f"Inspection failed for '{args.db}': {summarise_error(exc)}",
              file=sys.stderr)
        print(hint_for(exc, args.db), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        if args.schema:
            print(render_schema(report))
        elif args.projects:
            print(render_projects(report))
        elif args.tags is not None:
            print(render_tags(report))
        elif args.action:
            print(render_action(report))
        elif args.diagnose:
            print(render_diagnose(report))
        elif args.leads:
            print(render_leads(report))
        else:
            print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
