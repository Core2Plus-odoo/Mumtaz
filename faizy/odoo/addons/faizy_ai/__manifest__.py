{
    'name': 'Faizy AI Team',
    'version': '19.0.1.0.0',
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
""",
    'author': 'C2P Consultants',
    'license': 'LGPL-3',
    'depends': ['faizy_core', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/core_access.xml',
        'data/data.xml',
        'data/cron.xml',
        'views/ai_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
}
