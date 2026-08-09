"""Correct the currency labelling on a database installed before multi-market
pricing existed.

Two things need fixing on an existing instance, and neither is reachable from
the data files:

1. **The plan currency.** Plans now pin `currency_id` to AED, but that is in a
   `noupdate` block — deliberately, so ops repricing survives upgrades — which
   means existing plan records keep whatever they got at install. That was the
   company currency, and a fresh Odoo database defaults to USD. The figure 26.50
   was always the AED price; only the label was wrong.

2. **The subscription currency.** `faizy.subscription.currency_id` used to be
   `related="plan_id.currency_id"`. Its stored column therefore carries the same
   wrong label, and because the field is no longer related, fixing the plan will
   not propagate to it.

This relabels; it does not reprice. Every amount stays the number it was. That
distinction is the whole reason this runs as a migration rather than letting the
new `_compute_price` fire: the stored compute runs before this script, so it
would resolve `price_for(USD)` and hand an existing subscriber the *published
USD price* — a genuine repricing of a live subscription. The recompute at the
end is what puts that right.

Deliberately conservative about the company currency: only touched if the
database still looks untouched, exactly as the install hook is.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    aed = env.ref("base.AED", raise_if_not_found=False)
    if not aed:
        _logger.warning("faizy_core: base.AED missing, skipping currency migration")
        return
    aed.active = True

    company = env["res.company"].search([], limit=1)
    stale = company.currency_id if company.currency_id != aed else None

    # ── The company ──────────────────────────────────────────────────────
    usd = env.ref("base.USD", raise_if_not_found=False)
    if (
        stale
        and len(env["res.company"].search([])) == 1
        and usd
        and stale == usd
        and not env["account.move"].search_count([], limit=1)
    ):
        company.currency_id = aed
        if not company.country_id:
            company.country_id = env.ref("base.ae", raise_if_not_found=False)
        _logger.info("faizy_core: company currency corrected to AED")
    elif stale:
        _logger.warning(
            "faizy_core: company currency is %s, not AED. Left alone — either "
            "it was set deliberately or journal entries already exist. Plan "
            "prices are AED figures; check Settings > Companies.",
            stale.name,
        )

    # ── The plans ────────────────────────────────────────────────────────
    plans = env["faizy.plan"].search([("currency_id", "!=", aed.id)])
    if plans:
        _logger.info(
            "faizy_core: relabelling %s plan(s) from %s to AED",
            len(plans),
            ", ".join(sorted(set(plans.mapped("currency_id.name")))),
        )
        plans.currency_id = aed

    # ── The subscriptions ────────────────────────────────────────────────
    # Only those carrying the label inherited from the plan. A currency somebody
    # set on purpose after the upgrade is left alone.
    if stale:
        mislabelled = env["faizy.subscription"].search(
            [("currency_id", "=", stale.id)]
        )
        if mislabelled:
            _logger.info(
                "faizy_core: relabelling %s subscription(s) from %s to AED",
                len(mislabelled),
                stale.name,
            )
            mislabelled.currency_id = aed

    # `price` became a stored compute during this same upgrade, and it was
    # computed against the currency this script has just corrected. Recompute
    # explicitly rather than trusting field-init ordering.
    for sub in env["faizy.subscription"].search([]):
        sub.price = sub.plan_id.price_for(sub.currency_id)
