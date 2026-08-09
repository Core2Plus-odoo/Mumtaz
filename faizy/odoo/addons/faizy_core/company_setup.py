"""Company identity — the operator behind Faizy, and its mark.

Faizy is a service; **C2P Consultants FZC LLC** is the entity that bills for it.
That distinction has to be right in Odoo because the company record is what
lands on every invoice, and a customer disputing a charge needs to find a real
legal name there rather than a brand.

Called from two places, and only those: `post_init_hook` on a fresh database,
and the 19.0.1.2.0 migration for instances installed before this existed.
Deliberately not a data file — a non-noupdate record would re-apply on every
upgrade and stomp whatever the finance team had corrected by hand, and a
noupdate one would never reach the instance already running.
"""

import base64
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

LOGO = Path(__file__).parent / "static" / "description" / "icon.png"

# ONLY confirmed facts go in here.
#
# An earlier version of this file carried email="hello@faizy.pk", which nobody
# ever told me existed — I inferred it from the domain. A customer writing to a
# support address that bounces is worse off than one who cannot find an address
# at all, and the same goes for a placeholder street on a tax invoice. So the
# rule is: if Muhammad has not said it, it is not here.
#
# Still needed from him: the support WhatsApp number, a real support email, the
# registered address, and the TRN if C2P is VAT-registered. Each is a one-field
# edit in Settings > Companies and needs no deployment.

# The trading name. Muhammad's call: the company in Odoo is Faizy, because that
# is what a customer recognises at the top of an invoice.
COMPANY_NAME = "Faizy"

# The entity that actually bills. Still needed, because "Faizy" is a brand and
# the money is taken by a registered company — a customer disputing a charge,
# or a bank tracing one, needs a legal name to find. Keeping it in
# `report_footer` puts it on the bottom of every invoice and report without
# turning the header into a legal document.
LEGAL_ENTITY = "C2P Consultants FZC LLC"

PROFILE = {
    "name": COMPANY_NAME,
    "social_facebook": "https://www.facebook.com/faizy.pk/",
    "report_footer": f"Faizy is a service of {LEGAL_ENTITY}.",
}

# The name this module set before the rename. Used by the 19.0.1.4.0 migration
# to correct only what we wrote, and leave alone anything set by hand.
PREVIOUS_COMPANY_NAME = LEGAL_ENTITY


def apply_company_profile(env, overwrite_name=True):
    """Set the operating company's identity. Single company only.

    A multi-company database is somebody's deliberate structure, and guessing
    which one trades as Faizy would be worse than doing nothing.
    """
    companies = env["res.company"].search([])
    if len(companies) != 1:
        _logger.info(
            "faizy_core: %s companies present, leaving company details alone",
            len(companies),
        )
        return

    company = companies
    values = dict(PROFILE)
    if not overwrite_name:
        values.pop("name", None)

    # Odoo names a fresh company "My Company (San Francisco)" or similar. If it
    # has already been renamed to something real, that was a decision — except
    # when the name is the one THIS module set on an earlier version, which is
    # not a decision, it is our own leftover.
    renameable = (
        not company.name
        or "My Company" in company.name
        or company.name == PREVIOUS_COMPANY_NAME
    )
    if overwrite_name and not renameable:
        values.pop("name", None)
        _logger.info(
            "faizy_core: company already named %r, keeping it", company.name
        )

    # Same reasoning for the report footer: replace ours, never someone else's.
    if company.report_footer and LEGAL_ENTITY not in (company.report_footer or ""):
        values.pop("report_footer", None)

    if not company.country_id:
        values["country_id"] = env.ref("base.ae", raise_if_not_found=False).id or False

    if LOGO.exists() and not company.logo:
        values["logo"] = base64.b64encode(LOGO.read_bytes())
    elif not LOGO.exists():
        _logger.warning(
            "faizy_core: %s missing — run tools/make_icon.py to regenerate it",
            LOGO,
        )

    # social_facebook belongs to the `social_media` module, which faizy_core
    # does not depend on — it arrives via faizy_website -> website. Today the
    # load order means it is always present by the time this runs, but that is
    # a coincidence of the dependency graph, not a guarantee, and writing a
    # field that does not exist would take the whole install down.
    missing = [k for k in values if k not in company._fields]
    for key in missing:
        _logger.info(
            "faizy_core: res.company has no %r on this install — skipping it", key
        )
        values.pop(key)

    company.write({k: v for k, v in values.items() if v})
    _logger.info("faizy_core: company profile applied to %s", company.name)
