{
    "name": "C2P Command Center",
    "summary": "One-page view of everything happening at C2P: outreach, pipeline, "
               "money, delivery, AI agents, content and system health",
    "description": """
C2P Command Center
==================
A single dashboard for the Managing Partner. Read-only aggregation over data
that already lives in Odoo — CRM, the BD outreach engine, invoices, client
projects, the AI Agents work board, the blog and scheduled actions. Every
number is clickable and opens the underlying records.

Community only — no Enterprise dependency.
""",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "Core2Plus (C2P Consultants)",
    "website": "https://www.core2plus.com",
    "license": "LGPL-3",
    "depends": ["web", "mail", "crm", "project", "account", "website_blog"],
    "data": [
        "security/c2p_command_center_groups.xml",
        "views/c2p_command_center_actions.xml",
        "views/c2p_command_center_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "c2p_command_center/static/src/command_center/command_center.scss",
            "c2p_command_center/static/src/command_center/command_center.js",
            "c2p_command_center/static/src/command_center/command_center.xml",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
