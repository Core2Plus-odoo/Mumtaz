import hmac

from odoo import fields
from odoo.exceptions import AccessDenied

from .api_key import _get_pepper, _hash_key  # noqa: WPS436


def resolve_api_key(env, raw_key):
    if not raw_key:
        raise AccessDenied("Missing API key.")

    pepper = _get_pepper(env)
    key_hash = _hash_key(raw_key, pepper)

    # Constant-time prefix lookup + hash comparison prevents timing attacks
    prefix = raw_key[:10]
    record = env["mumtaz.api.key"].search(
        [("key_prefix", "=", prefix), ("active", "=", True)], limit=1
    )
    if not record:
        raise AccessDenied("Invalid API key.")

    # Constant-time comparison to prevent timing-based key enumeration
    if not hmac.compare_digest(record.key_hash, key_hash):
        raise AccessDenied("Invalid API key.")

    record.assert_not_expired()
    record.sudo().write({"last_used_at": fields.Datetime.now()})
    return record
