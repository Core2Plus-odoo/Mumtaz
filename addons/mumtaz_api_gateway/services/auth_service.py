import hashlib

from odoo import fields
from odoo.exceptions import AccessDenied


def resolve_api_key(env, raw_key):
    if not raw_key:
        raise AccessDenied("Missing API key.")
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    record = env["mumtaz.api.key"].search([("key_hash", "=", key_hash), ("active", "=", True)], limit=1)
    if not record:
        raise AccessDenied("Invalid API key.")
    record.assert_not_expired()
    record.sudo().write({"last_used_at": fields.Datetime.now()})
    return record
