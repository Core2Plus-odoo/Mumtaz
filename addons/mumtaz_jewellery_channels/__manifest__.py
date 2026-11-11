{
    'name': 'Mumtaz Jewellery: Channels',
    'version': '19.0.1.0.0',
    'summary': 'Rate-feed adapter that drafts for approval; publication control for the web shelf; requests by channel',
    'description': """
Channels (plan v3 slice "Channels"):

* **Rate feed, draft only.** An adapter reads a 24K price from a provider
  (a fixture for tests and demos, or a JSON endpoint over HTTPS with a
  value path and a unit) and enters it as a **draft** gold rate with
  source "feed". The maker-checker rule is untouched: a person approves,
  the feed never does, and prices keep the previous approved rate until
  then. Every fetch is logged with the raw value, the converted value, the
  draft it made or the error.
* **The web shelf is the storefront.** Each design has a publication
  switch; the public shelf (kiosk in the store, the same shelf on the web)
  shows only published designs that are on a shelf and priced from the
  approved rate. `website_sale` is deliberately not used: it cannot price a
  serial-tracked piece from a live rate without rebuilding the engine in a
  second place (see the reconciliation doc).
* **Requests by channel**: what came from the in-store kiosk and what came
  from the web, so the owner sees which door is working.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Sales/Sales',
    'depends': ['mumtaz_jewellery_kiosk', 'mumtaz_jewellery_owner', 'mumtaz_jewellery_api'],
    'data': [
        'security/ir.model.access.csv',
        'data/channels_data.xml',
        'views/channels_views.xml',
    ],
    'installable': True,
    'application': False,
}
