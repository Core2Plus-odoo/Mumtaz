{
    'name': 'Mumtaz Jewellery: price to sale',
    'summary': 'Carry the approved-rate price onto quotations and orders, with a frozen snapshot',
    'description': """
Slice 1. A jewellery line is priced from the gold rate that a second person
approved, and the components of that price are snapshotted onto the line.

The snapshot is the point. Gold moves daily; a confirmed order must not. Once
an order leaves draft, the price and every snapshot field are frozen in the
ORM, so a rate change tomorrow cannot silently restate what a client already
agreed to.
""",
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'author': 'Mumtaz',
    'category': 'Sales',
    'depends': ['mumtaz_jewellery', 'sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_views.xml',
    ],
    'installable': True,
    'application': False,
}
