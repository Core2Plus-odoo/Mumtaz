{
    'name': 'Mumtaz Jewellery: Stores and transfers',
    'version': '19.0.1.0.0',
    'summary': 'Multi-store custody on standard warehouses, two-sided transfers, daily fine-gram reconciliation',
    'description': """
Stores and transfers (plan v3 slice "Stores", architecture review R7/R8):

* **A store is a warehouse** (standard). Each store carries its pieces, its
  fine gold in grams, its value at the approved rate and an optional
  fine-gram limit the owner sets.
* **Transfers are two-sided.** The sending store dispatches: the pieces move
  to the company's transit location through standard stock moves. The
  receiving store receives them, by serial; a transfer that stays in
  transit past the expected days, or is reported lost, is an exception on
  the decision cards. Ownership and valuation never change in transit.
* **Reconciliation in fine grams, per store, per day.** Odoo reconciles
  value and quantity; the shop counts metal. A run snapshots what the store
  should hold, a person scans what is there, and the variance is stated in
  pieces and fine grams, missing serials named. A manager closes it with a
  note; an open variance is a card.
* Store staff see their own store's transfers and runs; managers see all.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Inventory/Inventory',
    'depends': ['mumtaz_jewellery_vip', 'mumtaz_jewellery_owner', 'mumtaz_jewellery_api'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/stores_data.xml',
        'views/stores_views.xml',
    ],
    'installable': True,
    'application': False,
}
