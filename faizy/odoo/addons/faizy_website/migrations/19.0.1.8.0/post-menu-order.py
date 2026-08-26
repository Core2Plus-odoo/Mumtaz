"""Put the header menu back in business-flow order.

The bar rendered as Home · Plans · **Start free** · Become a Faizy · WhatsApp,
with the one orange call-to-action stranded in the middle of the navigation.
The data file has always said Plans 20, Become a Faizy 30, WhatsApp 35, Start
free 40 — but `website_menu_data.xml` is `noupdate="1"`, so those numbers only
ever applied on the run that created each record. Anything that reordered them
afterwards, in the editor or by hand, stuck permanently.

noupdate is right for this file: reordering the menu is marketing's call and a
module upgrade should not undo it. But the current order is not a decision
anyone made, and "Start free" sitting third reads as an accident, so this
normalises it once.

Only touches the four menus we own, matched by URL, and only on the menus of
websites that have them. Anything else in the bar — Home, Contact us, whatever
somebody has added — keeps its own sequence.
"""

from odoo import SUPERUSER_ID, api

# url -> sequence. Browsing options first, then the way to talk to us, then the
# one thing we want pressed.
ORDER = {
    "/pricing": 20,
    "/join": 30,
    "/whatsapp": 35,
    "/start": 40,
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    menus = env["website.menu"].search([("url", "in", list(ORDER))])
    for menu in menus:
        wanted = ORDER[menu.url]
        if menu.sequence != wanted:
            menu.sequence = wanted
