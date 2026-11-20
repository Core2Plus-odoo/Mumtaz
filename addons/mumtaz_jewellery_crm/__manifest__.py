{
    'name': 'Mumtaz Jewellery: Sales Hub',
    'version': '19.0.1.0.0',
    'summary': 'Pipeline, Private Tray, client link, viewing request and reservation',
    'description': """
Plan v3, slice 2. Most of it is standard crm: an opportunity per client
moment, jewellery stages (Enquiry -> Tray shared -> Viewing booked ->
Reserved -> Won), activities for viewings, the reservation a draft
quotation priced from the approved rate.

What is ours: the Private Tray -- three to five pieces chosen by the
deterministic ranking that stores its reasons (or by hand for Private and
Royal clients, who are never scored) -- and the tokenised, expiring,
revocable link a client opens on her phone to like, ask or request a
viewing. A request is not a reservation: staff reserve.

Restricted tiers: a Royal client's tray never leaves the building (no link);
a tray of a restricted client is visible only to the people the client
record is visible to; the public page carries no client data and no
internal ids.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Sales/CRM',
    'depends': ['crm', 'mumtaz_jewellery_vip', 'mumtaz_jewellery_sale'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/crm_data.xml',
    ],
    'installable': True,
    'application': False,
}
