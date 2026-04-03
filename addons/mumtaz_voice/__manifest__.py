{
    "name": "Mumtaz CFO Voice Assistant",
    "summary": "AI-powered CFO Voice Assistant - query your Odoo financials by voice or text",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "author": "Mumtaz",
    "license": "LGPL-3",
    "depends": ["mumtaz_ai", "mumtaz_core", "account", "mumtaz_control_plane"],
    "data": [
        "security/mumtaz_voice_security.xml",
        "security/ir.model.access.csv",
        "views/mumtaz_voice_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mumtaz_voice/static/src/xml/voice_assistant.xml",
            "mumtaz_voice/static/src/js/voice_assistant.js",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": True,
}
