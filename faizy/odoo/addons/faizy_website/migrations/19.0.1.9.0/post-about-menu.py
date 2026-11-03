"""Group "Become a Faizy" under an About Us dropdown on the running site.

Muhammad's call: recruitment does not belong in the top bar. The visitor is an
expat worrying about their parents, and a link asking them to come and work for
us sits between "Plans" and the way to reach us, competing with the thing they
actually came for.

The data file now nests it, but `website_menu_data.xml` is `noupdate="1"` — the
parent it names only ever applied on the run that created the record — so the
live menu keeps its old shape until something moves it. This does.

Works per website rather than assuming one, and takes the parent and website
from the existing `/join` entry instead of resolving `website.main_menu`: a
site's menu tree is a copy of that template, not the template itself, so
reparenting onto the template would move the item off the visible menu
entirely.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

ABOUT_NAME = "About Us"
# url -> sequence within the dropdown.
CHILDREN = {"/join": 10, "/privacy": 20}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Menu = env["website.menu"]

    for join in Menu.search([("url", "=", "/join")]):
        if join.parent_id.name == ABOUT_NAME:
            continue  # already grouped, nothing to do

        top = join.parent_id
        about = Menu.search(
            [
                ("name", "=", ABOUT_NAME),
                ("parent_id", "=", top.id),
                ("website_id", "=", join.website_id.id),
            ],
            limit=1,
        )
        if not about:
            about = Menu.create({
                "name": ABOUT_NAME,
                "url": "#",
                "parent_id": top.id,
                "website_id": join.website_id.id,
                "sequence": 30,
            })
            _logger.info("faizy_website: created the About Us menu")

        for url, sequence in CHILDREN.items():
            child = Menu.search(
                [("url", "=", url), ("website_id", "=", join.website_id.id)],
                limit=1,
            )
            if child:
                child.write({"parent_id": about.id, "sequence": sequence})
            elif url == "/privacy":
                # The privacy page shipped without a menu entry of its own.
                Menu.create({
                    "name": "Privacy policy",
                    "url": url,
                    "parent_id": about.id,
                    "website_id": join.website_id.id,
                    "sequence": sequence,
                })
        _logger.info("faizy_website: grouped %s under About Us", ", ".join(CHILDREN))
