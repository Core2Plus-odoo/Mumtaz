# -*- coding: utf-8 -*-
{
    "name": "Mumtaz Media Buying",
    "version": "19.0.1.0.4",
    "summary": "Media-buying business flow: vendors, outlets, rate cards, "
               "media plans with commission + fees, vendor POs & client orders.",
    "description": """
Mumtaz Media Buying
===================
The complete media-buying flow for an agency working across TV & Radio, Print,
Digital & Social and Outdoor (OOH), built standard-first on top of Odoo Sales,
Purchase and Invoicing:

* **Media Vendors** — flagged partners (channels, publishers, platforms,
  billboard owners).
* **Media Outlets** — the properties you buy on (a TV channel, a newspaper,
  a platform, a billboard site), each tied to a vendor and a channel type.
* **Rate Cards** — versioned vendor price lists with validity windows,
  gross vs negotiated rates per outlet/format.
* **Media Plans** — the campaign blueprint per client: lines priced from rate
  cards, agency commission % + service fee, approval workflow, and one-click
  generation of the client sale order and per-vendor purchase orders
  (no double entry).
* **CEO Dashboard feed** — a JSON endpoint that powers the standalone
  ``mumtaz_ceo_dashboard`` app with live billings, revenue, pacing, campaign
  and receivables data (the dashboard falls back to sample data when this
  module is absent or empty).
""",
    "author": "Core2Plus",
    "website": "https://mumtaz.digital",
    "category": "Mumtaz/Media",
    "license": "LGPL-3",
    "depends": ["mail", "sale", "purchase"],
    "data": [
        "security/media_security.xml",
        "security/ir.model.access.csv",
        "data/media_data.xml",
        "views/media_outlet_views.xml",
        "views/media_rate_card_views.xml",
        "views/media_plan_views.xml",
        "views/media_menus.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
}
