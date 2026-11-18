{
    "name": "Pharma DEMO Website (fictional)",
    "summary": "Health and wellness demo storefront for the Pharma DEMO tenant: calm theme, DEMO ribbon on every page, demo home page, published DEMO products.",
    "description": "FICTIONAL demonstration website. Shows a DEMO ribbon on every public page while pharma.mode is "
                   "'demo', serves a demo home page explaining the three Pharma capabilities, and publishes the DEMO "
                   "products into two shop categories. Never install on a production database.",
    "version": "19.0.1.1.0",
    "category": "Pharma",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["website_sale", "pharma_demo_data"],
    "data": [
        "views/website_templates.xml",
        "data/website_pages.xml",
    ],
    "assets": {
        "web.assets_frontend": ["pharma_website_demo/static/src/css/wellness.css"],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
}
