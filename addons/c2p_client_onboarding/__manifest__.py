{
    "name": "C2P Client Onboarding",
    "summary": "Client master record and onboarding checklist over the existing "
               "partner and Consultants–Solutions project pair",
    "description": """
C2P Client Onboarding
=====================
Turns the existing client ``res.partner`` into a client master record and adds
an onboarding checklist to the existing portfolio (Consultants) project.

It adds no client, engagement or project model and creates no project: the
engagement is the portfolio project from ``c2p_project_tracker`` and its
Solutions side is that project's counterpart.

The access register stores *references* to a credential vault. It has no field
for a password or key, and refuses text that looks like one.

Community only — no Enterprise dependency.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "author": "Core2Plus (C2P Consultants)",
    "website": "https://www.core2plus.com",
    "license": "LGPL-3",
    "depends": ["c2p_project_tracker"],
    "data": [
        "security/ir.model.access.csv",
        "security/c2p_client_onboarding_rules.xml",
        "data/mail_template.xml",
        "views/c2p_onboarding_check_views.xml",
        "views/c2p_client_register_views.xml",
        "views/project_project_views.xml",
        "views/res_partner_views.xml",
        "views/c2p_client_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
