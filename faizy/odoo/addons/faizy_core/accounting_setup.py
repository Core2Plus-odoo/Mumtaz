"""Put the company on Pakistani books.

Muhammad's decision: the operating entity for accounting purposes is Pakistani,
so the company reports in PKR and keeps the Pakistan chart of accounts. That is
also why PKR is the base price — the work is done and costed in rupees, and
every other market price is a commercial decision on top of it rather than a
conversion of it.

Three steps, each independently guarded, because they fail for different
reasons and none of them is a reason to skip the others:

  country   — needed before Odoo will offer the right taxes or auto-install a
              localisation at all.
  currency  — safe only while the books are empty. Odoo will not stop you
              changing it under existing journal entries; it simply restates
              every one of them, silently, which is why this refuses.
  chart     — l10n_pk's accounts and taxes, loaded once. Never reloaded over a
              chart somebody is already posting to.

Idempotent by design: called from post_init_hook on a fresh database and from a
migration on the running one, and safe to run again after either.
"""

import logging

_logger = logging.getLogger(__name__)

CHART_TEMPLATE_CODE = "pk"


def apply_accounting_profile(env):
    """Country, currency and chart of accounts. Returns nothing; logs its work."""
    companies = env["res.company"].search([])
    if len(companies) != 1:
        _logger.info(
            "faizy_core: %s companies found, leaving accounting setup alone",
            len(companies),
        )
        return
    company = companies

    _set_country(env, company)
    _set_currency(env, company)
    _load_chart(env, company)


def _set_country(env, company):
    pakistan = env.ref("base.pk", raise_if_not_found=False)
    if not pakistan:
        return
    if company.country_id == pakistan:
        return
    if company.country_id:
        # Somebody set this deliberately. Changing a company's country moves
        # its tax country with it, which is not a thing to do behind a
        # migration message nobody reads.
        _logger.warning(
            "faizy_core: company country is %s, not Pakistan — left alone. "
            "Set it in Settings > Companies if the entity has moved.",
            company.country_id.name,
        )
        return
    company.country_id = pakistan
    _logger.info("faizy_core: company country set to Pakistan")


def _set_currency(env, company):
    pkr = env.ref("base.PKR", raise_if_not_found=False)
    if not pkr:
        _logger.error("faizy_core: base.PKR not found, company currency unchanged")
        return
    if company.currency_id == pkr:
        return

    if env["account.move"].sudo().search_count([], limit=1):
        _logger.warning(
            "faizy_core: company currency is %s and journal entries already "
            "exist, so it was NOT changed to PKR. Changing it now would "
            "restate every existing entry. Talk to an accountant before "
            "touching Settings > Companies.",
            company.currency_id.name,
        )
        return

    if not pkr.active:
        pkr.active = True
    previous = company.currency_id.name
    company.currency_id = pkr
    _logger.info("faizy_core: company currency %s -> PKR", previous)


def _load_chart(env, company):
    if company.chart_template:
        _logger.info(
            "faizy_core: company already on chart template %r, not reloading",
            company.chart_template,
        )
        return

    available = env["account.chart.template"]._get_chart_template_mapping()
    if CHART_TEMPLATE_CODE not in available:
        # l10n_pk is a hard dependency, so this means something is genuinely
        # wrong with the addons path rather than a missing optional module.
        _logger.error(
            "faizy_core: chart template %r is not available — is l10n_pk "
            "installed? Accounting will have no accounts or taxes.",
            CHART_TEMPLATE_CODE,
        )
        return

    env["account.chart.template"].try_loading(
        CHART_TEMPLATE_CODE, company, install_demo=False
    )
    _logger.info("faizy_core: loaded the Pakistan chart of accounts")
