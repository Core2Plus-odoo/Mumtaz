from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    x_mumtaz_code = fields.Char(
        string="Mumtaz Code",
        copy=False,
        index=True,
        help="Internal reference used by Mumtaz.",
    )

    _sql_constraints = [
        (
            "x_mumtaz_code_unique",
            "unique(x_mumtaz_code)",
            "Mumtaz Code must be unique.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            code = vals.get("x_mumtaz_code")
            if code:
                vals["x_mumtaz_code"] = code.strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        code = vals.get("x_mumtaz_code")
        if code:
            vals["x_mumtaz_code"] = code.strip().upper()
        return super().write(vals)
