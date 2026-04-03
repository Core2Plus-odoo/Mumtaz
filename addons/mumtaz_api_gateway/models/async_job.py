from odoo import fields, models


class MumtazAsyncJob(models.Model):
    _name = "mumtaz.async.job"
    _description = "Mumtaz Async API Job"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(required=True)
    tenant_id = fields.Many2one("mumtaz.tenant", required=True, ondelete="cascade", index=True)
    state = fields.Selection(
        [("queued", "Queued"), ("running", "Running"), ("done", "Done"), ("failed", "Failed")],
        default="queued",
        required=True,
        tracking=True,
    )
    job_type = fields.Char(required=True)
    payload_json = fields.Text()
    result_json = fields.Text()
    error_message = fields.Text()
    requested_by = fields.Many2one("res.users", default=lambda self: self.env.user, ondelete="set null")
    started_at = fields.Datetime()
    finished_at = fields.Datetime()
