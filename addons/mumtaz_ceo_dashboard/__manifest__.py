# -*- coding: utf-8 -*-
{
    "name": "Mumtaz CEO Dashboard — Media Buying",
    "version": "19.0.1.1.2",
    "summary": "Executive dashboard for a media-buying agency: billings, "
               "revenue, channel mix, budget pacing, campaigns & receivables.",
    "description": """
Mumtaz CEO Dashboard (Media Buying)
===================================
A standalone, self-contained executive dashboard rendered as an OWL client
action. Designed for the CEO of a media-buying agency across TV & Radio, Print,
Digital & Social and Outdoor (OOH).

* Gross media billings by channel (monthly, stacked)
* Net revenue trend (commission + fees)
* Blended margin, active campaigns, receivables KPIs
* Top clients & top media vendors
* Budget pacing vs plan
* Campaign watchlist with pacing & margin
* Accounts-receivable ageing

Ships with illustrative sample data for design sign-off; depends only on
``web`` so it installs on any Odoo 19 database. Light theme by default with an
in-dashboard light/dark toggle.
""",
    "author": "Core2Plus",
    "website": "https://mumtaz.digital",
    "category": "Mumtaz/Reporting",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [
        "views/ceo_dashboard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mumtaz_ceo_dashboard/static/src/scss/ceo_dashboard.scss",
            "mumtaz_ceo_dashboard/static/src/xml/ceo_dashboard.xml",
            "mumtaz_ceo_dashboard/static/src/js/ceo_dashboard.js",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": True,
}
