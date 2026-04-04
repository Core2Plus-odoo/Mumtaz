{
    'name': 'Mumtaz App Portal',
    'version': '19.0.1.0.0',
    'summary': 'Unified customer app portal — ERP, ZAKI AI, Marketplace, Account in one experience',
    'author': 'Core2Plus',
    'category': 'Mumtaz/Portal',
    'license': 'LGPL-3',
    'depends': [
        'web',
        'website',
        'mumtaz_core',
        'mumtaz_portal_routing',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/app_base_layout.xml',
        'views/app_home.xml',
        'views/app_erp.xml',
        'views/app_zaki.xml',
        'views/app_marketplace.xml',
        'views/app_account.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'mumtaz_app_portal/static/src/css/app.css',
            'mumtaz_app_portal/static/src/js/app.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}
