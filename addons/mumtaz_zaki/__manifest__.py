{
    "name": "Mumtaz ZAKI Connector",
    "summary": "Financial snapshot bridge for the ZAKI AI CFO agent",
    "version": "19.0.1.0.0",
    "category": "Mumtaz Platform",
    "author": "Mumtaz",
    "license": "LGPL-3",
    "depends": ["account", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "reports/board_pack_report.xml",
        "reports/board_pack_template.xml",
        "views/zaki_views.xml",
        "data/zaki_cron.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
