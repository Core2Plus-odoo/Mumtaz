{
    "name": "C2P Meeting Actions",
    "summary": "Minutes of meeting, with action items that become tasks exactly once",
    "description": """
C2P Meeting Actions
===================
A formal minutes-of-meeting record — attendees, agenda, discussion, decisions —
whose action items carry a durable reference and convert into standard
``project.task`` records.

The conversion is idempotent under concurrency. The guard is a database unique
constraint on the reference stamped onto the created task, not a Python check:
two simultaneous requests cannot both win an insert, so one creates the task and
the other adopts it.

Community only — no Enterprise dependency.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "author": "Core2Plus (C2P Consultants)",
    "website": "https://www.core2plus.com",
    "license": "LGPL-3",
    "depends": ["project", "mail"],
    "data": [
        "security/c2p_meeting_groups.xml",
        "security/ir.model.access.csv",
        "security/c2p_meeting_rules.xml",
        "data/ir_sequence.xml",
        "views/c2p_meeting_views.xml",
        "views/c2p_meeting_action_views.xml",
        "views/c2p_meeting_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
