"""Built-in Technical intelligence — Odoo development standards (v16–v19).

What a senior Odoo developer holds in their head: module anatomy, ORM and
inheritance patterns, view extension, security, performance, integration
patterns, version differences and the upgrade-safe checklist. `digest()` embeds
it in the developer agent; `review_module()` runs a local best-practice review
over generated module files (beyond the structural manifest/syntax check).
"""
from __future__ import annotations

import re

MODULE_ANATOMY = (
    "module/__manifest__.py (name, version, depends, data, license), __init__.py, "
    "models/ (Python, _inherit standard models), views/ (XML, xpath-extend standard "
    "views), security/ir.model.access.csv (+ record rules XML), data/ (master data, "
    "noupdate=1 where user-editable), reports/, static/, tests/ (odoo.tests.common)."
)

ORM_RULES = [
    "Inherit, never recreate: `_inherit = 'sale.order'` extends; a new model only for a "
    "genuinely new concept — and then link it (Many2one) to the standard flow.",
    "Mixins: `mail.thread` + `mail.activity.mixin` on any business model (chatter, "
    "activities); `portal.mixin` if customers see it.",
    "Compute: @api.depends stored compute over onchange where possible; never heavy "
    "compute without store=True on list views.",
    "Recordset discipline: batch with mapped/filtered; NEVER search/browse inside a loop "
    "(N+1); use read_group for aggregates.",
    "Constraints: @api.constrains for business rules; SQL constraints for uniqueness.",
    "No raw SQL unless unavoidable; if used, keep it injection-safe and document why.",
    "Use sudo() surgically and comment why; respect multi-company via company_id + "
    "check_company=True.",
]

VIEW_RULES = [
    "Extend with xpath on the standard view (inherit_id), don't replace views.",
    "v17+: inline attributes `invisible=\"state != 'draft'\"`, `<list>` tag; "
    "v16: `attrs=\"{'invisible': [...]}\"`, `<tree>` tag.",
    "Buttons call model methods (server actions for simple cases); statusbar for states.",
]

SECURITY_RULES = [
    "Every new model ships ir.model.access.csv (per group: read/write/create/unlink).",
    "Record rules for row-level scoping (company, team, own-records).",
    "Never grant group_system broadly; map to functional groups (sales user/manager …).",
]

INTEGRATION_PATTERNS = [
    "Inbound: REST controller (@http.route auth='user'/'api_key', type='json') or "
    "standard XML-RPC; validate and log every payload.",
    "Outbound: queued job/cron with idempotency keys and retry+backoff; never call "
    "external APIs synchronously inside onchange/compute.",
    "Webhooks: verify signatures, respond fast, process async.",
    "Store mappings (external_id ↔ odoo id) in a dedicated model; sync must be re-runnable.",
]

PERFORMANCE_RULES = [
    "Index searched fields (index=True); paginate; prefetch via recordsets not loops.",
    "Cron batches with commit windows for large volumes; guard with queue locks.",
    "Profile before optimising: --log-sql / profiler; suspect compute+store first.",
]

UPGRADE_SAFE = [
    "No monkey-patching; no core-file edits — ever.",
    "Feature-flag risky behaviour via ir.config_parameter.",
    "Migrations: use openupgrade-style migrate scripts per version bump.",
    "Pin depends minimal; every dependency is upgrade surface.",
    "Tests: at least a smoke TransactionCase per model + the critical business flow.",
]

VERSION_NOTES = (
    "v16: attrs/states syntax, tree tag, 'Automated Actions'. v17: new UI, list tag, "
    "inline attrs, ir.actions.act_window target=inline REMOVED. v18/19: further ORM "
    "tightening — @api.model_create_multi default, stricter access on compute; "
    "'Automation Rules' naming; check enterprise app renames per release."
)

DEPLOY_ODOOSH = [
    "Branch flow: feature → staging build (test with prod data copy) → merge to "
    "production; never push straight to production.",
    "Module updates: bump version in manifest so -u runs; keep data migrations in module.",
    "Logs: odoo.log via odoosh shell/lnav; monitor build status after every push.",
]

REVIEW_CHECKLIST = [
    "Manifest sane (name/version/depends/license/data files all exist)",
    "Models inherit standard where possible; new models linked to standard flow",
    "chatter/activity mixins on business models",
    "Access CSV present for every new model; record rules where scoping needed",
    "Views extend via xpath; version-correct syntax",
    "No search/browse in loops; no raw SQL without justification",
    "Multi-company safe (company_id / check_company)",
    "Tests present; no hardcoded ids/values; translations via _()",
]


def review_module(files: list) -> list:
    """Local best-practice review of generated module files. Returns warnings
    (empty = clean). Complements the structural manifest/syntax check."""
    warns: list[str] = []
    pys = [(f.get("path", ""), f.get("content", "")) for f in files or []
           if (f.get("path") or "").endswith(".py")]
    xmls = [(f.get("path", ""), f.get("content", "")) for f in files or []
            if (f.get("path") or "").endswith(".xml")]
    all_py = "\n".join(c for _, c in pys)

    has_new_model = re.search(r"_name\s*=\s*['\"][\w.]+['\"]", all_py)
    if has_new_model and not any("ir.model.access" in (f.get("path") or "")
                                 for f in files or []):
        warns.append("New model defined but no security/ir.model.access.csv shipped.")
    if has_new_model and "mail.thread" not in all_py:
        warns.append("New business model without mail.thread/activity mixins (no chatter).")
    for path, c in pys:
        if re.search(r"for\s+\w+\s+in[^\n]*:\s*\n(?:[^\n]*\n){0,3}[^\n]*\.(search|browse)\(", c):
            warns.append(f"Possible search/browse inside a loop in {path} (N+1).")
        if ".sudo()" in c and "# why" not in c and "# sudo" not in c.lower():
            warns.append(f"sudo() in {path} without a justifying comment.")
        if re.search(r"self\.env\.cr\.execute\(", c):
            warns.append(f"Raw SQL in {path} — verify injection-safety and necessity.")
    for path, c in xmls:
        if "attrs=" in c and "17" not in path:
            warns.append(f"v16-style attrs= in {path} — use inline invisible/readonly on v17+.")
        if "<tree" in c:
            warns.append(f"<tree> tag in {path} — v17+ uses <list>.")
        if 'target="inline"' in c:
            warns.append(f"target='inline' in {path} — removed in v18/19.")
    if pys and not any("tests/" in (f.get("path") or "") for f in files or []):
        warns.append("No tests/ shipped — add at least a smoke TransactionCase.")
    return warns[:10]


def digest() -> str:
    """Compact Odoo development-standards reference for the developer agent."""
    return ("ODOO DEVELOPMENT STANDARDS (C2P, v16–v19).\n"
            f"Module anatomy: {MODULE_ANATOMY}\n"
            "ORM: " + " ".join(ORM_RULES[:5]) + "\n"
            "Views: " + " ".join(VIEW_RULES) + "\n"
            "Security: " + " ".join(SECURITY_RULES) + "\n"
            "Integrations: " + " ".join(INTEGRATION_PATTERNS[:3]) + "\n"
            "Performance: " + " ".join(PERFORMANCE_RULES[:2]) + "\n"
            "Upgrade-safe: " + " ".join(UPGRADE_SAFE[:4]) + "\n"
            f"Version notes: {VERSION_NOTES}\n"
            "Odoo.sh: " + " ".join(DEPLOY_ODOOSH[:2]) + "\n"
            "Ship every module able to pass this review: " + "; ".join(REVIEW_CHECKLIST))
