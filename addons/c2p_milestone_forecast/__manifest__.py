{
    "name": "C2P Milestone Forecast",
    "summary": "Commitment date, forecast date and calculated health per milestone",
    "description": """
C2P Milestone Forecast
======================
Each project milestone keeps its commitment date (the standard milestone
deadline) and gains a forecast date. Health is calculated from the gap between
the two and is never rated by hand:

* Green: forecast on or before the commitment date.
* Amber: forecast later by 1 to 5 calendar days.
* Red: forecast later by more than 5 calendar days.
* No forecast (grey): no forecast entered. Never green.

A project shows the colour of its worst milestone. A reached milestone keeps
the colour it had when it was reached.

Changing a commitment date or a forecast date needs a reason, stored in the
same history entry as the tracked change.

No automations, no emails, no access rules. Community only.
""",
    "version": "19.0.1.0.1",
    "category": "Services/Project",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["project"],
    "data": [
        "views/project_milestone_views.xml",
        "views/project_project_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
