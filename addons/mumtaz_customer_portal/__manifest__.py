{
    'name': 'Mumtaz Customer Portal',
    'summary': 'Branded customer portal with e-invoicing QR support',
    'version': '19.0.1.0.0',
    'category': 'Mumtaz Platform',
    'author': 'Mumtaz',
    'license': 'LGPL-3',
    'depends': ['portal', 'sale_management', 'account', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_home_override.xml',
        'views/portal_invoice_override.xml',
        'views/portal_order_override.xml',
    ],
    'assets': {
        'web.assets_frontend': ['mumtaz_customer_portal/static/src/css/customer_portal.css'],
    },
    'installable': True,
    'auto_install': False,
}
