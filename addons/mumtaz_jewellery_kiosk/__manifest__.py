{
    'name': 'Mumtaz Jewellery: Virtual Sales Officer (kiosk)',
    'version': '19.0.1.0.0',
    'summary': 'Noor, the conversational kiosk for clients: shelf at the approved rate, viewing, next-day delivery request',
    'description': """
The Virtual Sales Officer: a conversational kiosk on a tablet in the store
and on the web, for clients. It shows what is on the shelf at the approved
gold rate, sets a piece aside for a viewing, or takes a next-day delivery
request.

What holds, whatever the client says or the agent hears:

* The kiosk is public and holds no client records. It reads the shelf and
  the approved rate through public endpoints that carry no internal ids and
  no client data, and writes exactly one thing: a request.
* **A request is not a reservation and not a sale.** A person confirms it:
  confirmation matches or creates the client, opens an opportunity and a
  draft quotation priced from the approved rate; stock moves only when the
  order is confirmed and paid, as at the counter. Next-day delivery is a
  promise a person makes after confirming availability and payment, never
  the kiosk.
* Requests are capped per phone and per day, and every one is logged.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Sales/CRM',
    'depends': ['mumtaz_jewellery_crm', 'mumtaz_jewellery_ai'],
    'data': [
        'security/ir.model.access.csv',
        'data/kiosk_data.xml',
    ],
    'installable': True,
    'application': False,
}
