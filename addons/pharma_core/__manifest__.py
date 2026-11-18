{
    "name": "Pharma Core",
    "summary": "Pharma Demo Co: shared foundation (roles, immutable raw-event archive, menus)",
    "version": "19.0.1.0.0",
    "category": "Pharma",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/pharma_security.xml",
        "security/ir.model.access.csv",
        "views/pharma_raw_event_views.xml",
        "views/pharma_menus.xml",
    ],
    "installable": True,
    "application": True,
}
