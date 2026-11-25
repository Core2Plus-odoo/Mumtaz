{
    "name": "C2P Work Hub",
    "summary": "My Work Today and fifteen-second task updates",
    "description": """
C2P Work Hub
============
One page per employee showing the work that is actually theirs, and a single
call that records a progress update, a blocker or a next action without opening
a form.

Reads standard ``project.task``. Adds no second task model, no second blocker
field and no second stage concept. Installs standalone; when
``c2p_project_tracker`` is present it reuses that module's ``blocked_reason``
rather than declaring its own.

Community only — no Enterprise dependency.
""",
    "version": "19.0.1.0.1",
    "category": "Services/Project",
    "author": "Core2Plus (C2P Consultants)",
    "website": "https://www.core2plus.com",
    "license": "LGPL-3",
    "depends": ["project", "web", "mail"],
    "data": [
        "views/c2p_work_hub_actions.xml",
        "views/c2p_work_hub_menus.xml",
        "views/project_task_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "c2p_work_hub/static/src/work_hub/work_hub.scss",
            "c2p_work_hub/static/src/work_hub/work_hub.js",
            "c2p_work_hub/static/src/work_hub/work_hub.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
