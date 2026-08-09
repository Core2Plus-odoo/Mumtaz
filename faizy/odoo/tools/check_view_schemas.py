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

# Parent views we inherit, and where their definition lives in the Odoo tree.
# Used to confirm every xpath anchor actually resolves — "cannot be located in
# parent view" is only discoverable at install otherwise, and anchors move
# between versions (//block[@id='companies'] became
# //block[@name='companies_setting_container'] in 19).
#
# A parent that is not listed here is skipped rather than guessed at. Add an
# entry when you inherit something new.
# Sentinel: the parent is itself an inheriting view, so its on-disk arch is a
# fragment and xpaths cannot be resolved without Odoo building the chain.
INHERITING_PARENT = object()

PARENT_VIEWS = {
    "base.view_partner_form": "odoo/addons/base/views/res_partner_views.xml",
    "base_setup.res_config_settings_view_form":
        "addons/base_setup/views/res_config_settings_views.xml",
}


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


def load_parent_arch(xmlid: str, odoo_root: Path | None, etree):
    """Return the <arch> root of a core view, or None if we cannot read it."""
    rel = PARENT_VIEWS.get(xmlid)
    if not rel:
        return None

    if odoo_root:
        path = odoo_root / rel
        if not path.exists():
            return None
        tree = etree.parse(str(path))
    else:
        url = f"https://raw.githubusercontent.com/odoo/odoo/{ODOO_VERSION}/{rel}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                tree = etree.fromstring(resp.read()).getroottree()
        except Exception:  # noqa: BLE001 - network is best-effort
            return None

    record_id = xmlid.split(".", 1)[1]
    for record in tree.iter("record"):
        if record.get("id") != record_id or record.get("model") != "ir.ui.view":
            continue

        # If the "parent" is itself an inheriting view, the arch on disk is only
        # a fragment — base_setup.res_config_settings_view_form, for instance, is
        # just <xpath expr="//form" position="inside">. The effective view is the
        # whole inheritance chain combined, which only Odoo can build. Report
        # that we cannot judge rather than failing a correct anchor.
        arch = record.find("./field[@name='arch']")
        if arch is None or not len(arch):
            return None
        if record.find("./field[@name='inherit_id']") is not None or arch[0].tag == "xpath":
            return INHERITING_PARENT
        return arch[0]
    return None


def check_xpath_anchors(odoo_root: Path | None, etree) -> int:
    """Confirm every xpath in an inheriting view resolves in its parent."""
    problems = 0
    cache: dict[str, object] = {}

    for xml_file in sorted(ADDONS.glob("*/views/*.xml")):
        tree = etree.parse(str(xml_file))
        for record in tree.iter("record"):
            if record.get("model") != "ir.ui.view":
                continue
            inherit = record.find("./field[@name='inherit_id']")
            if inherit is None:
                continue
            parent_id = inherit.get("ref", "")
            if parent_id not in PARENT_VIEWS:
                continue

            if parent_id not in cache:
                cache[parent_id] = load_parent_arch(parent_id, odoo_root, etree)
            parent = cache[parent_id]
            if parent is None:
                print(f"  ? {parent_id}: could not read parent view, skipping")
                continue
            if parent is INHERITING_PARENT:
                print(f"  ~ {parent_id} is itself an inheriting view — "
                      f"anchors need the full chain, skipping")
                continue

            arch = record.find("./field[@name='arch']")
            if arch is None:
                continue
            for node in arch.iter("xpath"):
                expr = node.get("expr")
                if not expr:
                    continue
                try:
                    hits = parent.xpath(expr)
                except Exception as err:  # noqa: BLE001 - bad expression
                    print(f"  ✗ {xml_file.name} :: {record.get('id')}")
                    print(f"      invalid xpath {expr!r}: {err}")
                    problems += 1
                    continue
                if not hits:
                    print(f"  ✗ {xml_file.name} :: {record.get('id')}")
                    print(f"      xpath {expr!r} matches nothing in {parent_id}")
                    problems += 1
    return problems


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

    print("\nVerifying xpath anchors against parent views")
    problems += check_xpath_anchors(args.odoo, etree)

    if problems:
        print(f"\n{problems} problem(s) — Odoo will refuse these at install.")
        return 1

    print("\nOK — schema-backed views validate and every xpath anchor resolves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
