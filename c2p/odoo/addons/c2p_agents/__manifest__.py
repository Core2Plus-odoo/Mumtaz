{
    "name": "C2P Agents",
    "summary": "The four nightly CRM and receivables agents, as versioned code",
    "description": """
C2P Agents
==========

Four scheduled agents that previously lived as Python in the ``code`` field of
``ir.actions.server`` records, created directly in the database:

* **Lead scoring** — rule-based priority on ``crm.lead``.
* **Stale opportunity detection** — high-priority opportunities that have gone
  quiet get a To-Do.
* **Proposal follow-up** — leads parked in a proposal stage get a Call.
* **Invoice chaser** — overdue posted customer invoices get a Call on the owner.

All four were found silently empty: the crons ran every night, executed nothing,
and reported success. Code in a database field cannot be reviewed, diffed,
tested or rolled back, which is why it moved here.

Safety
------

The module installs **inert**. ``c2p_agents.dry_run`` defaults to ``True``, so
the agents run on schedule, log and record exactly what they would have touched,
and write nothing. Set the parameter to ``False`` to arm them.

Every run — dry or live — writes a ``c2p.agent.run`` row. A run that scans
nothing and acts on nothing is visible in the UI rather than buried in the
server log, which is the failure this module exists to make impossible.

See ``docs/migration-from-server-actions.md`` for moving the existing crons over
without losing their schedules.
""",
    "version": "19.0.1.0.0",
    "category": "Sales/CRM",
    "author": "C2P Consultants",
    "website": "https://core2plus.com",
    "license": "LGPL-3",
    "depends": [
        "crm",
        "mail",
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/c2p_agents_params.xml",
        "data/c2p_agents_cron.xml",
        "views/c2p_agent_run_views.xml",
        "views/crm_stage_views.xml",
    ],
    # Ticks "Proposal Stage" on stages that already look like proposal stages,
    # so the follow-up agent has something to select on the day it installs.
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
    "application": False,
}
