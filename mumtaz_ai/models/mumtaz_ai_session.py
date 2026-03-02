from odoo import api, fields, models
from odoo.exceptions import UserError


class MumtazAISession(models.Model):
    _name = "mumtaz.ai.session"
    _description = "Mumtaz AI Session"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _check_company_auto = True

    name = fields.Char(required=True, default="New Session", tracking=True)
    user_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user, index=True, check_company=True
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True, check_company=True
    )
    company_currency_id = fields.Many2one(related="company_id.currency_id", store=False, readonly=True)
    execution_status = fields.Selection(
        [("draft", "Draft"), ("running", "Running"), ("done", "Done"), ("failed", "Failed")],
        default="draft",
        tracking=True,
    )
    message_ids = fields.One2many("mumtaz.ai.message", "session_id", string="Messages")
    message_count = fields.Integer(compute="_compute_message_count")
    prompt = fields.Text(string="Prompt", help="Current prompt input for chat-like interaction.")
    response = fields.Text(string="Last Response", readonly=True)
    token_usage = fields.Integer(readonly=True)
    model_used = fields.Char(readonly=True)
    last_error = fields.Text(readonly=True)

    @api.depends("message_ids")
    def _compute_message_count(self):
        for record in self:
            record.message_count = len(record.message_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            vals.setdefault("user_id", self.env.user.id)
        return super().create(vals_list)

    def action_process_prompt(self):
        self.ensure_one()
        if not self.prompt:
            raise UserError("Please enter a prompt before sending.")
        self.execution_status = "running"
        try:
            result = self.env["mumtaz.ai.service"].process_user_prompt(self, self.prompt)
            self.response = result.get("response")
            self.token_usage = result.get("token_usage", 0)
            self.model_used = result.get("model_used")
            self.execution_status = "done"
            self.last_error = False
            self.prompt = False
        except Exception as exc:
            self.execution_status = "failed"
            self.last_error = str(exc)
            raise

    def action_view_history(self):
        self.ensure_one()
        return {
            "name": "Session History",
            "type": "ir.actions.act_window",
            "res_model": "mumtaz.ai.message",
            "view_mode": "list,form",
            "domain": [("session_id", "=", self.id)],
            "context": {"default_session_id": self.id, "default_company_id": self.company_id.id},
        }
