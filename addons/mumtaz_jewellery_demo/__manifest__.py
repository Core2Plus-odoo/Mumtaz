{
    'name': 'Mumtaz Jewellery DEMO data',
    'version': '19.0.1.0.0',
    'summary': 'Synthetic DEMO data for the Jewel staging/demo database',
    'description': """
Seed data for a demonstration database. SYNTHETIC ONLY.

Every record this module creates is prefixed "DEMO". There are no real
client names, no real contact details, no keys and no tokens, per
docs/mumtaz-jewel/CLAUDE.md. Never install it on a database that holds real
client data: it adds visible DEMO records and two demo manager logins.

The gold rate is seeded through the real maker-checker path (one demo
manager enters it, a different demo manager approves it), so the demo
database shows the control working rather than a rate written straight to
'approved'.

The two demo users are created without a password and so cannot sign in
until somebody sets one deliberately.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Industries',
    'depends': [
        'mumtaz_jewellery',
        'mumtaz_jewellery_vip',
        'mumtaz_jewellery_owner',
        # So the demo leaves real priced documents behind: a quotation, a
        # confirmed order and a posted invoice. Without them Sales and
        # Invoicing are empty, which is the first thing anyone opens in a
        # demonstration.
        'mumtaz_jewellery_sale',
        'mumtaz_jewellery_crm',
        'mumtaz_jewellery_ai',
    ],
    'data': [],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
