{
    'name': 'Faizy AI Team',
    'version': '19.0.1.4.0',
    'category': 'Services',
    'summary': 'AI team layer for Faizy: draft-and-approve queue, inbound WhatsApp log, agent users, daily digest',
    'description': """
Faizy AI Team
=============
Adds the AI team to Faizy Core without changing it.

* AI agents (CoS, Insights, Intezam, Rabta, Noor, Kalam, Tasveer, Awaaz, Jor) can only DRAFT.
* Mashood (communications approver) approves customer-facing drafts; Raza (Faizy / Operations)
  approves order drafts; Umer (Faizy / Manager) can approve anything.
* An approved customer message becomes a queued faizy.whatsapp.message only inside working hours
  (10am to 9pm Karachi); otherwise it is held until the hours open.
* Inbound WhatsApp webhook and log (faizy_core only sends).
* Read-only daily digest for the Insights and Chief of Staff agents.
* Knowledge notes and recent rejection reasons that each agent reads before it drafts (get_brief).
* Work routing: every piece of work is a standard activity on the real record, on the right
  person's desk, with a checklist and an escalation window. Leads route to their salesperson.
* My desk: each person's waiting, overdue, done and lead numbers; the manager sees the team.
""",
    'author': 'C2P Consultants',
    'license': 'LGPL-3',
    'depends': ['faizy_core', 'mail', 'crm'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/core_access.xml',
        'data/data.xml',
        'data/cron.xml',
        'data/knowledge_data.xml',
        'views/ai_views.xml',
        'views/menus.xml',
        'data/routing_data.xml',
        'views/routing_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
}
