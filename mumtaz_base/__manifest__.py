{
    "name": "Mumtaz Base",
    "summary": "Base customizations for Mumtaz in Odoo Community",
    "version": "16.0.1.0.0",
    "category": "Contacts",
    "author": "Mumtaz",
    "license": "LGPL-3",
    "depends": ["base", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
}
