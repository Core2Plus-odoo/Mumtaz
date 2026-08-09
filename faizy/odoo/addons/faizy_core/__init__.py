import logging

from . import models

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Point the company at the currency the price list is written in.

    A fresh Odoo database defaults its company to USD. Faizy's base plan prices
    are AED — C2P Consultants FZC LLC is a UAE free-zone entity — so leaving the
    default in place makes Odoo read `price = 26.50` as USD 26.50. Nothing
    errors; the number is simply wrong everywhere it appears, which is the worst
    kind of wrong.

    Deliberately conservative. This only fires on a database that still looks
    untouched: exactly one company, still on Odoo's USD default, with no journal
    entries behind it. Anything else is a real configuration and is left alone —
    changing the currency under existing accounting entries would silently
    restate them.
    """
    companies = env["res.company"].search([])
    if len(companies) != 1:
        _logger.info(
            "faizy_core: %s companies found, leaving currency configuration alone",
            len(companies),
        )
        return

    company = companies
    aed = env.ref("base.AED", raise_if_not_found=False)
    if not aed:
        return

    if company.currency_id == aed:
        return

    usd = env.ref("base.USD", raise_if_not_found=False)
    if usd and company.currency_id != usd:
        _logger.info(
            "faizy_core: company currency is %s, not Odoo's default — leaving it",
            company.currency_id.name,
        )
        return

    if env["account.move"].sudo().search_count([], limit=1):
        _logger.warning(
            "faizy_core: company currency is %s but journal entries already "
            "exist, so it was NOT changed to AED. Plan prices are AED figures — "
            "check Settings > Companies before invoicing.",
            company.currency_id.name,
        )
        return

    aed.active = True
    company.currency_id = aed
    if not company.country_id:
        company.country_id = env.ref("base.ae", raise_if_not_found=False)
    _logger.info("faizy_core: company currency set to AED")
