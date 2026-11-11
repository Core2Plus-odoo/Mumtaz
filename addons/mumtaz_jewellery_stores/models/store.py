"""A store is a warehouse. What it holds is read from quants, in pieces,
fine grams and value at the approved rate; the owner may set a fine-gram
limit per store. Staff may be tied to one store."""
from odoo import api, fields, models
from odoo.exceptions import UserError


def fine_grams(lot):
    return (lot.net_weight_g or 0.0) * float(lot.karat or 0) / 24.0


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    jewellery_store_limit_fine_g = fields.Float(string='Fine-gram limit', digits=(16, 3),
                                                help='The most fine gold this store should hold, in grams. 0 for no limit.')

    def jewellery_lots(self):
        """Jewellery pieces on this store's shelves (any internal location
        under the warehouse), by quant."""
        self.ensure_one()
        quants = self.env['stock.quant'].sudo().search([
            ('location_id', 'child_of', self.view_location_id.id), ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0), ('lot_id', '!=', False),
            ('lot_id.product_id.product_tmpl_id.is_jewellery', '=', True)])
        return quants.mapped('lot_id')

    def jewellery_summary(self):
        self.ensure_one()
        lots = self.jewellery_lots()
        fine = sum(fine_grams(l) for l in lots)
        rate = None
        try:
            rate = self.env['jewellery.gold.rate'].get_current(self.company_id)
        except UserError:
            rate = None
        Transfer = self.env['jewellery.transfer'].sudo()
        out_t = Transfer.search([('from_warehouse_id', '=', self.id), ('state', '=', 'in_transit')])
        in_t = Transfer.search([('to_warehouse_id', '=', self.id), ('state', '=', 'in_transit')])
        today = fields.Date.context_today(self)
        recon = self.env['jewellery.gold.reconciliation'].sudo().search(
            [('warehouse_id', '=', self.id), ('date', '=', today)], order='id desc', limit=1)
        return {
            'id': self.id, 'name': self.name, 'code': self.code,
            'pieces': len(lots), 'fine_g': round(fine, 3),
            'value': round(fine * rate.rate_per_gram, 2) if rate else None,
            'currency': self.company_id.currency_id.name,
            'limit_fine_g': self.jewellery_store_limit_fine_g or None,
            'over_limit': bool(self.jewellery_store_limit_fine_g) and fine > self.jewellery_store_limit_fine_g,
            'in_transit_out': {'transfers': len(out_t), 'pieces': sum(len(t.lot_ids) for t in out_t),
                               'fine_g': round(sum(t.fine_g for t in out_t), 3)},
            'in_transit_in': {'transfers': len(in_t), 'pieces': sum(len(t.lot_ids) for t in in_t),
                              'fine_g': round(sum(t.fine_g for t in in_t), 3)},
            'today': {'id': recon.id, 'name': recon.name, 'state': recon.state,
                      'variance_fine_g': recon.variance_fine_g, 'missing_count': recon.missing_count} if recon else None,
        }


class ResUsers(models.Model):
    _inherit = 'res.users'

    jewellery_store_id = fields.Many2one('stock.warehouse', string='Jewellery store',
                                         help='The store this person works in. Empty: every store.')

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['jewellery_store_id']


class StockLot(models.Model):
    _inherit = 'stock.lot'

    def jewellery_current_location(self):
        self.ensure_one()
        quant = self.env['stock.quant'].sudo().search([
            ('lot_id', '=', self.id), ('quantity', '>', 0), ('location_id.usage', '=', 'internal')], limit=1)
        return quant.location_id if quant else None

    def jewellery_store(self):
        loc = self.jewellery_current_location()
        return loc.warehouse_id if loc else self.env['stock.warehouse']

    @api.model
    def _jewellery_move(self, lot, source, destination, reference):
        """Move one serial from one internal location to another, done at
        once, as the approval memo does. Ownership and valuation unchanged."""
        move = self.env['stock.move'].sudo().create({
            'description_picking': '%s: %s' % (reference, lot.name),
            'product_id': lot.product_id.id, 'product_uom_qty': 1.0, 'product_uom': lot.product_id.uom_id.id,
            'location_id': source.id, 'location_dest_id': destination.id, 'company_id': lot.company_id.id or self.env.company.id,
        })
        move._action_confirm()
        move._action_assign()
        move.move_line_ids.write({'lot_id': lot.id, 'quantity': 1.0})
        if not move.move_line_ids:
            self.env['stock.move.line'].sudo().create({
                'move_id': move.id, 'product_id': lot.product_id.id, 'product_uom_id': lot.product_id.uom_id.id,
                'lot_id': lot.id, 'quantity': 1.0, 'location_id': source.id, 'location_dest_id': destination.id,
            })
        move.picked = True
        move._action_done()
        return move
