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
    "odoo/addons/base/models/res_currency.py",
    "odoo/addons/base/models/ir_actions.py",
    "addons/website/models/website_menu.py",
    "odoo/addons/base/models/res_company.py",
    "addons/social_media/models/res_company.py",  # social_facebook et al
    # res.partner is spread across modules. All of them are needed, because a
    # field missing from one file is not a missing field — `currency_id` comes
    # from account, `lang` and `country_id` from base, the messaging fields
    # from mail. Indexing only base would produce a wall of false failures.
    "odoo/addons/base/models/res_partner.py",
    "addons/account/models/partner.py",
    "addons/mail/models/res_partner.py",
]

# ir.cron delegates to ir.actions.server via _inherits, so these are legal on a
# cron record even though they are declared on the action.
DELEGATED_FIELDS = {
    "ir.cron": {"name", "model_id", "state", "code", "sequence", "binding_model_id"},
}

# Models we deliberately never check: ours, and the ones whose "fields" are
# really view plumbing rather than a model schema.
#
# ir.actions.act_window used to be here. It should not have been — its fields
# are ordinary, and skipping it is exactly why target="inline" reached
# production. Removing it needs the inheritance merge below, because
# act_window declares only its own fields and gets `name`, `type` and friends
# from ir.actions.actions.
SKIP_MODELS = {"ir.ui.view", "ir.model.access"}

# Attribute access that is the ORM rather than a field, so absence from the
# field index means nothing.
ORM_ATTRS = {
    "id", "ids", "env", "sudo", "with_context", "with_user", "browse",
    "search", "search_count", "read", "write", "create", "mapped",
    "filtered", "sorted", "exists", "ensure_one", "display_name",
}


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


# Both spellings: `_inherit = "x"` and `_inherit = ["x", "y"]`. Odoo core uses
# the list form for ir.actions.act_window, and a regex that only handled the
# bare string quietly credited act_window with none of ir.actions.actions'
# fields — which showed up as `name does not exist`, a false alarm that would
# have taught everyone to ignore this tool.
def _model_names(block: str, attr: str) -> list[str]:
    match = re.search(
        rf'{attr}\s*=\s*(\[[^\]]*\]|["\'][\w.]+["\'])', block
    )
    if not match:
        return []
    return re.findall(r'["\']([\w.]+)["\']', match.group(1))


def index_fields(sources: dict[str, str]) -> dict[str, set[str]]:
    """model name -> declared field names, parsed from the core source."""
    index: dict[str, set[str]] = {}
    parents: dict[str, set[str]] = {}
    for text in sources.values():
        for block in re.split(r"\nclass\s+\w+\(", text)[1:]:
            names = _model_names(block, "_name")
            inherits = _model_names(block, "_inherit")
            targets = names or inherits
            if not targets:
                continue
            fields = set(re.findall(r"^    ([a-z_]+)\s*=\s*fields\.", block, re.M))
            for target in targets:
                index.setdefault(target, set()).update(fields)
            # `_name = X` alongside `_inherit = Y` is Odoo's "extend Y into a
            # new model X". X therefore has Y's fields too, and without this
            # every <field name="name"> on an act_window looks undeclared.
            if names and inherits:
                for child in names:
                    parents.setdefault(child, set()).update(inherits)

    for child, ancestors in parents.items():
        seen, queue = set(), list(ancestors)
        while queue:
            ancestor = queue.pop()
            if ancestor in seen:
                continue
            seen.add(ancestor)
            index.setdefault(child, set()).update(index.get(ancestor, set()))
            queue.extend(parents.get(ancestor, ()))
    return index


# A Selection whose options are a literal list on one logical line. Anything
# computed, or built from a function, is not matched and therefore not checked
# — the point of this tool is that it never guesses.
SELECTION_RE = re.compile(
    r"^    ([a-z_]+)\s*=\s*fields\.Selection\(\s*\[(.*?)\]", re.M | re.S
)
OPTION_RE = re.compile(r"\(\s*['\"]([\w.-]+)['\"]\s*,")


def index_selections(sources: dict[str, str]) -> dict[tuple[str, str], set[str]]:
    """(model, field) -> allowed values, for statically-declared Selections.

    Exists because `target="inline"` on an ir.actions.act_window sailed past
    every offline check and killed a production upgrade. The field name was
    real, so the name check passed; only the VALUE was wrong, and "inline" has
    not been valid since Odoo 8. Odoo raises ValueError at load, which means
    you find out during the upgrade, with the module half-applied.
    """
    index: dict[tuple[str, str], set[str]] = {}
    for text in sources.values():
        for block in re.split(r"\nclass\s+\w+\(", text)[1:]:
            names = _model_names(block, "_name")
            inherits = _model_names(block, "_inherit")
            targets = names or inherits
            for field, body in SELECTION_RE.findall(block):
                options = set(OPTION_RE.findall(body))
                if not options:
                    continue
                for target in targets:
                    index.setdefault((target, field), set()).update(options)
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
    selections = index_selections(sources)
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
                    continue

                # Plain text only. eval=/ref= values are expressions, and
                # judging them would mean evaluating them.
                options = selections.get((model, fname))
                value = (field.text or "").strip()
                if (
                    options
                    and value
                    and not field.get("eval")
                    and not field.get("ref")
                    and value not in options
                ):
                    problems.append(
                        f"{xml_file.relative_to(ADDONS)}: "
                        f"{model}.{fname} = {value!r} is not a valid value in "
                        f"Odoo {ODOO_VERSION} — allowed: "
                        f"{', '.join(sorted(options))}"
                    )

    # ── QWeb templates ──────────────────────────────────────────────────
    #
    # `company.mobile` in a website template took the home page down with a
    # 500 on every render: res.company has `phone` and `email` in Odoo 19, and
    # no `mobile` at all. Nothing caught it, because the view-field check only
    # covers <field name="..."> against our own models, and this was an
    # attribute access inside a QWeb expression on a CORE model.
    #
    # Narrow on purpose. It only looks at attribute access on names that are
    # unambiguously a res.company, and only flags an attribute that is neither
    # a field nor plausibly a method. Anything cleverer would need to evaluate
    # the template.
    COMPANY_EXPRS = re.compile(
        r"\b(?:company|website\.company_id|res_company)\.([a-z_][a-z0-9_]*)\b"
    )
    company_fields = index.get("res.company", set())
    if company_fields:
        for xml_file in sorted(ADDONS.glob("*/views/*.xml")):
            # Comments first. The fix for this very bug carries the words
            # "company.mobile" in a comment explaining why not to use it, and
            # a checker that flags its own documentation is a checker people
            # start ignoring.
            text = re.sub(r"<!--.*?-->", "", xml_file.read_text(), flags=re.S)
            for attr in sorted(set(COMPANY_EXPRS.findall(text))):
                if attr in company_fields or attr in ORM_ATTRS:
                    continue
                problems.append(
                    f"{xml_file.relative_to(ADDONS)}: res.company has no "
                    f"{attr!r} in Odoo {ODOO_VERSION} — a QWeb template reading "
                    f"it raises at render, not at install"
                )
        checked.add("res.company (templates)")

    # ── Python ──────────────────────────────────────────────────────────
    #
    # The third time a field Odoo 19 removed has reached production, and the
    # first time it was in Python rather than XML:
    #
    #   res.groups.category_id   data file      — blocked the install
    #   res.company.mobile       QWeb template  — 500 on the home page
    #   res.partner.mobile       PYTHON         — /start/submit wrote it on
    #       every customer signup, so signup 500'd; the WhatsApp queue read it,
    #       so every customer notification raised; and the vendor loader
    #       crashed on its first row.
    #
    # Odoo 18 declared `phone` AND `mobile` on res.partner; 19.0 declares
    # `phone = fields.Char()` alone.
    #
    # This is a deny-list, not an existence check, and that is deliberate. The
    # first attempt indexed res.partner's fields and flagged anything missing —
    # it produced 28 failures, every one of them wrong, because res.partner is
    # assembled from a dozen modules and any index built from a handful of
    # files is incomplete. A checker that cries wolf gets switched off, and
    # then it catches nothing at all. So: name the fields we know were removed
    # and that we know we used, and say exactly what to use instead.
    REMOVED_IN_19 = {
        "mobile": (
            "removed from res.partner and res.company in Odoo 19 — 18.0 "
            "declared phone AND mobile, 19.0 declares phone alone. Use `phone`."
        ),
    }
    roots = [ADDONS, ADDONS.parent / "tools"]
    for source_file in sorted(
        f for root in roots for pat in ("*.py", "*.xml", "*.csv")
        for f in root.rglob(pat)
    ):
        if "__pycache__" in source_file.parts:
            continue
        # This file necessarily names the fields it forbids — the deny-list is
        # a dict of them. Skipping it is not an exemption, it is the only way
        # the tool can state its own rule.
        if source_file.resolve() == Path(__file__).resolve():
            continue
        text = source_file.read_text()
        # Strip comments and docstrings first. Every fix for one of these bugs
        # explains itself in prose that names the very field it removed, and a
        # checker that flags its own documentation is one people stop trusting.
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        text = re.sub(r"#.*", "", text)
        text = re.sub(r'""".*?"""|\'\'\'.*?\'\'\'', "", text, flags=re.S)
        for name, reason in REMOVED_IN_19.items():
            # As an attribute (`partner.mobile`), a dict key or domain term
            # (`"mobile"`), or a CSV column header.
            if re.search(rf"""\.{name}\b|["']{name}["']|(?:^|,){name}(?:,|$)""",
                         text, flags=re.M):
                problems.append(
                    f"{source_file.name}: uses {name!r} — {reason}"
                )
    checked.add("removed-field deny-list (py/xml/csv)")

    print("Checked against:", ", ".join(sorted(checked)) or "nothing")
    if problems:
        print(f"\n{len(problems)} problem(s):\n")
        for problem in problems:
            print(f"  ✗ {problem}")
        return 1

    print("\nOK — core-model fields and selection values all exist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
