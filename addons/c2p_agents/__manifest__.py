{
    "name": "C2P Agents",
    "summary": "Seven scheduled CRM and receivables agents, as versioned code",
    "description": """
C2P Agents

Seven scheduled agents for the C2P CRM, as a versioned module rather than Python
stored in ir.actions.server code fields.

Lead scoring sets priority on crm.lead. Stale opportunity detection raises a
To-Do on high-priority opportunities that have gone quiet. Proposal follow-up
chases leads parked in a proposal stage. The invoice chaser raises a call on the
owner of an overdue posted customer invoice. Email validation checks addresses
before outreach and routes to WhatsApp when an address is unusable. Owner
assignment gives every open lead a salesperson. The last agent raises a To-Do on
any owned lead with nothing scheduled.

The first four are ports of crons that ran as code in database fields, where
they could not be reviewed, diffed, tested or rolled back.

The module installs inert. The system parameter c2p_agents.dry_run defaults to
True, so the agents run on schedule, record what they would have touched, and
write nothing until it is set to False. Every run writes a c2p.agent.run row, so
an agent that quietly stops matching anything is visible rather than silent.

See docs/migration-from-server-actions.md for moving the existing crons over
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
    # dnspython, if installed, gives the email validation agent real MX lookups.
    # Deliberately NOT declared in external_dependencies: doing so would make
    # Odoo refuse to install the module without it. Absent, the domain layer
    # degrades to "does this domain resolve at all" — weaker, but still catching
    # most bounce sources — and every result records which check actually ran.
    "data": [
        "security/ir.model.access.csv",
        "data/c2p_agents_params.xml",
        "data/c2p_agents_cron.xml",
        "views/c2p_agent_run_views.xml",
        "views/ir_cron_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
