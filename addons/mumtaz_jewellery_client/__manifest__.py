{
    'name': 'Mumtaz Jewellery: Client app',
    'version': '19.0.1.0.0',
    'summary': "The client's own page: sign-in by one-time code, what she owns, her selections and requests, her choices",
    'description': """
Client app (roadmap slice 6, review R15):

* **Sign-in by one-time code**, never a password: she gives her phone, a
  six-digit code is created for ten minutes, and a person in the shop
  gives it to her (it shows on her record for staff); the server sends no
  message. Five wrong tries end the code; three codes an hour per phone.
  An unknown phone gets the same answer as a known one.
* **Her page**: today's approved rate; what she owns (the pieces she bought,
  with the metal value at today's rate, read from the engine); the
  selections prepared for her; her kiosk requests and their state; her
  marketing consent, which she may withdraw herself.
* **No payments, no prices invented, no agent.** The page reads the engine
  and her own records, scoped by the token alone; nothing about her enters
  a model request.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Website/Website',
    'depends': ['mumtaz_jewellery_sale', 'mumtaz_jewellery_crm', 'mumtaz_jewellery_kiosk', 'mumtaz_jewellery_outreach', 'mumtaz_jewellery_api'],
    'data': [
        'security/ir.model.access.csv',
        'data/client_data.xml',
    ],
    'installable': True,
    'application': False,
}
