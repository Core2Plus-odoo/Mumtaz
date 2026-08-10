"""One row per agent run.

The reason this model exists: four crons ran nightly for an unknown period,
executed nothing, and reported success. Odoo's own cron log records that a job
ran, not that it did anything. This records both, so "scanned 0, acted on 0,
every night for six weeks" is a line in a list view somebody can notice.
"""

from odoo import api, fields, models

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
        help="How many records the agent's domain selected, before the limit "
        "on what it would act on.",
    )
    acted = fields.Integer(
        string="Records Acted On",
        help="How many records the agent changed — or, on a dry run, would "
        "have changed.",
    )
    limit_applied = fields.Integer(string="Limit")
    note = fields.Text()
    error = fields.Text()
    state = fields.Selection(
        [("ok", "Completed"), ("error", "Failed")],
        compute="_compute_state",
        store=True,
        index=True,
    )

    @api.depends("error")
    def _compute_state(self):
        for run in self:
            run.state = "error" if run.error else "ok"
