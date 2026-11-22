{
    'name': 'Mumtaz Jewellery: Outreach',
    'version': '19.0.1.0.0',
    'summary': 'Occasion-driven messages Layla drafts, consent on the client record, a person sends',
    'description': """
Outreach (plan v3 slice "Outreach", autonomy level C with a level D send):

* **Consent lives on the client record**: not recorded, given, or withdrawn,
  with when, how and by whom. A message leaves only with recorded consent;
  a client without it gets a call note for her advisor, never a message.
* **Occasions drive the drafts**: each morning Layla drafts the messages
  for the occasions inside their lead time, one per client per year, for
  the relationship manager (or the deputy) to review. A Private or Royal
  client's draft takes the local path; nothing about her reaches a model.
* **A person sends.** An approved draft is handed to the named person as a
  link that opens the text in her own WhatsApp or mail client; the server
  never sends a message. Who handed it, when and on which channel is
  written on the draft and on the client's record.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Sales/CRM',
    'depends': ['mumtaz_jewellery_ai', 'mumtaz_jewellery_api'],
    'data': [
        'data/outreach_data.xml',
        'views/partner_views.xml',
    ],
    'installable': True,
    'application': False,
}
