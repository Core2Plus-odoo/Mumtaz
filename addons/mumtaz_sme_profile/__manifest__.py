{
    "name": "Mumtaz SME Profile",
    "summary": "SME company profile, classification, and lifecycle management",
    "version": "19.0.1.1.0",
    "category": "Mumtaz Platform",
    "author": "Mumtaz",
    "license": "LGPL-3",
    "depends": [
        "mumtaz_branding",
        "mumtaz_tenant_manager",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/mumtaz_sme_profile_rules.xml",
        "security/sme_profile_tenant_rules.xml",
        "views/mumtaz_sme_profile_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
