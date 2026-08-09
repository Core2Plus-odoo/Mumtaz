"""Put the Faizy mark in the browser tab.

Odoo ships its own purple favicon and never changes it, so an otherwise
finished site sits in the tab bar looking like a generic Odoo install — which
is the one piece of chrome a visitor sees on every single page.

`website.favicon` takes any image and Odoo's own `_handle_favicon` crops it
square and converts it to a 256x256 ICO on write, so the module only has to
hand over the PNG.

Called from `post_init_hook` on a fresh database and from the 19.0.1.1.0
migration for one already installed. Not a data file, for the same reason the
company profile is not: a non-noupdate record would overwrite a favicon
somebody uploaded by hand on every upgrade, and a noupdate one would never
reach the running instance.
"""

import base64
import hashlib
import logging

from odoo import tools

_logger = logging.getLogger(__name__)

# Records the mark this module last installed. Odoo re-encodes the favicon to
# ICO on write, so what comes back out never matches what went in and we cannot
# recognise our own work by comparison. Without this, the first run would look
# "custom" to the second, and the day the real logo lands the upgrade would
# politely refuse to replace the placeholder.
STAMP = "faizy_website.favicon_source_sha"

# Lives in faizy_core because the module icon is generated from the same mark;
# one source, so the tab and the Apps list cannot drift apart.
MARK = "faizy_core/static/description/icon.png"
ODOO_DEFAULT = "web/static/img/favicon.ico"


def apply_favicon(env):
    """Set the favicon on every website that still has Odoo's default.

    A favicon somebody uploaded deliberately is left alone. Detected by
    comparing against Odoo's shipped default rather than by a flag, because
    that is the only thing we can actually tell apart.
    """
    try:
        with tools.file_open(MARK, "rb") as handle:
            mark = base64.b64encode(handle.read())
    except FileNotFoundError:
        _logger.warning(
            "faizy_website: %s missing — run tools/make_icon.py. Favicon unchanged.",
            MARK,
        )
        return

    try:
        with tools.file_open(ODOO_DEFAULT, "rb") as handle:
            default = base64.b64encode(handle.read())
    except FileNotFoundError:
        default = None

    params = env["ir.config_parameter"].sudo()
    digest = hashlib.sha256(mark).hexdigest()
    ours = bool(params.get_param(STAMP))

    for website in env["website"].sudo().search([]):
        current = website.favicon
        untouched = default is not None and current == default
        if current and not untouched and not ours:
            _logger.info(
                "faizy_website: website %s has a favicon we did not set, keeping it",
                website.name,
            )
            continue
        website.favicon = mark
        _logger.info("faizy_website: favicon set on website %s", website.name)

    params.set_param(STAMP, digest)
