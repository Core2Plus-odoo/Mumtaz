{
    "name": "Mumtaz Theme",
    "summary": "Rebrand Odoo Community backend and login to match Mumtaz platform identity",
    "version": "19.0.1.0.0",
    "category": "Mumtaz Platform",
    "author": "Mumtaz",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [
        "views/webclient_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mumtaz_theme/static/src/css/mumtaz_backend.css",
        ],
        "web.assets_frontend": [
            "mumtaz_theme/static/src/css/mumtaz_login.css",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
