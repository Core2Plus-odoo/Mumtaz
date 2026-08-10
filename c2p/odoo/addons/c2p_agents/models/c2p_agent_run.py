"""One row per agent run.

Why this exists: four crons ran nightly for an unknown period, executed nothing,
and reported success. Odoo's own cron log records that a job ran, not that it
did anything. This records both, so "scanned 0, acted on 0, every night for six
weeks" is a line in a list somebody can notice.

It deliberately does not record failures. A crash is already loud — Odoo marks
the cron failed and logs the traceback — and a row written here would be rolled
back with the transaction anyway. The quiet failure is the one that needed a
home.
"""

from odoo import fields, models

AGENTS = [
    ("lead_scoring", "Lead Scoring"),
    ("stale_opportunity", "Stale Opportunity Detection"),
    ("proposal_followup", "Proposal Follow-up"),
    ("invoice_chaser", "Invoice Chaser"),
]


class C2pAgentRun(models.Model):
    _name = "c2p.agent.run"
    _description = "C2P Agent Run"
    _order = "executed_at desc, id desc"
    _rec_name = "agent"

    agent = fields.Selection(AGENTS, required=True, index=True)
    executed_at = fields.Datetime(
        required=True, default=fields.Datetime.now, index=True
    )
    dry_run = fields.Boolean(
        help="A dry run selects and reports but writes nothing.",
    )
    scanned = fields.Integer(
        string="Records Scanned",
        help="How many records the agent's domain selected.",
    )
    acted = fields.Integer(
        string="Records Acted On",
        help="How many records the agent changed — or, on a dry run, would "
        "have changed.",
    )
    limit_applied = fields.Integer(string="Limit")
    note = fields.Text()
