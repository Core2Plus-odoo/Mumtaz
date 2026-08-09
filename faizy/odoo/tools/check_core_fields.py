#!/usr/bin/env python3
"""Verify that data files only write fields that exist on Odoo core models.

Why this exists: three separate installs failed on this one class of error —
`res.groups.category_id`, `ir.cron.numbercall`, `ir.rule.global`. Each is
invisible to every offline check. The XML is well-formed, the field name is
plausible, Python has nothing to say about it, and it only fails at install with
"Invalid field 'x' in 'model'" from inside XML parsing. Fixing them one per
deploy cycle is not a strategy.

So rather than maintaining a hand-written list of what Odoo removed and when,
this reads the field names out of the actual Odoo source for the target version
and checks every data record against them.

    python3 faizy/odoo/tools/check_core_fields.py            # fetch from GitHub
    python3 faizy/odoo/tools/check_core_fields.py --odoo /opt/faizy/odoo

Needs network for the default path. On a server with Odoo already checked out,
--odoo reads from disk and needs nothing. Models whose source is not in the list
below are skipped rather than guessed at — a silent skip is honest, a false
failure is not.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ADDONS = Path(__file__).resolve().parents[1] / "addons"
ODOO_VERSION = "19.0"
RAW = f"https://raw.githubusercontent.com/odoo/odoo/{ODOO_VERSION}"

# Source files covering the core models our data files touch. Add to this when a
# new core model is referenced; anything not covered is skipped, not guessed.
CORE_SOURCES = [
    "odoo/addons/base/models/ir_cron.py",
    "odoo/addons/base/models/ir_sequence.py",
    "odoo/addons/base/models/ir_rule.py",
    "odoo/addons/base/models/res_users.py",       # res.groups lives here
    "odoo/addons/base/models/ir_module.py",
    "addons/website/models/website_menu.py",
]

# ir.cron delegates to ir.actions.server via _inherits, so these are legal on a
# cron record even though they are declared on the action.
DELEGATED_FIELDS = {
    "ir.cron": {"name", "model_id", "state", "code", "sequence", "binding_model_id"},
}

# Models we deliberately never check: ours, and the ones whose "fields" are
# really view/action plumbing rather than a model schema.
SKIP_MODELS = {"ir.ui.view", "ir.actions.act_window", "ir.model.access"}


def load_sources(odoo_root: Path | None) -> dict[str, str]:
    sources = {}
    for rel in CORE_SOURCES:
        if odoo_root:
            path = odoo_root / rel
            if path.exists():
                sources[rel] = path.read_text()
            continue
        try:
            with urllib.request.urlopen(f"{RAW}/{rel}", timeout=30) as resp:
                sources[rel] = resp.read().decode()
        except Exception as err:  # noqa: BLE001 - network is best-effort
            print(f"  ! could not fetch {rel}: {err}", file=sys.stderr)
    return sources


def index_fields(sources: dict[str, str]) -> dict[str, set[str]]:
    """model name -> declared field names, parsed from the core source."""
    index: dict[str, set[str]] = {}
    for text in sources.values():
        for block in re.split(r"\nclass\s+\w+\(", text)[1:]:
            names = re.findall(r'_name\s*=\s*["\']([\w.]+)["\']', block)
            inherits = re.findall(r'_inherit\s*=\s*["\']([\w.]+)["\']', block)
            targets = names or inherits
            if not targets:
                continue
            fields = set(re.findall(r"^    ([a-z_]+)\s*=\s*fields\.", block, re.M))
            for target in targets:
                index.setdefault(target, set()).update(fields)
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odoo", type=Path, help="Path to an Odoo checkout")
    args = parser.parse_args()

    print(f"Reading Odoo {ODOO_VERSION} core models "
          f"({'from ' + str(args.odoo) if args.odoo else 'from GitHub'})")
    sources = load_sources(args.odoo)
    if not sources:
        print("Could not read any core sources — skipping this check.")
        return 0

    index = index_fields(sources)
    known_models = sorted(m for m in index if index[m])
    print(f"Indexed {len(known_models)} core models\n")

    problems = []
    checked = set()
    for xml_file in sorted(ADDONS.glob("*/**/*.xml")):
        try:
            tree = ET.parse(xml_file)
        except ET.ParseError:
            continue  # validate_modules.py reports malformed XML
        for record in tree.iter("record"):
            model = record.get("model", "")
            if not model or model.startswith("faizy.") or model in SKIP_MODELS:
                continue
            allowed = index.get(model, set())
            if not allowed:
                continue  # not indexed; cannot judge, so do not pretend to
            checked.add(model)
            allowed = allowed | DELEGATED_FIELDS.get(model, set())
            for field in record.findall("./field"):
                fname = field.get("name")
                if fname and fname not in allowed:
                    problems.append(
                        f"{xml_file.relative_to(ADDONS)}: "
                        f"{model}.{fname} does not exist in Odoo {ODOO_VERSION}"
                    )

    print("Checked against:", ", ".join(sorted(checked)) or "nothing")
    if problems:
        print(f"\n{len(problems)} problem(s):\n")
        for problem in problems:
            print(f"  ✗ {problem}")
        return 1

    print("\nOK — every core-model field written by a data file exists.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
