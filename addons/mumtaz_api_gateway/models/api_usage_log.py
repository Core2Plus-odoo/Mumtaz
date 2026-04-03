from odoo import fields, models


class MumtazApiUsageLog(models.Model):
    _name = "mumtaz.api.usage.log"
    _description = "Mumtaz API Usage Log"
    _order = "request_time desc"

    request_time = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    api_key_id = fields.Many2one("mumtaz.api.key", ondelete="set null", index=True)
    tenant_id = fields.Many2one("mumtaz.tenant", ondelete="set null", index=True)
    endpoint = fields.Char(required=True)
    method = fields.Char(required=True)
    status_code = fields.Integer(required=True)
    duration_ms = fields.Integer()
    request_id = fields.Char(index=True)
    ip_address = fields.Char()
    user_agent = fields.Char()
    payload_size = fields.Integer()
    response_size = fields.Integer()
    error_message = fields.Char()
