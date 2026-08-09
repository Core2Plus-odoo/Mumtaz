import logging

from . import models
from .company_setup import apply_company_profile

_logger = logging.getLogger(__name__)


def _set_company_currency(env):
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
    if not aed or company.currency_id == aed:
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
    _logger.info("faizy_core: company currency set to AED")


def post_init_hook(env):
    """Set up the operating company on a fresh database.

    The two steps are independent on purpose. Currency has a long list of
    reasons to bail out — existing journal entries, a deliberately different
    currency — and none of them are a reason to leave the company called
    "My Company" with no logo.
    """
    _set_company_currency(env)
    apply_company_profile(env)
