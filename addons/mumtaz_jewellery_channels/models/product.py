"""Publication: a design is on the web shelf only when a person says so.
The public shelf (kiosk and web) honours the switch; staff screens do not."""
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    jewellery_published = fields.Boolean(string='On the web shelf', default=True,
                                         help='Shown on the public shelf (kiosk and web) when a piece of this design is on a shelf.')


class Tray(models.Model):
    _inherit = 'jewellery.tray'

    def _lot_public(self, lot):
        """On the public shelf: available, and its design published."""
        return self._lot_available(lot) and bool(lot.product_id.product_tmpl_id.jewellery_published)
