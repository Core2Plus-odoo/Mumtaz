{
    "name": "Mumtaz Subdomain Routing",
    "summary": "Host/subdomain → tenant database routing for *.erp.mumtaz.digital "
               "(database-per-tenant). Additive and disabled by default.",
    "version": "19.0.1.0.0",
    "category": "Mumtaz Platform",
    "author": "Mumtaz",
    "license": "LGPL-3",
    "depends": ["mumtaz_tenant_manager"],
    "data": [
        "data/config_params.xml",
        "views/tenant_views.xml",
    ],
    "post_load": "post_load",
    "installable": True,
    "application": False,
    "auto_install": False,
}
