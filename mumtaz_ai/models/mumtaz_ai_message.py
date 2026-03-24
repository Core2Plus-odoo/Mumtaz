from odoo import api, fields, models


class MumtazAIMessage(models.Model):
    _name = "mumtaz.ai.message"
    _description = "Mumtaz AI Message"
    _order = "create_date desc"
    _check_company_auto = True

    session_id = fields.Many2one(
        "mumtaz.ai.session", required=True, ondelete="cascade", index=True, check_company=True
    )
    user_id = fields.Many2one("res.users", required=True, index=True, check_company=True)
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("session_id") and not vals.get("company_id"):
                session = self.env["mumtaz.ai.session"].browse(vals["session_id"])
                vals["company_id"] = session.company_id.id
            vals.setdefault("company_id", self.env.company.id)
            vals.setdefault("user_id", self.env.user.id)
        return super().create(vals_list)
