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
import hashlib
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

LOGO = Path(__file__).parent / "static" / "description" / "icon.png"

# Records the mark we installed, so a later logo replaces it while one
# uploaded by hand survives. Odoo ships a placeholder, so "is it empty"
# cannot tell the two apart.
LOGO_STAMP = "faizy_core.logo_source_sha"

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

# Mirrors res.company.faizy_free_activity_grant's own default. Needed here too
# because a field default applies when a RECORD is created, not when a COLUMN
# is added: installing onto an existing database leaves the company row at 0,
# and every customer then signs up with no free activities while /start
# promises three.
DEFAULT_FREE_GRANT = 3

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

# ── How invoices look ────────────────────────────────────────────────────
#
# An invoice is the one document a customer keeps, forwards to a spouse and
# occasionally shows a bank. It is worth as much care as the home page, and it
# is a different rendering path — a PDF, with no internet and no webfonts.
#
# **The brand orange is not here, and cannot be.** Odoo paints `primary_color`
# onto the invoice heading, the total and the tagline as TEXT (see
# web.styles_company_report). #F69E22 as text on white measures 2.14:1. That is
# the same rule the whole design system is built on — orange is a background
# colour, never a text colour — so the report primary is the clay already used
# for headings on the site, at 6.38:1. Orange still appears, in the logo.
#
# `font` is a Selection with eight options and Poppins is not one of them.
# Montserrat is the nearest geometric sans Odoo will actually embed; asking for
# Poppins would either fail validation or render as a fallback nobody chose.
REPORT_STYLE = {
    # Boxed puts the total in a filled band, which is the number the reader is
    # looking for. Odoo computes the text colour against the fill, and picks
    # white over clay.
    "layout_key": "web.external_layout_boxed",
    "font": "Montserrat",
    "primary_color": "#8f4f08",     # 6.38:1 on white
    "secondary_color": "#2b2622",   # 14.97:1 on white, for the field labels
    # Muhammad's tagline, in the one place on a document where a tagline
    # belongs. Roman Urdu deliberately, not the Urdu script: the PDF engine has
    # no Nastaliq font and would render it as empty boxes.
    "report_header": "Faizy Hai Na!",
}

# The name this module set before the rename. Used by the 19.0.1.4.0 migration
# to correct only what we wrote, and leave alone anything set by hand.
PREVIOUS_COMPANY_NAME = LEGAL_ENTITY


def _report_style_values(env, company):
    """Brand the printed documents, without overruling a deliberate choice.

    Each key is set only while it is still Odoo's default or empty. Someone who
    has opened Settings → Document Layout and picked a colour has made a
    decision, and a module upgrade quietly reverting it is the behaviour that
    makes people stop upgrading.
    """
    values = {}

    if not company.external_report_layout_id:
        layout = env.ref(REPORT_STYLE["layout_key"], raise_if_not_found=False)
        if layout:
            values["external_report_layout_id"] = layout.id
        else:
            _logger.warning(
                "faizy_core: report layout %s not found, leaving the default",
                REPORT_STYLE["layout_key"],
            )

    # "Lato" is Odoo's default, so it means "nobody chose", not "somebody chose
    # Lato". Any other value is a choice and stays.
    if not company.font or company.font == "Lato":
        values["font"] = REPORT_STYLE["font"]

    for field in ("primary_color", "secondary_color", "report_header"):
        if not company[field]:
            values[field] = REPORT_STYLE[field]

    return values


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

    # Country is not set here any more. accounting_setup owns it, and it runs
    # first — this used to default to base.ae, which now contradicts the
    # decision that the books are Pakistani.

    if not company.faizy_free_activity_grant:
        values["faizy_free_activity_grant"] = DEFAULT_FREE_GRANT
        _logger.warning(
            "faizy_core: company had no free-activity grant; setting %s. "
            "Anyone who signed up before this got none.",
            DEFAULT_FREE_GRANT,
        )

    values.update(_report_style_values(env, company))

    # `not company.logo` was wrong and shipped as "Your Logo" on the live
    # header. Odoo gives every new company a placeholder logo, so the field is
    # never empty and this branch never fired. Same fix as the favicon: stamp
    # what we installed, replace ours, never touch one somebody uploaded.
    stamp = env["ir.config_parameter"].sudo()
    if LOGO.exists():
        mark = base64.b64encode(LOGO.read_bytes())
        digest = hashlib.sha256(mark).hexdigest()
        previous = stamp.get_param(LOGO_STAMP)

        # First run owns the branding. There is no way to tell Odoo's "Your
        # Logo" placeholder from a real upload by inspection — res.company.logo
        # is an Image field, so Odoo re-encodes whatever it stores and a
        # byte-comparison against the shipped default does not hold. The
        # previous two attempts both got this wrong in the same direction and
        # shipped the placeholder to the live header twice.
        #
        # After that, the stamp does the work: re-install only when the
        # packaged mark itself changes, so a logo uploaded later survives every
        # ordinary upgrade and the real artwork still lands when it replaces
        # this interim one.
        if previous is None or previous != digest:
            values["logo"] = mark
            stamp.set_param(LOGO_STAMP, digest)
            _logger.info("faizy_core: installing the packaged logo")
        else:
            _logger.info("faizy_core: logo already current, leaving it")
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
