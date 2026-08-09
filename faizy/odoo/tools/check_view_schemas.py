#!/usr/bin/env python3
"""Validate view definitions against Odoo's own RelaxNG schemas.

Odoo validates every view at install time against `base/rng/<type>_view.rng`.
When a view fails, the install dies with an RNG error naming a line inside a
generated string — you get "Invalid attribute expand for element group" and a
file name, but not the file's line, and nothing offline catches it first.

This runs the same schemas over the same view definitions, before deploying.

    python3 faizy/odoo/tools/check_view_schemas.py             # fetch from GitHub
    python3 faizy/odoo/tools/check_view_schemas.py --odoo /opt/faizy/odoo

Odoo only ships RNG for some view types — search, list, calendar, pivot, graph.
Form and kanban are validated in Python instead, so they are skipped here rather
than waved through with a pretend check.

Requires lxml (RelaxNG is not in the standard library). If lxml is missing the
check reports that and exits 0, so it degrades to a no-op instead of blocking.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

ADDONS = Path(__file__).resolve().parents[1] / "addons"
ODOO_VERSION = "19.0"
RNG_DIR = "odoo/addons/base/rng"
RAW = f"https://raw.githubusercontent.com/odoo/odoo/{ODOO_VERSION}/{RNG_DIR}"

# Types Odoo ships an RNG for. common.rng is included by the others by relative
# href, so it has to land beside them.
VIEW_TYPES = ["search", "list", "calendar", "pivot", "graph"]
SUPPORT = ["common.rng"]


def fetch_schemas(dest: Path, odoo_root: Path | None) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    got = []
    wanted = [f"{t}_view.rng" for t in VIEW_TYPES] + SUPPORT

    for filename in wanted:
        target = dest / filename
        if odoo_root:
            source = odoo_root / RNG_DIR / filename
            if source.exists():
                target.write_bytes(source.read_bytes())
                got.append(filename)
            continue
        try:
            with urllib.request.urlopen(f"{RAW}/{filename}", timeout=30) as resp:
                body = resp.read()
            # A 404 page is not a schema; guard against writing HTML.
            if body.lstrip().startswith(b"<?xml") or body.lstrip().startswith(b"<rng"):
                target.write_bytes(body)
                got.append(filename)
        except Exception as err:  # noqa: BLE001 - network is best-effort
            print(f"  ! could not fetch {filename}: {err}", file=sys.stderr)
    return got


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odoo", type=Path, help="Path to an Odoo checkout")
    parser.add_argument("--cache", type=Path, default=Path("/tmp/faizy-rng"))
    args = parser.parse_args()

    try:
        from lxml import etree
    except ImportError:
        print("lxml not installed — skipping view schema validation.")
        print("Install it with: pip install lxml")
        return 0

    print(f"Fetching Odoo {ODOO_VERSION} view schemas "
          f"({'from ' + str(args.odoo) if args.odoo else 'from GitHub'})")
    got = fetch_schemas(args.cache, args.odoo)
    if not got:
        print("No schemas available — skipping.")
        return 0

    schemas = {}
    for view_type in VIEW_TYPES:
        path = args.cache / f"{view_type}_view.rng"
        if not path.exists():
            continue
        try:
            schemas[view_type] = etree.RelaxNG(etree.parse(str(path)))
        except Exception as err:  # noqa: BLE001
            print(f"  ! {path.name} did not load: {err}", file=sys.stderr)

    print(f"Validating against: {', '.join(sorted(schemas)) or 'nothing'}\n")
    if not schemas:
        return 0

    problems = 0
    checked = 0
    for xml_file in sorted(ADDONS.glob("*/views/*.xml")):
        tree = etree.parse(str(xml_file))
        for record in tree.iter("record"):
            if record.get("model") != "ir.ui.view":
                continue
            arch = record.find("./field[@name='arch']")
            if arch is None:
                continue
            for root in arch:
                schema = schemas.get(root.tag)
                if schema is None:
                    continue  # form/kanban: validated in Python, not RNG
                checked += 1
                if schema.validate(root):
                    continue
                problems += 1
                rel = xml_file.relative_to(ADDONS)
                print(f"  ✗ {rel} :: {record.get('id')} (<{root.tag}>)")
                for entry in schema.error_log:
                    print(f"      {entry.message}")
                print()

    print(f"Checked {checked} view(s) with a schema.")
    if problems:
        print(f"{problems} invalid view(s) — Odoo will refuse these at install.")
        return 1

    print("OK — every schema-backed view validates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
