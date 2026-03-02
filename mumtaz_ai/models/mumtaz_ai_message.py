from odoo import fields, models


class MumtazAIMessage(models.Model):
    _name = "mumtaz.ai.message"
    _description = "Mumtaz AI Message"
    _order = "create_date desc"

    session_id = fields.Many2one("mumtaz.ai.session", required=True, ondelete="cascade", index=True)
    user_id = fields.Many2one("res.users", required=True, index=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    intent = fields.Selection(
        [
            ("financial_query", "Financial Query"),
            ("crm_query", "CRM Query"),
            ("sales_query", "Sales Query"),
            ("general_query", "General Query"),
        ],
        required=True,
    )
    prompt = fields.Text(required=True)
    response = fields.Text()
    token_usage = fields.Integer(default=0)
    model_used = fields.Char()
    execution_status = fields.Selection(
        [("running", "Running"), ("done", "Done"), ("failed", "Failed")],
        default="done",
        required=True,
    )
