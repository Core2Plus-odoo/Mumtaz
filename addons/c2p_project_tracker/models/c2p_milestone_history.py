import contextvars

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# True only while `log()` is creating a row. It lives in this process, so it
# cannot be sent over the API the way a context key can: a caller who is not
# this module's own code cannot switch it on.
_INTERNAL_WRITE = contextvars.ContextVar("c2p_history_internal_write", default=False)


class C2pMilestoneHistory(models.Model):
    """Append-only record of every portfolio-milestone stage or deadline change.

    The dashboards' trend charts read this rather than recomputing from the
    current state, which cannot show what a milestone looked like last week.
    Rows are written by the sync engine and by manual edits alike, with `source`
    distinguishing them.
    """

    _name = "c2p.milestone.history"
    _description = "C2P Milestone Change History"
    _order = "change_date desc, id desc"
    _rec_name = "milestone_id"

    milestone_id = fields.Many2one(
        "project.task", string="Portfolio Milestone",
        required=True, ondelete="cascade", index=True)
    project_id = fields.Many2one(
        "project.project", string="Project",
        related="milestone_id.project_id", store=True, index=True)
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="milestone_id.company_id", store=True, index=True)

    change_date = fields.Datetime(
        required=True, default=fields.Datetime.now, index=True)
    source = fields.Selection(
        [("sync", "Auto-sync"), ("manual", "Manual")],
        required=True, default="sync")

    old_stage_id = fields.Many2one("project.task.type", string="Old Stage")
    new_stage_id = fields.Many2one("project.task.type", string="New Stage")
    old_deadline = fields.Date()
    new_deadline = fields.Date()

    # Snapshot of the delivery side at the moment of the change, so a trend
    # chart can show progress without re-deriving historical task states.
    done_task_count = fields.Integer()
    open_task_count = fields.Integer()
    waiting_task_count = fields.Integer()

    note = fields.Char()
    paired_company_id = fields.Many2one(
        "res.company", string="Paired Delivery Company",
        related="project_id.c2p_counterpart_id.company_id", store=True,
        index=True,
        help="Company of the paired delivery project. Lets that company read "
             "and log the history without access to the engagement itself.")

    _milestone_date_idx = models.Index("(milestone_id, change_date)")

    @api.model_create_multi
    def create(self, vals_list):
        # Rows are evidence. Only `log()` may write them: a direct create, an
        # import or an API call is refused, whatever group the caller is in.
        # The install and system-level code (superuser) are not API callers.
        if not (_INTERNAL_WRITE.get() or self.env.su):
            raise AccessError(_(
                "Milestone history is written by the tracker only."))
        return super().create(vals_list)

    @api.model
    def log(self, milestone, old_stage, old_deadline, counts, source="sync",
            note=False):
        """Create a row for a change. Returns the record, or an empty recordset
        when nothing actually changed, so callers can skip chatter too."""
        stage_changed = (old_stage.id or False) != (milestone.stage_id.id or False)
        new_deadline = milestone._c2p_deadline_date()
        date_changed = (old_deadline or False) != (new_deadline or False)
        if not stage_changed and not date_changed:
            return self.browse()
        token = _INTERNAL_WRITE.set(True)
        try:
            return self.create(self._log_values(
                milestone, old_stage, old_deadline, new_deadline, counts,
                source, note))
        finally:
            _INTERNAL_WRITE.reset(token)

    def _log_values(self, milestone, old_stage, old_deadline, new_deadline,
                    counts, source, note):
        return {
            "milestone_id": milestone.id,
            "source": source,
            "old_stage_id": old_stage.id or False,
            "new_stage_id": milestone.stage_id.id or False,
            "old_deadline": old_deadline or False,
            "new_deadline": new_deadline or False,
            "done_task_count": counts.get("done", 0),
            "open_task_count": counts.get("open", 0),
            "waiting_task_count": counts.get("waiting", 0),
            "note": note,
        }
