{
    'name': 'Mumtaz Jewellery',
    'version': '19.0.1.0.0',
    'summary': 'Jewellery edition: gold-rate pricing, piece-level stock, old-gold exchange',
    'description': """
Jewellery vertical for the Mumtaz platform (Odoo 19 Community).

* Gold rate with maker-checker approval; prices always computed from the
  approved rate in the database.
* Pricing per gram, tola and ounce: karat or fineness, wastage, making
  charge (percent, per gram, fixed), stones, VAT, dealer making discount.
* Serial-tracked pieces with weights, RFID tag and certificate reference.
* Old-gold exchange with melt loss, valuation and approval above a
  configurable threshold.

Compliance values (VAT rate, approval threshold) are configuration, not code.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Industries',
    'depends': ['stock', 'sale_management', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/config.xml',
        'views/jewellery_views.xml',
    ],
    'installable': True,
    'application': True,
}
