{
    "name": "Mumtaz Digital - Native Website Builder Blocks",
    "summary": "Mumtaz Digital marketing homepage as native Odoo Website Builder blocks, with a CRM demo form",
    "description": "Seven reusable Website Builder blocks (hero, three pathways, ERP modules, industry editions, ZAKI AI, white-label partners, CRM demo form) and an unpublished preview page at /mumtaz-native-preview. CSS is scoped to .o_mumtaz_site so other websites on the same database are untouched. Nothing is published or set as homepage by installation.",
    "version": "19.0.1.0.0",
    "category": "Website/Website",
    "license": "LGPL-3",
    "author": "Mumtaz Digital",
    "depends": ["website", "website_crm"],
    "data": [
        "data/crm_tags.xml",
        "views/snippets/mumtaz_blocks.xml",
        "views/snippets/mumtaz_snippets.xml",
        "data/website_page.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "mumtaz_website_builder/static/src/css/mumtaz_builder.css",
        ],
    },
    "installable": True,
    "application": False,
}
