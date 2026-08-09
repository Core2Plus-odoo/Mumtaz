{
    "name": "Faizy Website & Portal",
    "summary": "Public site, pricing, Faizy sign-up and the customer portal",
    "description": """
The customer-facing half of Faizy.

* Marketing pages carrying the brand: orange #F69E22, black #0A0A0A, Poppins,
  and the Urdu tagline حاضر ہیں۔ rendered with proper RTL shaping.
* Pricing driven by faizy.plan records, so changing a price is an ops edit
  rather than a deployment.
* A public application form for ground workers that feeds the admin pipeline
  and returns a FZY- reference the applicant can track.
* Portal pages where a customer sees their family, their orders and their
  remaining care activities.

The site's domain is configured on the Website record (Settings > Website), not
hardcoded here — see faizy/docs/02-odoo-deployment.md.
""",
    "version": "19.0.1.6.0",
    "category": "Website",
    "author": "C2P Consultants FZC LLC",
    "website": "https://faizy.pk",
    "license": "LGPL-3",
    "depends": ["website", "portal", "faizy_core"],
    "data": [
        "views/faizy_website_templates.xml",
        "views/faizy_portal_templates.xml",
        "data/website_menu_data.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "faizy_website/static/src/scss/faizy.scss",
        ],
    },
    # Odoo never changes its own favicon, so a finished site sits in the
    # tab bar looking like a generic Odoo install.
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
    "application": False,
}
