{
    "name": "Mumtaz AI",
    "summary": "Pluggable AI interaction layer for Odoo Community",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "Mumtaz",
    "license": "LGPL-3",
    "depends": ["base", "mail", "account", "mumtaz_core"],
    "data": [
        "security/mumtaz_ai_security.xml",
        "security/ir.model.access.csv",
        "views/mumtaz_ai_session_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
}
