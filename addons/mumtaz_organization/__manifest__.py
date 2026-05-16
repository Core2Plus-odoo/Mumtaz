{
    "name": "Mumtaz Organization",
    "summary": "White-label org management — /org/<slug>/ portal + SME signup flow",
    "version": "19.0.1.0.0",
    "category": "Mumtaz Platform",
    "author": "Mumtaz",
    "license": "LGPL-3",
    "depends": ["portal", "base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/org_data.xml",
        "views/org_portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "mumtaz_organization/static/src/css/org_portal.css",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
