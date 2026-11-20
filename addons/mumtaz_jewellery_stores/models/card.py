"""Stores on the decision cards: transfers overdue or lost, an open
variance, a store over its fine-gram limit."""
from odoo import _, api, fields, models


class OwnerCard(models.Model):
    _inherit = 'jewellery.owner.card'

    kind = fields.Selection(selection_add=[('store', 'Stores and transfers')], ondelete={'store': 'cascade'})

    @api.model
    def _desired(self):
        out = super()._desired()
        env = self.env
        for t in env['jewellery.transfer'].sudo().search([('state', 'in', ('in_transit', 'lost'))]):
            if t.state == 'lost' or t.overdue:
                out.append(dict(kind='store', res_model=t._name, res_id=t.id, priority=10 if t.state == 'lost' else 8,
                                title=_('%(n)s %(w)s: %(a)s → %(b)s', n=t.name, w=_('reported lost') if t.state == 'lost' else _('overdue in transit'),
                                        a=t.from_warehouse_id.name, b=t.to_warehouse_id.name),
                                detail=_('%(p)s pieces, %(g).3f g fine, dispatched %(d)s by %(u)s.', p=t.piece_count, g=t.fine_g,
                                         d=t.dispatched_at or '', u=t.dispatched_by_id.name or ''),
                                recommendation=_('Call the receiving store; receive or report lost'), impact=''))
        for r in env['jewellery.gold.reconciliation'].sudo().search([('state', '=', 'open'), ('variance_fine_g', '!=', 0)]):
            out.append(dict(kind='store', res_model=r._name, res_id=r.id, priority=9,
                            title=_('%(s)s: %(g).3f g fine %(w)s on %(d)s', s=r.warehouse_id.name, g=abs(r.variance_fine_g),
                                    w=_('missing') if r.variance_fine_g < 0 else _('over'), d=r.date),
                            detail=_('%(m)s of %(e)s pieces not found.', m=r.missing_count, e=r.expected_count),
                            recommendation=_('Recount, then a manager closes with a note'), impact=''))
        for w in env['stock.warehouse'].sudo().search([('jewellery_store_limit_fine_g', '>', 0)]):
            s = w.jewellery_summary()
            if s['over_limit']:
                out.append(dict(kind='store', res_model='stock.warehouse', res_id=w.id, priority=6,
                                title=_('%s holds more fine gold than its limit') % w.name,
                                detail=_('%(g).1f g against a limit of %(l).1f g.', g=s['fine_g'], l=w.jewellery_store_limit_fine_g),
                                recommendation=_('Transfer pieces to another store or raise the limit'), impact=''))
        return out
