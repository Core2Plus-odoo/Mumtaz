{
    'name': 'Jawhar API',
    'version': '19.0.1.0.0',
    'summary': 'JSON API the Jawhar front end and agents talk to',
    'description': """
The gateway between the Jawhar product interface and Odoo.

Jawhar is a standalone product whose interface is not the Odoo web client.
This module is the one door that interface uses. Every endpoint:

* runs as the signed-in Odoo user, so access rights and record rules apply
  exactly as they do in the web client -- the API cannot see more than the
  person can;
* returns figures that come from the pricing engine and the approved gold
  rate, never computed or rounded on the client;
* is recorded in an audit row (who, what, when, how long, outcome).

Phase 0 is read-only: sign in, see the rate, the pieces, the clients, the
documents and the owner's cards. Writes arrive with their autonomy level
(A read, B recommend, C draft, D execute with named approval, E prohibited)
in later phases; nothing here writes business data.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Industries',
    'depends': [
        'mumtaz_jewellery',
        'mumtaz_jewellery_vip',
        'mumtaz_jewellery_owner',
        'mumtaz_jewellery_sale',
        'mumtaz_jewellery_crm',
        'mumtaz_jewellery_ai',
        'mumtaz_jewellery_kiosk',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
}
