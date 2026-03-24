from odoo import api, fields, models


class MumtazVoiceMessage(models.Model):
    _name = "mumtaz.voice.message"
    _description = "Mumtaz Voice Conversation Message"
    _order = "create_date asc"
    _check_company_auto = True

    session_id = fields.Many2one(
        "mumtaz.voice.session", required=True, ondelete="cascade", index=True, check_company=True
    )
    company_id = fields.Many2one("res.company", required=True, index=True, check_company=True)
    user_id = fields.Many2one("res.users", required=True, index=True)
    role = fields.Selection([("user", "User"), ("assistant", "CFO Assistant")], required=True)
    content = fields.Text(required=True)
    intent = fields.Char()
    model_used = fields.Char()
    token_usage = fields.Integer(default=0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("session_id") and not vals.get("company_id"):
                session = self.env["mumtaz.voice.session"].browse(vals["session_id"])
                vals["company_id"] = session.company_id.id
            vals.setdefault("company_id", self.env.company.id)
            vals.setdefault("user_id", self.env.user.id)
        return super().create(vals_list)
