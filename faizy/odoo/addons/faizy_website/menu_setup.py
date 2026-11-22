"""Keep the header menu of a real website in the shape the data file describes.

`data/website_menu_data.xml` creates its entries on Odoo's generic menu tree.
Odoo then copies each top-level entry onto every website, but a copy of an
entry that sits *inside* a group keeps pointing at the generic group, not at
the website's own one. The visible result: "Our AI team" (and, on a fresh
database, "Become a Faizy" and "Privacy policy" too) never shows up under
"About Us" on the live site, and the dropdown can be empty.

This puts those entries under the website's own "About Us", and makes sure the
Blog link does not tie with the "Get started" button for the last slot (the
button is meant to end the row). It only moves entries that are still under the
generic group, so a placement chosen in the website editor is left alone.
"""

import logging

_logger = logging.getLogger(__name__)

ABOUT_CHILDREN = ("/join", "/ai-team", "/privacy")


def _find(env, website, url, parent=None, name=None):
    domain = [("website_id", "=", website.id), ("url", "=", url)]
    if parent:
        domain.append(("parent_id", "=", parent.id))
    if name:
        domain.append(("name", "=", name))
    return env["website.menu"].search(domain, limit=1)


def fix_header_menu(env):
    moved = reordered = 0
    for website in env["website"].search([]):
        top = website.menu_id
        if not top:
            continue
        about = _find(env, website, "#", parent=top, name="About Us")
        if about:
            for url in ABOUT_CHILDREN:
                stray = env["website.menu"].search(
                    [("website_id", "=", website.id), ("url", "=", url), ("parent_id", "!=", about.id)]
                )
                stray = stray.filtered(lambda m: m.parent_id and not m.parent_id.website_id and m.parent_id.url == "#")
                if stray:
                    stray.write({"parent_id": about.id})
                    moved += len(stray)
        blog = _find(env, website, "/blog", parent=top)
        start = _find(env, website, "/start", parent=top)
        if blog and start and blog.sequence == start.sequence:
            blog.sequence = start.sequence - 4
            reordered += 1
    _logger.info("faizy_website: header menu fixed (%s moved under About Us, %s reordered)", moved, reordered)
    return moved, reordered
