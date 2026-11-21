{
    "name": "Mumtaz Tenant Profile",
    "summary": "Controls what tenant (customer) users see in the Odoo backend",
    "version": "19.0.1.0.0",
    "category": "Mumtaz Platform",
    "author": "Mumtaz",
    "license": "LGPL-3",
    "depends": [
        "base",
        "crm",
        "mumtaz_lead_scraper",
        "mumtaz_lead_nurture",
        "mumtaz_control_plane",
    ],
    "data": [
        "security/tenant_profile_security.xml",
        "data/menu_restrictions.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
