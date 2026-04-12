from odoo import api, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        sanitized = [self._sanitize_nul_strings(vals) for vals in vals_list]
        return super().create(sanitized)

    def write(self, vals):
        return super().write(self._sanitize_nul_strings(vals))

    @staticmethod
    def _sanitize_nul_strings(vals):
        clean = {}
        for key, value in (vals or {}).items():
            if isinstance(value, str):
                clean[key] = value.replace("\x00", "")
            else:
                clean[key] = value
        return clean
