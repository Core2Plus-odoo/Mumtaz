{
    'name': 'Mumtaz Jewellery Owner Command Centre',
    'version': '19.0.1.0.0',
    'summary': 'One morning screen of decisions: what happened, why it matters, what to do',
    'description': """
Decision cards for the owner. Each card says what happened, the recommended
action and the money involved. Cards open the underlying record, so every
approval still runs under the user's own permissions. Cards about Private and
Royal clients are visible only to VIP managers.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Industries',
    'depends': ['mumtaz_jewellery_vip'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/owner_views.xml',
    ],
    'installable': True,
}
