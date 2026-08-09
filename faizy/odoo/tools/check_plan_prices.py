#!/usr/bin/env python3
"""Check the plan price matrix for gaps and drift.

Subscribers live anywhere, so every plan carries a published price per market
rather than one base price converted at today's rate. That is the right model,
but it turns three numbers into fifteen, and a fifteen-cell table maintained by
hand drifts: someone reprices Standard in AED and forgets that the plan's own
`price` field is the AED figure too, or adds a currency to one plan and not the
others, and the gap only shows up as a customer being quoted the wrong thing.

Nothing else catches this. The XML is well-formed, the fields all exist, and
Odoo installs happily — a missing GBP row on one plan just means that plan
silently falls back to its base price on the pricing page, which looks like a
price rather than an error.

So this reads the data file and asserts the invariants the model relies on:

  1. Every plan publishes in the same set of currencies — no market gaps.
  2. Every published price carries an overage rate, or overage silently
     bills nothing.
  3. Every plan pins `currency_id` to AED. Left unset it inherits the company
     currency, and a fresh Odoo database defaults that to USD — which turns
     AED 26.50 into USD 26.50 without erroring anywhere.
  4. A plan's base `price`/`overage_price` match the AED row, since that row is
     the fallback those fields stand in for.
  5. The PKR overage row matches `overage_price_pkr`, which is the figure the
     customer app quotes.

    python3 faizy/odoo/tools/check_plan_prices.py

No network, no database.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DATA = (
    Path(__file__).resolve().parents[1]
    / "addons/faizy_core/data/faizy_plan_data.xml"
)

# Each plan pins its own currency_id in the data file, so the base price never
# depends on how the company happened to be set up. This is the value it must
# be pinned to — an unpinned plan would inherit the company currency, and a
# fresh Odoo database defaults that to USD.
BASE_CURRENCY = "AED"


def field(record: ET.Element, name: str) -> str | None:
    node = record.find(f"./field[@name='{name}']")
    if node is None:
        return None
    return node.get("ref") or (node.text or "").strip()


def num(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def main() -> int:
    root = ET.parse(DATA).getroot()

    plans: dict[str, dict] = {}
    prices: dict[str, list[dict]] = {}

    for record in root.iter("record"):
        model = record.get("model")
        if model == "faizy.plan":
            plans[record.get("id")] = {
                "name": field(record, "name"),
                "currency": (field(record, "currency_id") or "").removeprefix("base."),
                "price": num(field(record, "price")),
                "overage_price": num(field(record, "overage_price")),
                "overage_pkr": num(field(record, "overage_price_pkr")),
            }
        elif model == "faizy.plan.price":
            plan_ref = field(record, "plan_id")
            currency = (field(record, "currency_id") or "").removeprefix("base.")
            prices.setdefault(plan_ref, []).append(
                {
                    "id": record.get("id"),
                    "currency": currency,
                    "amount": num(field(record, "amount")),
                    "overage": num(field(record, "overage_amount")),
                }
            )

    errors: list[str] = []

    if not plans:
        errors.append("no faizy.plan records found — has the data file moved?")

    # 1. Same set of markets on every plan.
    markets = {ref: {p["currency"] for p in rows} for ref, rows in prices.items()}
    for ref in plans:
        if ref not in markets:
            errors.append(f"{ref}: publishes no prices at all")
    if len(set(map(frozenset, markets.values()))) > 1:
        every = set().union(*markets.values())
        for ref, have in sorted(markets.items()):
            missing = every - have
            if missing:
                errors.append(
                    f"{ref}: no price published in {', '.join(sorted(missing))} "
                    f"— that market silently falls back to the base price"
                )

    for ref, rows in sorted(prices.items()):
        plan = plans.get(ref)
        if plan is None:
            errors.append(f"price rows reference unknown plan {ref!r}")
            continue

        # An unpinned plan silently inherits the company currency.
        if plan["currency"] != BASE_CURRENCY:
            errors.append(
                f"{ref}: currency_id is {plan['currency'] or 'unset'}, expected "
                f"{BASE_CURRENCY} — the base price would be read in whatever "
                f"currency the company happens to use"
            )

        seen = set()
        for row in rows:
            # 2. Overage published everywhere.
            if not row["overage"]:
                errors.append(
                    f"{row['id']}: no overage_amount — extra activities in "
                    f"{row['currency']} would bill nothing"
                )
            if row["amount"] is None:
                errors.append(f"{row['id']}: no amount")
            if row["currency"] in seen:
                errors.append(f"{ref}: two price rows for {row['currency']}")
            seen.add(row["currency"])

            # 3. The company-currency row is what the plan's own fields mean.
            if row["currency"] == BASE_CURRENCY:
                if row["amount"] != plan["price"]:
                    errors.append(
                        f"{ref}: plan price {plan['price']} disagrees with the "
                        f"{BASE_CURRENCY} row {row['amount']} — the plan field "
                        f"is the fallback for that same market"
                    )
                if plan["overage_price"] and row["overage"] != plan["overage_price"]:
                    errors.append(
                        f"{ref}: plan overage_price {plan['overage_price']} "
                        f"disagrees with the {BASE_CURRENCY} row {row['overage']}"
                    )

            # 4. PKR is the figure the customer app quotes.
            if row["currency"] == "PKR" and plan["overage_pkr"] is not None:
                if row["overage"] != plan["overage_pkr"]:
                    errors.append(
                        f"{ref}: overage_price_pkr {plan['overage_pkr']} disagrees "
                        f"with the PKR row {row['overage']} — the app quotes the "
                        f"former, invoicing uses the latter"
                    )

    if errors:
        print(f"Plan price matrix: {len(errors)} problem(s)\n")
        for err in errors:
            print(f"  ✗ {err}")
        return 1

    n_markets = len(set().union(*markets.values())) if markets else 0
    print(
        f"OK — {len(plans)} plan(s) × {n_markets} market(s), "
        f"every cell published and consistent with the plan fallback."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
