{
    "name": "C2P Master Agent",
    "version": "19.0.1.0.1",
    "summary": "AI master agent embedded in Odoo — controls CRM, Projects, HR, Finance",
    "description": "Talk to your business. The C2P Master Agent reads your full Odoo system and acts on your commands — assign tasks, brief you on the pipeline, allocate team members, generate proposals.",
    "category": "Productivity",
    "author": "C2P Consultants",
    "website": "https://www.core2plus.com",
    "depends": ["base", "crm", "project", "hr", "account", "sale", "utm"],
    "data": [
        "security/c2p_master_agent_groups.xml",
        "security/ir.model.access.csv",
        "views/master_agent_views.xml",
        "views/master_agent_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "c2p_master_agent/static/src/css/agent.css",
            "c2p_master_agent/static/src/xml/agent_widget.xml",
            "c2p_master_agent/static/src/js/agent_widget.js",
        ],
    },
    "application": True,
    "installable": True,
    "license": "LGPL-3",
}
