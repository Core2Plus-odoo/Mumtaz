#!/usr/bin/env python3
"""Assert every `self.<attr>` on a Faizy model resolves to something declared.

Written after `_check_exchange_rate` shipped to production reading
`self.company_id or self.env.company` — an idiom copied from `faizy.order`,
which declares `company_id`. `faizy.subscription` does not. Python raises
`AttributeError` only when the line runs, and that line runs inside the guard
that gates invoicing, so the effect on the live database was that every
non-PKR invoice was refused with the message

    'faizy.subscription' object has no attribute 'company_id'

The guard appeared to work: the currencies it was meant to block were blocked.
It kept blocking them after the exchange rates were entered, and would have
kept blocking them forever, because the check never got as far as looking at a
rate. Nothing in compileall, flake8 or Odoo's own view validation sees this —
attribute access on a recordset is resolved at runtime against fields the ORM
assembles from every module in the graph.

Scope, deliberately narrow. Only classes that declare `_name` and inherit
nothing but mixins are examined: those are Faizy's own models, where every
field is declared in the same class, so an index built from that one file is
complete. Classes that `_inherit` a real model (`res.partner`, `res.company`,
`res.config.settings`) are skipped entirely — their fields come from a dozen
modules this cannot see, and indexing them is exactly how an earlier attempt at
a field checker produced 28 findings of which 28 were wrong. A checker that
cries wolf gets switched off.

    python3 faizy/odoo/tools/check_self_fields.py
"""

from __future__ import annotations

import ast
import pathlib
import sys

# Inheriting one of these adds attributes, all of which are in ALLOW below.
# Inheriting anything else means the model's fields are not knowable from here.
MIXINS = {
    "mail.thread",
    "mail.activity.mixin",
    "mail.thread.blacklist",
    "portal.mixin",
    "image.mixin",
}

# What every recordset carries from the ORM itself.
ORM = {
    "env", "id", "ids", "_name", "_description", "_inherit", "_order", "_rec_name",
    "ensure_one", "browse", "search", "search_count", "search_read", "search_fetch",
    "read", "create", "write", "unlink", "copy", "exists", "filtered",
    "filtered_domain", "mapped", "sorted", "grouped", "sudo", "with_context",
    "with_company", "with_user", "with_env", "with_prefetch", "read_group",
    "_read_group", "flush_recordset", "invalidate_recordset", "fetch",
    "display_name", "create_date", "write_date", "create_uid", "write_uid",
    "_fields", "_table", "_cr", "_uid", "_context", "_origin", "_field_to_sql",
    "_as_query", "_search", "fields_get", "default_get", "check_access",
    "check_access_rule", "check_access_rights", "_compute_display_name",
    "_valid_field_parameter", "_prepare_create_values", "_load_records",
}

# What mail.thread / mail.activity.mixin add. Only consulted for classes that
# actually inherit them, but kept as one set because a model that does not
# inherit mail.thread and calls message_post is broken anyway.
MAIL = {
    "message_post", "message_ids", "message_follower_ids", "message_subscribe",
    "message_unsubscribe", "message_notify", "message_main_attachment_id",
    "message_has_error", "message_is_follower", "message_needaction",
    "message_attachment_count", "has_message", "website_message_ids",
    "_track_subtype", "_message_get_suggested_recipients", "_message_auto_subscribe",
    "activity_ids", "activity_schedule", "activity_state", "activity_user_id",
    "activity_type_id", "activity_date_deadline", "activity_summary",
    "activity_exception_decoration", "activity_exception_icon",
}

ALLOW = ORM | MAIL


def _inherit_targets(value: ast.expr) -> list[str]:
    if isinstance(value, (ast.List, ast.Tuple)):
        return [e.value for e in value.elts if isinstance(e, ast.Constant)]
    if isinstance(value, ast.Constant):
        return [value.value]
    return ["<computed>"]  # unparseable — treat as foreign, i.e. skip the class


def declared(cls: ast.ClassDef) -> tuple[set[str], str | None, bool]:
    """Return (names assigned or defined in the class, _name, inherits_foreign)."""
    names: set[str] = set()
    model_name: str | None = None
    foreign = False
    for node in cls.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if not isinstance(tgt, ast.Name):
                    continue
                if tgt.id == "_name" and isinstance(node.value, ast.Constant):
                    model_name = node.value.value
                elif tgt.id == "_inherit":
                    foreign = any(t not in MIXINS for t in _inherit_targets(node.value))
                # Every class-level assignment is reachable as self.<name>:
                # fields.Char(...) and plain constants like BILLABLE_STATES alike.
                names.add(tgt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names, model_name, foreign


def check(root: pathlib.Path) -> list[tuple[str, int, str, str]]:
    findings = []
    for path in sorted(root.rglob("models/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            names, model_name, foreign = declared(cls)
            if not model_name or foreign:
                continue
            known = names | ALLOW
            for node in ast.walk(cls):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "self"
                    and node.attr not in known
                ):
                    rel = path.relative_to(root.parent) if root.parent in path.parents else path
                    findings.append((str(rel), node.lineno, model_name, node.attr))
    return findings


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent.parent / "addons"
    if len(sys.argv) > 1:
        root = pathlib.Path(sys.argv[1])

    findings = check(root)
    models = {f[2] for f in findings}
    if findings:
        print(f"{len(findings)} undeclared attribute(s) on {len(models)} model(s):\n")
        for rel, line, model_name, attr in findings:
            print(f"  ✗ {rel}:{line}  {model_name} has no `{attr}`")
        print(
            "\nEach of these raises AttributeError when the line runs, not at "
            "install. Declare the field, or use the right source for the value."
        )
        return 1

    print("OK — every self.<attr> on a Faizy model resolves to a declared field, "
          "constant or method.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
