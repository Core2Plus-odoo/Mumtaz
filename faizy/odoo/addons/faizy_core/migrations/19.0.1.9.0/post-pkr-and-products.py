"""Move the plans onto PKR and give them the products billing needs.

Two changes that both hit `faizy.plan`, which lives in a `noupdate="1"` block —
so editing the data file reaches a fresh install and nothing else. Without this
the production plans keep AED as their base currency and keep no product at
all, which is precisely the state that has stopped a single invoice from ever
being raised.

**PKR as the base.** Muhammad's call: the work is done in Pakistan and costed
in rupees, so the plan's own `price` is the rupee figure and every other market
price is a commercial decision on top of it, not a conversion of it. The
per-market `faizy.plan.price` rows are untouched — a subscriber in Dubai still
pays the AED figure published for Dubai. What changes is the fallback and the
number the plan itself carries.

**Products.** `_prepare_invoice_lines` raises UserError when a plan has no
`product_id`; `_cron_recurring_invoice` catches it and writes the failure into
the subscription's chatter, so the billing run has been failing silently every
day since it was switched on. A product is also what carries the income account
and the tax mapping, so this is what makes the invoices land correctly in the
books rather than in whatever the default happens to be.

Conservative on purpose. A plan whose price has been edited away from the AED
figure we shipped is left alone and logged — somebody set that deliberately and
a migration must not overwrite a commercial decision. Same for a plan that
already has a product.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# code -> (AED price we shipped, PKR price, AED overage, PKR overage,
#          product xmlid)
PLANS = {
    "lite": (26.50, 1999.0, 4.00, 300.0, "faizy_core.product_plan_lite"),
    "standard": (66.20, 4999.0, 3.50, 250.0, "faizy_core.product_plan_standard"),
    "family_pro": (119.20, 8999.0, 2.75, 200.0, "faizy_core.product_plan_family_pro"),
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    pkr = env.ref("base.PKR", raise_if_not_found=False)
    if not pkr:
        _logger.error("faizy_core: base.PKR not found, plans left on their currency")
        return
    if not pkr.active:
        pkr.active = True

    overage_product = env.ref(
        "faizy_core.product_overage_activity", raise_if_not_found=False
    )

    for code, (aed, pkr_price, aed_overage, pkr_overage, xmlid) in PLANS.items():
        plan = env["faizy.plan"].search([("code", "=", code)], limit=1)
        if not plan:
            continue

        values = {}

        # Currency and price move together or not at all. Setting one without
        # the other would reprice the plan by a factor of ~75 in whichever
        # direction, which is the kind of error that looks like a working
        # migration.
        if plan.currency_id != pkr:
            if abs(plan.price - aed) < 0.01:
                values["currency_id"] = pkr.id
                values["price"] = pkr_price
                if abs(plan.overage_price - aed_overage) < 0.01:
                    values["overage_price"] = pkr_overage
            else:
                _logger.warning(
                    "faizy_core: plan %s is %.2f %s, not the %.2f AED we "
                    "shipped — somebody set that, so currency and price were "
                    "left alone. Change them together in Faizy > Plans.",
                    code, plan.price, plan.currency_id.name, aed,
                )

        if not plan.product_id:
            product = env.ref(xmlid, raise_if_not_found=False)
            if product:
                values["product_id"] = product.id
        if not plan.overage_product_id and overage_product:
            values["overage_product_id"] = overage_product.id

        if values:
            plan.write(values)
            _logger.info("faizy_core: plan %s updated — %s", code, ", ".join(values))
