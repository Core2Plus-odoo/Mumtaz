from odoo import fields
from odoo.exceptions import AccessDenied


def check_rate_limit(api_key):
    window_start = fields.Datetime.subtract(fields.Datetime.now(), minutes=1)
    count = api_key.env["mumtaz.api.usage.log"].sudo().search_count([
        ("api_key_id", "=", api_key.id),
        ("request_time", ">=", window_start),
    ])
    if count >= api_key.rate_limit_per_minute:
        raise AccessDenied("Rate limit exceeded.")
    return True
