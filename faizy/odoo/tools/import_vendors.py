"""Load the vendor seed list into a live Faizy database.

    sudo -u faizy /opt/faizy/venv/bin/python3 /opt/faizy/odoo/odoo-bin shell \\
      -c /opt/faizy/odoo.conf -d faizy_prod --no-http \\
      < /opt/faizy/src/faizy/odoo/tools/import_vendors.py

Not a module data file, deliberately. These are operational records that ops
will edit, retire and add to — putting them in `data/` would make them
`noupdate` fixtures that reappear on every fresh install and fight anyone who
tries to change them. A one-shot loader is the honest shape.

Idempotent: matched on website, so running it twice does not create duplicates
and does not overwrite edits somebody has already made. Everything lands as a
PROSPECT — `faizy.order` refuses an unapproved vendor, so nothing here can
carry a customer's money until a human presses Approve under
Faizy → Network → Vendors.
"""

import csv
import os

CSV_PATH = os.environ.get(
    "FAIZY_VENDOR_CSV", "/opt/faizy/src/faizy/odoo/tools/vendors_seed.csv"
)

# `odoo-bin shell` injects `env` as a global. Reading it this way rather than
# relying on a bare name keeps the file lint-clean and gives a usable error
# when someone runs it with plain python by mistake.
try:
    env = globals()["env"]
except KeyError:  # pragma: no cover - only hit outside odoo-bin shell
    raise SystemExit(
        "Run this inside `odoo-bin shell`, e.g.\n"
        "  odoo-bin shell -c /opt/faizy/odoo.conf -d faizy_prod --no-http "
        "< import_vendors.py"
    )


def _selection_map(model, field_name):
    """Accept either the stored value or the human label from the CSV."""
    selection = model._fields[field_name].selection
    if callable(selection):
        selection = selection(model)
    mapping = {}
    for value, label in selection:
        mapping[value.lower()] = value
        mapping[label.lower()] = value
    return mapping


def main():
    Partner = env["res.partner"].sudo()
    Country = env["res.country"].sudo()
    Service = env["faizy.service"].sudo()

    types = _selection_map(Partner, "faizy_vendor_type")
    states = _selection_map(Partner, "faizy_vendor_state")

    with open(CSV_PATH, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    created, skipped, warnings = [], [], []

    for row in rows:
        name = (row.get("name") or "").strip()
        website = (row.get("website") or "").strip()
        if not name:
            continue

        existing = Partner.search(
            ["|", ("website", "=", website), ("name", "=ilike", name)], limit=1
        )
        if existing:
            skipped.append(f"{name} (already present as id {existing.id})")
            continue

        values = {
            "name": name,
            "is_company": (row.get("is_company") or "").strip().lower()
            in ("true", "1", "yes"),
            "website": website or False,
            "email": (row.get("email") or "").strip() or False,
            "phone": (row.get("phone") or "").strip() or False,
            "mobile": (row.get("mobile") or "").strip() or False,
            "street": (row.get("street") or "").strip() or False,
            "city": (row.get("city") or "").strip() or False,
            "is_faizy_vendor": True,
            "faizy_vendor_note": (row.get("faizy_vendor_note") or "").strip() or False,
        }

        country = (row.get("country_id") or "").strip()
        if country:
            found = Country.search([("name", "=ilike", country)], limit=1)
            if found:
                values["country_id"] = found.id
            else:
                warnings.append(f"{name}: no country named {country!r}")

        raw_type = (row.get("faizy_vendor_type") or "").strip()
        if raw_type:
            resolved = types.get(raw_type.lower())
            if resolved:
                values["faizy_vendor_type"] = resolved
            else:
                warnings.append(f"{name}: unknown vendor type {raw_type!r}, left blank")

        # Everything lands unapproved regardless of what the CSV says. A file
        # is not an approval, and this loader must not be a way around the gate.
        values["faizy_vendor_state"] = states["prospect"]
        raw_state = (row.get("faizy_vendor_state") or "").strip().lower()
        if raw_state and states.get(raw_state) != "prospect":
            warnings.append(
                f"{name}: CSV asked for state {raw_state!r}; imported as Prospect — "
                "approve it in the UI instead"
            )

        service_names = [
            s.strip()
            for s in (row.get("faizy_vendor_service_ids") or "").split(",")
            if s.strip()
        ]
        if service_names:
            services = Service.browse()
            for service_name in service_names:
                found = Service.search([("name", "=ilike", service_name)], limit=1)
                if found:
                    services |= found
                else:
                    warnings.append(f"{name}: no service named {service_name!r}")
            if services:
                values["faizy_vendor_service_ids"] = [(6, 0, services.ids)]

        record = Partner.create(values)
        created.append(f"{record.faizy_vendor_code or '—'}  {record.name}")

    env.cr.commit()

    print(f"\n=== Faizy vendor import — {CSV_PATH}")
    print(f"{len(rows)} row(s) read\n")
    print(f"created {len(created)}:")
    for line in created:
        print(f"  + {line}")
    if skipped:
        print(f"\nskipped {len(skipped)} (already in the database):")
        for line in skipped:
            print(f"  = {line}")
    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for line in warnings:
            print(f"  ! {line}")
    print(
        "\nAll imported as PROSPECT. Nothing can be routed an order until it is "
        "approved:\n  Faizy → Network → Vendors → filter 'Awaiting Approval' → "
        "open → Approve Vendor\n"
    )


main()
