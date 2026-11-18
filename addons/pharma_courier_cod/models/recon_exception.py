from odoo import fields, models

CATEGORIES = [
    ("collection", "Customer paid less than declared"),
    ("remittance", "Courier accounted for less than collected"),
    ("overdue", "Remittance overdue"),
    ("deduction", "Deduction above the authorized amount"),
    ("returned_cod", "COD collected on a returned parcel"),
    ("intake", "No matching internal order"),
]


class PharmaReconException(models.Model):
    """The hub's exception queue, taught where a courier exception came from.

    `dedupe_key` makes raising idempotent: re-running a check never creates a second exception for the same
    finding, and an exception that was resolved stays resolved."""

    _inherit = "pharma.recon.exception"

    dedupe_key = fields.Char(index=True, copy=False)
    category = fields.Selection(CATEGORIES, index=True)
    source_model = fields.Char(readonly=True)
    source_id = fields.Integer(readonly=True)

    def action_open_source(self):
        self.ensure_one()
        if not (self.source_model and self.source_id):
            return False
        return {"type": "ir.actions.act_window", "res_model": self.source_model, "res_id": self.source_id,
                "view_mode": "form"}
