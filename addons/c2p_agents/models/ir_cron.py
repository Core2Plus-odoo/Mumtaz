"""Health at a glance for every scheduled action on the database.

Four crons ran nightly with an empty ``code`` field for an unknown period and
nobody could see it, because the Scheduled Actions list shows a name, a schedule
and an active flag — none of which change when the body of the job is blank.

This adds no table and stores nothing. It is two computed columns and a set of
filters over records Odoo already keeps, so there is no second copy of the truth
to drift. Deliberately covers *every* cron, not just this module's: the failure
being guarded against was never specific to C2P's agents.
"""

from datetime import timedelta

from odoo import api, fields, models

# How far past its nextcall a live cron must be before it counts as overdue.
# Generous, because a busy worker or a long-running job can legitimately push a
# schedule out by minutes without anything being wrong.
OVERDUE_HOURS = 6


class IrCron(models.Model):
    _inherit = "ir.cron"

    c2p_code_length = fields.Integer(
        string="Code Length",
        compute="_compute_c2p_health",
        help="Characters of Python in this action's body. Zero on a code "
        "action is the failure this column exists to expose.",
    )
    c2p_health = fields.Selection(
        [
            ("empty", "Empty code"),
            ("inactive", "Inactive"),
            ("never_ran", "Never ran"),
            ("overdue", "Overdue"),
            ("ok", "OK"),
        ],
        string="Health",
        compute="_compute_c2p_health",
        help="Empty code: the action is scheduled but its body is blank — it "
        "will run nightly and do nothing, reporting success.",
    )

    @api.depends("active", "code", "state", "lastcall", "nextcall")
    def _compute_c2p_health(self):
        """Worst-first. An empty body outranks everything except being off.

        Not stored, so the verdict is always computed from the record in front
        of you rather than from a cached answer that was true last month. The
        search-view filters use plain domains on the underlying fields for the
        same reason — nothing here can go stale.
        """
        cutoff = fields.Datetime.now() - timedelta(hours=OVERDUE_HOURS)
        for cron in self:
            code = (cron.code or "").strip()
            cron.c2p_code_length = len(code)
            if not cron.active:
                cron.c2p_health = "inactive"
            elif cron.state == "code" and not code:
                cron.c2p_health = "empty"
            elif not cron.lastcall:
                cron.c2p_health = "never_ran"
            elif cron.nextcall and cron.nextcall < cutoff:
                cron.c2p_health = "overdue"
            else:
                cron.c2p_health = "ok"
