#!/usr/bin/env python3
"""Assert every model a portal template reads is readable by portal users.

Written after `/my/orders/<id>` returned a 500 to the first real customer who
opened it:

    You are not allowed to access 'Faizy Service' (faizy.service) records.

The template had always contained `t-out="order.service_id.name"`. Reading a
Many2one *field* on faizy.order is allowed; following it and reading a field on
the far side is a read of the far model, and `base.group_portal` had no ACL row
for faizy.service. The same was true of faizy.plan on /my/care. Neither shows
up in any other check: the XML is valid, the field exists, the view renders
perfectly as an internal user — and every internal user, including the one
doing the testing, bypasses it.

What this does: builds `model → {field: comodel}` from the addon's own model
definitions, reads which models `base.group_portal` may read from
ir.model.access.csv, then walks the portal templates for `var.field_id.x`
and reports any hop that lands on a model portal users cannot read.

`ROOTS` maps the template variable names to their models. It is written by
hand on purpose — inferring it would mean interpreting the controllers, and a
short explicit table that some human keeps honest beats a clever one that is
subtly wrong. A variable not in ROOTS is skipped rather than guessed at.

Values the controller passes in already-resolved (`worker_name`, computed with
sudo precisely so the model need not be opened) are plain strings and never
match the dotted pattern, so they are correctly invisible here.

    python3 faizy/odoo/tools/check_portal_access.py
"""

from __future__ import annotations

import ast
import csv
import pathlib
import re
import sys

PORTAL_GROUP = "base.group_portal"

# Template variable → the model it holds. Kept short and explicit.
ROOTS = {
    "order": "faizy.order",
    "subscription": "faizy.subscription",
    "member": "faizy.family.member",
    "partner": "res.partner",
    "service": "faizy.service",
    "category": "faizy.service.category",
}

# Models outside the addon. Core Odoo grants portal users read on these itself,
# so the addon's own ACL file is not where they would appear.
EXTERNAL_OK = {"res.partner", "res.currency", "res.company", "res.users"}

RELATIONAL = {"Many2one", "One2many", "Many2many"}


def field_map(addons: pathlib.Path) -> dict[str, dict[str, str]]:
    """{model: {field: comodel}} for every model the addon declares."""
    out: dict[str, dict[str, str]] = {}
    for path in sorted(addons.rglob("models/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            model = None
            fields: dict[str, str] = {}
            for node in cls.body:
                if not isinstance(node, ast.Assign):
                    continue
                for tgt in node.targets:
                    if not isinstance(tgt, ast.Name):
                        continue
                    if tgt.id == "_name" and isinstance(node.value, ast.Constant):
                        model = node.value.value
                    v = node.value
                    if (
                        isinstance(v, ast.Call)
                        and isinstance(v.func, ast.Attribute)
                        and v.func.attr in RELATIONAL
                        and v.args
                        and isinstance(v.args[0], ast.Constant)
                    ):
                        fields[tgt.id] = v.args[0].value
            if model:
                out.setdefault(model, {}).update(fields)
    return out


def portal_readable(csv_path: pathlib.Path) -> set[str]:
    models = set()
    with csv_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["group_id:id"] == PORTAL_GROUP and row["perm_read"] == "1":
                models.add(row["model_id:id"].replace("model_", "").replace("_", "."))
    return models


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent.parent
    addons = root / "addons"
    fields = field_map(addons)
    readable = portal_readable(addons / "faizy_core/security/ir.model.access.csv")

    findings = []
    for path in sorted(addons.rglob("views/*portal*.xml")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.split("\n"), 1):
            # order.service_id.name  /  subscription.plan_id.overage_display
            for var, field, _rest in re.findall(
                r"\b(\w+)\.(\w+_ids?)\.(\w+)", line
            ):
                model = ROOTS.get(var)
                if not model:
                    continue
                comodel = fields.get(model, {}).get(field)
                if not comodel or comodel in EXTERNAL_OK or comodel in readable:
                    continue
                findings.append(
                    (str(path.relative_to(root)), lineno, var, field, comodel)
                )

    seen, unique = set(), []
    for f in findings:
        key = (f[0], f[3], f[4])
        if key not in seen:
            seen.add(key)
            unique.append(f)

    if unique:
        print(f"{len(unique)} portal read(s) with no portal ACL:\n")
        for rel, lineno, var, field, comodel in unique:
            print(f"  ✗ {rel}:{lineno}  {var}.{field} reads {comodel}, "
                  f"which {PORTAL_GROUP} cannot read")
        print(
            "\nEach is a 500 for a real customer and renders perfectly for you,\n"
            "because an internal user bypasses the ACL. Either grant portal read\n"
            "in ir.model.access.csv, or resolve the value in the controller with\n"
            "sudo() and pass it in — the second if the model carries anything the\n"
            "customer should not have."
        )
        return 1

    print(f"OK — every model reached from a portal template is readable by "
          f"{PORTAL_GROUP} ({len(readable)} granted).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
