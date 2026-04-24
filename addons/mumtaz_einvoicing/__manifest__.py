{
    'name': 'Mumtaz E-Invoicing',
    'summary': 'UAE FTA, KSA ZATCA Phase 2, and Pakistan FBR e-invoicing compliance',
    'version': '19.0.1.0.0',
    'category': 'Mumtaz Platform',
    'author': 'Mumtaz',
    'license': 'LGPL-3',
    'depends': ['account', 'base_setup'],
    'data': [
        'security/mumtaz_einvoice_security.xml',
        'security/ir.model.access.csv',
        'data/mumtaz_einvoice_data.xml',
        'views/mumtaz_einvoice_config_views.xml',
        'views/mumtaz_einvoice_views.xml',
        'views/mumtaz_einvoice_menus.xml',
    ],
    'assets': {
        'web.assets_backend': ['mumtaz_einvoicing/static/src/css/einvoice.css'],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
