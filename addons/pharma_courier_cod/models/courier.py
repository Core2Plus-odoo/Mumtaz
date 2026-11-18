from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PharmaCourier(models.Model):
    """A courier the business ships COD parcels with. Generic: the name is data, never code."""

    _name = "pharma.courier"
    _description = "Courier"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, help="Short stable code used in references and event ids, for example COURIER-A.")
    active = fields.Boolean(default=True)
    remittance_cycle_days = fields.Integer(
        default=14, help="Days from delivery within which the courier must remit the COD it collected. "
                         "Beyond this a shipment is overdue.")
    variance_tolerance = fields.Float(
        digits=(16, 2), default=0.0,
        help="Differences up to this amount are not raised as exceptions.")
    partner_id = fields.Many2one(
        "res.partner", string="Vendor", help="The courier as a supplier. Used when its invoices are booked.")
    shipment_count = fields.Integer(compute="_compute_shipment_count")
    is_demo = fields.Boolean(string="DEMO")

    _code_uniq = models.Constraint("UNIQUE(code)", "A courier with this code already exists.")

    @api.constrains("remittance_cycle_days", "variance_tolerance")
    def _check_values(self):
        for c in self:
            if c.remittance_cycle_days < 1:
                raise ValidationError("The remittance cycle must be at least one day.")
            if c.variance_tolerance < 0:
                raise ValidationError("The variance tolerance cannot be negative.")

    def _compute_shipment_count(self):
        data = {c.id: n for c, n in self.env["pharma.courier.shipment"]._read_group(
            [("courier_id", "in", self.ids)], ["courier_id"], ["__count"])}
        for c in self:
            c.shipment_count = data.get(c.id, 0)
