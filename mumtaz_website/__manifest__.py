{
    'name': 'Mumtaz Website',
    'version': '19.0.1.0.0',
    'summary': 'Marketing website for mumtaz.digital',
    'author': 'Core2Plus',
    'category': 'Mumtaz/Website',
    'license': 'LGPL-3',
    'depends': ['web', 'website'],
    'data': [
        'views/website_layout.xml',
        'views/home.xml',
        'views/features.xml',
        'views/pricing.xml',
        'views/contact.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'mumtaz_website/static/src/css/website.css',
            'mumtaz_website/static/src/js/website.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}
