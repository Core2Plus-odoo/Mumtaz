{
    'name': 'Mumtaz Jewellery VIP & Upsell',
    'version': '19.0.1.0.0',
    'summary': 'Premium / royal client tiers, restricted records, private viewings, occasions, next-best-offer',
    'description': """
Client layer for Mumtaz Jewellery.

* Client tiers: Standard, Preferred, Private, Royal / Protocol.
* Private and Royal records visible only to the named relationship manager,
  the deputy and VIP managers; every view is logged.
* Pieces on approval (memo) with return deadline and reminders.
* Occasion calendar that prepares drafts for staff; nothing is sent
  automatically to Private or Royal clients.
* Next-best-offer: deterministic, explainable ranking of in-stock pieces.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Industries',
    'depends': ['mumtaz_jewellery', 'mail', 'stock'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/stock_data.xml', 'data/cron.xml',
        'views/vip_views.xml',
    ],
    'installable': True,
}
