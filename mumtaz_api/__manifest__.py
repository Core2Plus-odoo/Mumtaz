{
    'name': 'Mumtaz Public API',
    'version': '19.0.1.0.0',
    'summary': 'REST API for website forms and partner integrations',
    'description': """
        Public-facing JSON API endpoints:
        - POST /api/mumtaz/v1/demo         — demo request → CRM lead
        - POST /api/mumtaz/v1/contact      — contact form → CRM lead
        - GET  /api/mumtaz/v1/health       — health check
        Supports CORS for mumtaz.digital static website.
    """,
    'author': 'Mumtaz Digital',
    'website': 'https://mumtaz.digital',
    'category': 'Mumtaz/API',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'crm', 'mumtaz_core'],
    'data': [],
    'assets': {},
    'installable': True,
    'auto_install': False,
    'application': False,
}
