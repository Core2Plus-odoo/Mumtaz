{
    'name': 'Faizy Pilot: Evidence Gate',
    'version': '19.0.1.1.0',
    'category': 'Services',
    'summary': 'Completion evidence gate: reviewed proof and receipt before an order completes or is billed',
    'description': """
Faizy Pilot: Evidence Gate
==========================
Additive to Faizy Core; nothing in faizy_core is edited and faizy.order.state is unchanged.

* ``evidence_state`` (none / submitted / approved / rejected) with reviewer, date and a mandatory reject reason.
* An order cannot be completed (button, RPC, kanban drag or ORM write) unless its proof photo is approved and,
  when ``purchase_value`` is above zero, its receipt photo too. Billing (draft customer invoice + wallet debit)
  runs only after the gate passes, because the gate sits in front of the billing override.
* Exception path: Faizy / Manager only, with a written reason, logged in the chatter.
* The proof and receipt images become staff-only fields. A customer sees an image only after it is approved,
  through one reviewed route (/faizy/evidence/<order>/<proof|receipt>) that applies the order record rule first.
* No new groups, no new models. Reviewers use Faizy / Operations; the exception uses Faizy / Manager.
""",
    'author': 'C2P Consultants',
    'license': 'LGPL-3',
    'depends': ['faizy_core'],
    'data': [
        'views/faizy_order_views.xml',
        'views/evidence_queue_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
