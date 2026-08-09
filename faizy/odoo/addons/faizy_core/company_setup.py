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

# Everything here is confirmed. Address, TRN and the support phone number are
# NOT known, so they are absent rather than invented — a placeholder address on
# a tax invoice is worse than a blank one.
PROFILE = {
    "name": "C2P Consultants FZC LLC",
    "website": "https://faizy.pk",
    "email": "hello@faizy.pk",
}


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
    # has already been renamed to something real, that was a decision.
    if overwrite_name and company.name and "My Company" not in company.name:
        values.pop("name", None)
        _logger.info(
            "faizy_core: company already named %r, keeping it", company.name
        )

    if not company.country_id:
        values["country_id"] = env.ref("base.ae", raise_if_not_found=False).id or False

    if LOGO.exists() and not company.logo:
        values["logo"] = base64.b64encode(LOGO.read_bytes())
    elif not LOGO.exists():
        _logger.warning(
            "faizy_core: %s missing — run tools/make_icon.py to regenerate it",
            LOGO,
        )

    company.write({k: v for k, v in values.items() if v})
    _logger.info("faizy_core: company profile applied to %s", company.name)
