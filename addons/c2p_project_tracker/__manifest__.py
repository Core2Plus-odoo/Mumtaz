{
    "name": "C2P Project Tracker",
    "summary": "Portfolio and delivery tracking across the C2P consulting group",
    "description": """
C2P Project Tracker
===================
Executive portfolio view for the Managing Partner and a delivery control view
for the C2P Solutions lead, over the existing two-layer project structure:
milestone projects in C2P Consultants and delivery projects in C2P Solutions.

Community only — no Enterprise dependency.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "author": "Core2Plus (C2P Consultants)",
    "website": "https://www.core2plus.com",
    "license": "LGPL-3",
    # project brings project.milestone and project.update, both Community.
    # mail is needed for the chatter notes the sync engine posts.
    "depends": ["project", "mail"],
    "data": [
        "security/c2p_project_tracker_groups.xml",
        "security/ir.model.access.csv",
        "security/c2p_project_tracker_rules.xml",
        "data/ir_sequence.xml",
        "data/ir_cron.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
