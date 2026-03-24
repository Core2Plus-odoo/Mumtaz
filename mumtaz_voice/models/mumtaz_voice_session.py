from odoo import api, fields, models
from odoo.exceptions import UserError


class MumtazVoiceSession(models.Model):
    _name = "mumtaz.voice.session"
    _description = "Mumtaz CFO Voice Assistant Session"
    _inherit = ["mail.thread"]
    _order = "create_date desc"
    _check_company_auto = True

    name = fields.Char(required=True, default="CFO Voice Session", tracking=True)
    user_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user, index=True, check_company=True
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )

    transcript = fields.Text(string="Voice Input / Question")
    response = fields.Text(string="CFO Response", readonly=True)
    intent = fields.Char(string="Detected Intent", readonly=True)
    financial_context = fields.Text(string="Financial Context Used", readonly=True)

    status = fields.Selection(
        [("idle", "Ready"), ("processing", "Processing"), ("done", "Done"), ("error", "Error")],
        default="idle",
        tracking=True,
    )
    last_error = fields.Text(readonly=True)
    model_used = fields.Char(readonly=True)
    token_usage = fields.Integer(readonly=True, default=0)

    message_ids = fields.One2many("mumtaz.voice.message", "session_id", string="Conversation History")
    message_count = fields.Integer(compute="_compute_message_count")

    @api.depends("message_ids")
    def _compute_message_count(self):
        for rec in self:
            rec.message_count = len(rec.message_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            vals.setdefault("user_id", self.env.user.id)
        return super().create(vals_list)

    def action_ask(self):
        self.ensure_one()
        if not self.transcript or not self.transcript.strip():
            raise UserError("Please enter a question before asking.")
        self.status = "processing"
        try:
            result = self.env["mumtaz.voice.service"].process_cfo_query(self, self.transcript)
            self.write({
                "response": result.get("response"),
                "intent": result.get("intent"),
                "financial_context": result.get("financial_context"),
                "model_used": result.get("model_used"),
                "token_usage": result.get("token_usage", 0),
                "status": "done",
                "last_error": False,
            })
        except Exception as exc:
            self.write({"status": "error", "last_error": str(exc)})
            raise
        return True

    def action_clear_session(self):
        self.ensure_one()
        self.write({"transcript": False, "response": False, "intent": False,
                    "financial_context": False, "status": "idle", "last_error": False, "token_usage": 0})

    def action_view_history(self):
        self.ensure_one()
        return {"name": "Conversation History", "type": "ir.actions.act_window",
                "res_model": "mumtaz.voice.message", "view_mode": "list,form",
                "domain": [("session_id", "=", self.id)],
                "context": {"default_session_id": self.id}}
