import importlib.util
import os

from odoo import api, fields, models
from odoo.exceptions import UserError

_spec = importlib.util.spec_from_file_location(
    'mumtaz_nbo', os.path.join(os.path.dirname(__file__), '..', 'services', 'nbo.py'))
nbo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nbo)


class StockLot(models.Model):
    _inherit = 'stock.lot'

    occasion_tags = fields.Char(help='Comma separated: wedding, eid, birthday ...')


class OfferSuggestion(models.Model):
    _name = 'jewellery.offer.suggestion'
    _description = 'Next-best-offer suggestion'
    _order = 'score desc, id'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade')
    lot_id = fields.Many2one('stock.lot', required=True, ondelete='cascade')
    score = fields.Float()
    reasons = fields.Text()
    price = fields.Float(digits=(16, 2))
    margin_pct = fields.Float(string='Making + wastage share %')
    state = fields.Selection([('new', 'New'), ('accepted', 'Accepted'), ('dismissed', 'Dismissed')], default='new')

    def action_accept(self):
        self.write({'state': 'accepted'})

    def action_dismiss(self):
        self.write({'state': 'dismissed'})

    @api.model
    def generate_for(self, partner):
        in_stock = self.env['stock.quant'].sudo().search([
            ('location_id.usage', '=', 'internal'), ('quantity', '>', 0), ('lot_id', '!=', False),
            ('lot_id.product_id.product_tmpl_id.is_jewellery', '=', True)]).mapped('lot_id')
        pieces = []
        for lot in in_stock:
            try:
                b = lot.get_price_breakdown()
            except UserError:
                continue
            sub = float(b['subtotal']) or 1.0
            share = (float(b['making_charge']) + float(b['wastage_value'])) / sub * 100
            pieces.append({'id': lot.id, 'name': lot.name, 'karat': lot.karat, 'price': float(b['total']),
                           'margin_pct': share,
                           'occasions': [t.strip() for t in (lot.occasion_tags or '').split(',') if t.strip()]})
        today = fields.Date.context_today(self)
        upcoming = None
        for occ in partner.occasion_ids:
            nxt = occ._next_date(today)
            if nxt >= today and (nxt - today).days <= 60 and (not upcoming or nxt < upcoming[0]):
                upcoming = (nxt, occ.kind)
        prefs = {'karats': [k.strip() for k in (partner.preferred_karats or '').split(',') if k.strip()],
                 'budget': partner.typical_budget or None,
                 'occasion': upcoming[1] if upcoming else None}
        ranked = nbo.rank_pieces(prefs, pieces)
        partner.suggestion_ids.filtered(lambda s: s.state == 'new').unlink()
        self.create([{'partner_id': partner.id, 'lot_id': r['id'], 'score': r['score'],
                      'reasons': '\n'.join(r['reasons']), 'price': r['price'], 'margin_pct': r['margin_pct']}
                     for r in ranked])
        return ranked
