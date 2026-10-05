from odoo import api, fields, models


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

    _milestone_date_idx = models.Index("(milestone_id, change_date)")

    @api.model
    def log(self, milestone, old_stage, old_deadline, counts, source="sync",
            note=False):
        """Create a row for a change. Returns the record, or an empty recordset
        when nothing actually changed, so callers can skip chatter too."""
        stage_changed = (old_stage.id or False) != (milestone.stage_id.id or False)
        date_changed = (old_deadline or False) != (milestone.date_deadline or False)
        if not stage_changed and not date_changed:
            return self.browse()
        return self.create({
            "milestone_id": milestone.id,
            "source": source,
            "old_stage_id": old_stage.id or False,
            "new_stage_id": milestone.stage_id.id or False,
            "old_deadline": old_deadline or False,
            "new_deadline": milestone.date_deadline or False,
            "done_task_count": counts.get("done", 0),
            "open_task_count": counts.get("open", 0),
            "waiting_task_count": counts.get("waiting", 0),
            "note": note,
        })
