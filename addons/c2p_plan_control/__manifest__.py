{
    "name": "C2P Plan Control",
    "summary": "One approved delivery plan: contributors propose changes, the "
               "delivery owner decides in-scope ones, Consultants decide the rest",
    "description": """
C2P Plan Control
================
Protects the approved plan on the existing Solutions delivery project.

* A contributor proposes a change (a date, an assignee, a task adjustment, or a
  scope change) with a reason. They cannot alter a committed date, assignee,
  milestone or acceptance criteria directly.
* The delivery owner approves or rejects in-scope changes. Every change keeps
  who, when, why, the previous value, the new value and what it affects.
* A milestone date change keeps the original baseline next to the forecast and
  notifies the Consultants account owner.
* A scope, price or contract change is never applied here. It becomes exactly
  one standard change request on the paired Consultants engagement.

No new project or engagement model. Community only.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "author": "Core2Plus (C2P Consultants)",
    "website": "https://www.core2plus.com",
    "license": "LGPL-3",
    "depends": ["c2p_project_tracker"],
    "data": [
        "security/ir.model.access.csv",
        "security/c2p_plan_control_rules.xml",
        "data/ir_sequence.xml",
        "views/c2p_plan_change_views.xml",
        "views/project_views.xml",
        "views/c2p_plan_control_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
