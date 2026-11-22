{
    'name': 'Jawhar: public website door',
    'version': '19.0.1.0.0',
    'summary': 'Demo requests from the public site land in the CRM, with consent recorded',
    'description': """
The one thing the public website writes: a demo request.

* The form on jewel.mumtaz.digital posts to a public endpoint that creates a
  demo request and a CRM lead tagged "Jawhar demo". No session, no internal
  ids in the response, a per-contact daily cap, a honeypot for bots.
* Consent is stored with the request: what the visitor agreed to, when, and
  from which page. Nothing is sent to the visitor by the system; a person
  follows up.
* The request keeps the lead's provenance; a manager sees requests under
  CRM > Jawhar demo requests.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Website',
    'depends': ['crm', 'mail', 'mumtaz_jewellery'],
    'data': [
        'security/ir.model.access.csv',
        'data/website_data.xml',
        'views/demo_request_views.xml',
    ],
    'installable': True,
    'application': False,
}
