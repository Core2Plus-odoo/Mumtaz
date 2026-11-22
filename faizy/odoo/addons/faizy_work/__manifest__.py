{
    'name': 'Faizy Work: Checklists, Staff Desks and KPIs',
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'Checklist-driven staff work on the existing CRM lead, FAIZY order, vendor and draft records',
    'description': """
Faizy Work
==========
Additive to Faizy Core, Faizy AI and Faizy Pilot. Nothing in those modules is edited.

* ONE lightweight checklist mechanism (template -> checklist -> lines) that attaches to the
  business record (CRM lead, FAIZY order, vendor, AI draft) or stands alone for daily and weekly
  reviews. The business record stays the source of truth.
* Versioned templates, mandatory and conditional items, evidence links, SOP shown inline,
  Ready for Review, Blocked with escalation, reject and reopen with history, no self-approval
  of restricted items.
* Server-side gates: CRM prospect status, order assignment and completion, draft approval.
* Standard CRM is extended (originator, prospect status, verification evidence, duplicate guard).
  No second CRM, task or approval module.
* KPI scorecards computed from real records, with "Insufficient data" and a baseline period.
* My Work desk for each employee and a founder command centre with drill-down.
* Customer WhatsApp sending is untouched and stays off. Nothing here messages a customer.
""",
    'author': 'C2P Consultants',
    'license': 'LGPL-3',
    'depends': ['faizy_core', 'faizy_ai', 'faizy_pilot', 'crm', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/params.xml',
        'data/template_data.xml',
        'data/cron.xml',
        'views/checklist_views.xml',
        'views/record_views.xml',
        'views/desk_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
