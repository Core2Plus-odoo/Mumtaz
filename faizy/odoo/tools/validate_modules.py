#!/usr/bin/env python3
"""Static validation for the Faizy Odoo modules.

Installing Odoo itself in CI is heavy and slow, but most of what breaks a module
is catchable without it: a typo in a manifest, malformed XML, a data file that
was renamed but not updated in the manifest, a model with no ACL, an ACL
pointing at a model that does not exist, or a view referencing a field the model
never declares.

This checks all of that with the standard library alone.

    python3 faizy/odoo/tools/validate_modules.py

Exits non-zero on the first category of failure, printing every instance.
It is a smoke test, not a substitute for installing the module — do that on a
staging database before releasing.
"""

from __future__ import annotations

import ast
import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ADDONS = Path(__file__).resolve().parents[1] / "addons"

# Fields every Odoo model has without declaring them.
INHERITED_FIELDS = {
    "id",
    "display_name",
    "create_date",
    "create_uid",
    "write_date",
    "write_uid",
    "__last_update",
    # mail.thread / mail.activity.mixin
    "message_ids",
    "message_follower_ids",
    "activity_ids",
    "activity_state",
    "activity_user_id",
    "message_needaction",
    "rating_ids",
}


def module_dirs() -> list[Path]:
    return sorted(p for p in ADDONS.iterdir() if (p / "__manifest__.py").exists())


def parse_manifest(module: Path) -> dict:
    return ast.literal_eval((module / "__manifest__.py").read_text())


# Fields these mixins already define. Redeclaring one shadows the mixin's, which
# breaks the related fields that resolve through it — the registry then fails at
# install time with a KeyError that names the RELATED field, not the one you
# actually redeclared. Cost a deploy cycle once; hence this check.
MIXIN_FIELDS = {
    "mail.thread": {
        "message_ids", "message_follower_ids", "message_partner_ids",
        "message_is_follower", "message_unread", "message_unread_counter",
        "message_needaction", "message_needaction_counter", "message_has_error",
        "message_has_error_counter", "message_attachment_count",
        "message_main_attachment_id", "website_message_ids", "message_has_sms_error",
    },
    "mail.activity.mixin": {
        "activity_ids", "activity_state", "activity_user_id", "activity_type_id",
        "activity_type_icon", "activity_date_deadline", "my_activity_date_deadline",
        "activity_summary", "activity_exception_decoration",
        "activity_exception_icon", "activity_calendar_event_id",
    },
}


def collect_models(module: Path) -> dict[str, dict]:
    """Map model name -> {"fields", "inherits"}, read from the source.

    Deliberately regex-based rather than importing: importing needs Odoo on the
    path, which is the dependency this script exists to avoid.
    """
    models: dict[str, dict] = {}
    for py in (module / "models").glob("*.py") if (module / "models").exists() else []:
        source = py.read_text()
        # Split on class boundaries so fields land against the right model.
        for block in re.split(r"\nclass\s+\w+\(", source)[1:]:
            name_match = re.search(r'_name\s*=\s*["\']([\w.]+)["\']', block)
            # Both spellings: _inherit = "x" and _inherit = ["x", "y"].
            inherit_single = re.search(r'_inherit\s*=\s*["\']([\w.]+)["\']', block)
            inherit_list = re.search(r"_inherit\s*=\s*\[([^\]]*)\]", block)

            inherits = set()
            if inherit_list:
                inherits = set(re.findall(r'["\']([\w.]+)["\']', inherit_list.group(1)))
            elif inherit_single:
                inherits = {inherit_single.group(1)}

            model = name_match.group(1) if name_match else (
                inherit_single.group(1) if inherit_single else None
            )
            if not model:
                continue

            fields = set(re.findall(r"^\s{4}(\w+)\s*=\s*fields\.", block, re.MULTILINE))
            entry = models.setdefault(model, {"fields": set(), "inherits": set()})
            entry["fields"].update(fields)
            entry["inherits"].update(inherits)
    return models


def main() -> int:
    failures: list[str] = []
    all_models: dict[str, set[str]] = {}

    modules = module_dirs()
    if not modules:
        print("No modules found — is the addons path right?")
        return 1

    for module in modules:
        name = module.name
        manifest = parse_manifest(module)

        # 1. Declared data files must exist.
        for rel in manifest.get("data", []):
            if not (module / rel).exists():
                failures.append(f"{name}: manifest lists missing data file {rel}")

        # 2. Declared assets must exist.
        for bundle in manifest.get("assets", {}).values():
            for asset in bundle:
                # Asset paths are "module_name/path/inside/module".
                parts = asset.split("/", 1)
                if len(parts) == 2 and not (ADDONS / parts[0] / parts[1]).exists():
                    failures.append(f"{name}: manifest lists missing asset {asset}")

        # 3. Every XML file must parse.
        for xml_file in module.rglob("*.xml"):
            try:
                ET.parse(xml_file)
            except ET.ParseError as err:
                failures.append(f"{name}: {xml_file.relative_to(module)} — {err}")

        models = collect_models(module)
        all_models.update(models)

        # 4a. A declared field must not shadow one its mixins already define.
        for model_name, info in models.items():
            for mixin in info["inherits"]:
                clashes = info["fields"] & MIXIN_FIELDS.get(mixin, set())
                for field_name in sorted(clashes):
                    failures.append(
                        f"{name}: {model_name}.{field_name} shadows a field from "
                        f"{mixin} — rename it, or the registry fails at install"
                    )

        # 4. ACLs: every own model covered, every reference resolvable.
        acl_path = module / "security" / "ir.model.access.csv"
        if acl_path.exists():
            rows = list(csv.DictReader(acl_path.open()))
            own = {f"model_{m.replace('.', '_')}" for m in models if "." in m}
            referenced = {r["model_id:id"].split(".")[-1] for r in rows}
            for ref in referenced:
                if ref.startswith("model_faizy") and ref not in own:
                    failures.append(f"{name}: ACL references unknown model {ref}")
            for model_ref in own:
                # Inherited models (res.partner) legitimately need no ACL.
                base = model_ref.removeprefix("model_")
                if base.startswith("faizy") and model_ref not in referenced:
                    failures.append(f"{name}: model {base} has no ACL entry")

    # 5. Views must only reference fields the model declares.
    for module in modules:
        for xml_file in (module / "views").rglob("*.xml") if (module / "views").exists() else []:
            try:
                tree = ET.parse(xml_file)
            except ET.ParseError:
                continue  # already reported above
            for record in tree.iter("record"):
                if record.get("model") != "ir.ui.view":
                    continue
                model_field = record.find("./field[@name='model']")
                if model_field is None or not model_field.text:
                    continue
                model_name = model_field.text.strip()
                declared = (all_models.get(model_name) or {}).get("fields")
                # Only check models this codebase defines; core Odoo models
                # have fields we cannot see from here.
                if not declared or not model_name.startswith("faizy."):
                    continue
                arch = record.find("./field[@name='arch']")
                if arch is None:
                    continue

                def walk(node, inside_subview: bool) -> None:
                    """Check field names belonging to THIS model only.

                    Two things must not be checked: the <field name="arch">
                    wrapper itself, and anything nested inside another <field>,
                    because a nested list/form describes a RELATED model's
                    fields (e.g. activity_ids -> faizy.activity.log). Starting
                    from arch's children skips the first; the flag skips the
                    second.
                    """
                    for child in node:
                        if child.tag == "field":
                            fname = child.get("name")
                            if (
                                not inside_subview
                                and fname
                                and "." not in fname
                                and fname not in declared
                                and fname not in INHERITED_FIELDS
                            ):
                                failures.append(
                                    f"{module.name}: {xml_file.name} references "
                                    f"{model_name}.{fname}, which the model does "
                                    f"not declare"
                                )
                            walk(child, True)
                        else:
                            walk(child, inside_subview)

                walk(arch, False)

    print(f"Checked {len(modules)} module(s): {', '.join(m.name for m in modules)}")
    print(f"Models found: {len([m for m in all_models if m.startswith('faizy.')])}")

    if failures:
        print(f"\n{len(failures)} problem(s):\n")
        for failure in failures:
            print(f"  ✗ {failure}")
        return 1

    print("\nOK — manifests, XML, ACLs and view field references all check out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
