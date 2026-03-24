from odoo import fields, models


class MumtazCoreLog(models.Model):
    _name = "mumtaz.core.log"
    _description = "Mumtaz Core Action Log"
    _order = "create_date desc"
    _check_company_auto = True

    company_id = fields.Many2one("res.company", required=True, index=True)
    user_id = fields.Many2one("res.users", required=True, index=True, check_company=True)
    module_name = fields.Char(required=True)
    action = fields.Char(required=True)
    request_payload = fields.Text()
    response_payload = fields.Text()
    level = fields.Selection(
        [("info", "Info"), ("warning", "Warning"), ("error", "Error")],
        default="info",
        required=True,
    )

    def log_action(
        self,
        module_name,
        action,
        company,
        user,
        request_payload=None,
        response_payload=None,
        level="info",
    ):
        return self.create(
            {
                "company_id": company.id,
                "user_id": user.id,
                "module_name": module_name,
                "action": action,
                "request_payload": request_payload,
                "response_payload": response_payload,
                "level": level,
            }
        )
