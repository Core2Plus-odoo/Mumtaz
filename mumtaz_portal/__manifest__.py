{
    'name': 'Mumtaz SME Portal',
    'version': '19.0.1.0.0',
    'summary': 'Customer-facing SME portal — Dashboard, AI CFO, CFO Workspace, Finance Hub',
    'description': """
        Web portal for SME users:
        /mumtaz/dashboard   — AI briefing, KPIs, onboarding progress
        /mumtaz/ai          — AI CFO conversational interface
        /mumtaz/cfo         — CFO workspace: upload, transactions, review
        /mumtaz/finance     — Finance Hub: credit score, matched offers
        /mumtaz/onboard     — Guided onboarding wizard
        /mumtaz/profile     — SME profile settings
    """,
    'author': 'Mumtaz Digital',
    'website': 'https://mumtaz.digital',
    'category': 'Mumtaz/Portal',
    'license': 'LGPL-3',
    'depends': [
        'portal',
        'website',
        'mumtaz_core',
        'mumtaz_sme_profile',
        'mumtaz_onboarding',
        'mumtaz_ai',
        'mumtaz_cfo_base',
        'mumtaz_cfo_transactions',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_layout.xml',
        'views/portal_dashboard.xml',
        'views/portal_ai.xml',
        'views/portal_cfo.xml',
        'views/portal_finance.xml',
        'views/portal_onboard.xml',
        'views/portal_profile.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'mumtaz_portal/static/src/css/portal.css',
            'mumtaz_portal/static/src/js/portal.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
