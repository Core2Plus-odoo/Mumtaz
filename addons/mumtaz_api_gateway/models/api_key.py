import hashlib
import hmac
import secrets

from odoo import api, fields, models
from odoo.exceptions import ValidationError


def _get_pepper(env) -> bytes:
    """Return the server-side pepper from system parameters.
    Falls back to a deterministic empty-pepper (less secure) if not set,
    so existing deployments don't break before the pepper is configured."""
    pepper = env["ir.config_parameter"].sudo().get_param("mumtaz.api_key.pepper", "")
    return pepper.encode("utf-8") if pepper else b""


def _hash_key(raw_key: str, pepper: bytes) -> str:
    """HMAC-SHA256 with server-side pepper. Constant-time safe."""
    return hmac.new(pepper, raw_key.encode("utf-8"), hashlib.sha256).hexdigest()


class MumtazApiKey(models.Model):
    _name = "mumtaz.api.key"
    _description = "Mumtaz API Key"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    tenant_id = fields.Many2one("mumtaz.tenant", required=True, ondelete="cascade", index=True)
    key_prefix = fields.Char(readonly=True, index=True)
    key_hash = fields.Char(readonly=True)
    rate_limit_per_minute = fields.Integer(default=120, tracking=True)
    expires_at = fields.Datetime(tracking=True)
    last_used_at = fields.Datetime(readonly=True)

    _sql_constraints = [
        ("mumtaz_api_key_prefix_unique", "unique(key_prefix)", "API key prefix must be unique."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        pepper = _get_pepper(self.env)
        for vals in vals_list:
            raw = secrets.token_urlsafe(32)
            vals["key_prefix"] = raw[:10]
            vals["key_hash"] = _hash_key(raw, pepper)
        return super().create(vals_list)

    def rotate_key(self):
        self.ensure_one()
        pepper = _get_pepper(self.env)
        raw = secrets.token_urlsafe(32)
        self.write({
            "key_prefix": raw[:10],
            "key_hash": _hash_key(raw, pepper),
            "last_used_at": False,
        })
        return raw

    def assert_not_expired(self):
        self.ensure_one()
        if self.expires_at and fields.Datetime.now() >= self.expires_at:
            raise ValidationError("API key has expired.")
