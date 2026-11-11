{
    'name': 'Mumtaz Jewellery: AML and KYC',
    'version': '19.0.1.0.0',
    'summary': 'Identity and screening on the client record; cash against a finance-confirmed threshold at the counter',
    'description': """
AML and KYC (plan v3 §17, architecture review R14):

* **Identity on the client record**: document type, the last four characters
  only (never the full number), expiry, who verified it and when. Screening
  result and risk band, set by a manager. Nothing here ever enters a model
  request.
* **The threshold is configuration, not code.** The cash threshold and the
  window it is counted over are empty until the named finance manager
  confirms them; until then the counter sells as before and a decision card
  asks for the values. Nothing here is validated law.
* **At the counter**: cash taken now plus the client's cash in the window is
  compared with the threshold. At or above it the sale needs a verified,
  unexpired identity and no screening match, else the commit refuses and
  nothing happened. Every crossing is written as an event finance can report
  on; the API door shows the check before the commit.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Accounting/Localizations',
    'depends': ['mumtaz_jewellery_sale', 'mumtaz_jewellery_vip', 'mumtaz_jewellery_owner', 'mumtaz_jewellery_api'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/partner_views.xml',
        'views/aml_views.xml',
    ],
    'installable': True,
    'application': False,
}
