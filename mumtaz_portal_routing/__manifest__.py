{
    'name': 'Mumtaz Portal Routing',
    'version': '19.0.1.0.0',
    'summary': 'Multi-portal experience layer with role-based routing and menu isolation',
    'description': """
Phase 9 — Portal Separation & Experience Layer
===============================================

Transforms Mumtaz from a monolithic Odoo interface into a multi-portal
SaaS platform with clean product separation and role-based routing.

Portals
-------
1. Admin Control Plane  — platform admins manage tenants, bundles, provisioning
2. ERP Portal           — ERP users access CRM, lead scraper, lead nurture, marketplace
3. ZAKI AI Portal       — CFO users access financial analytics, AI assistant, transactions
4. Marketplace Portal   — SME users browse and list on the B2B marketplace

Capabilities
------------
- Login redirect: auto-route users to their portal after login
- Menu isolation: each portal shows only relevant menus
- Portal gate groups: bundle permissions cleanly per product area
- Portal home pages: dedicated landing dashboard per portal
- Tenant context awareness: portal pages are company-scoped
- Portal switcher: super-admins can navigate across portals
    """,
    'author': 'Mumtaz',
    'category': 'Mumtaz/Portal',
    'license': 'LGPL-3',
    'depends': [
        'web',
        'website',
        'mumtaz_core',
        'mumtaz_tenant_manager',
        'mumtaz_cfo_base',
    ],
    'data': [
        'security/portal_routing_security.xml',
        'security/ir.model.access.csv',
        'data/portal_home_actions.xml',
        'views/portal_layout_template.xml',
        'views/portal_admin_template.xml',
        'views/portal_erp_template.xml',
        'views/portal_zaki_template.xml',
        'views/portal_marketplace_template.xml',
        'views/portal_switcher_template.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'mumtaz_portal_routing/static/src/css/portal.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
