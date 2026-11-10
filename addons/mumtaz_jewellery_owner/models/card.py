from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

KINDS = [('rate', 'Gold rate'), ('exposure', 'Metal and stock value'), ('vip', 'VIP clients'),
         ('memo', 'Pieces on approval'), ('exchange', 'Old-gold exchanges'), ('slow', 'Slow stock')]


class OwnerCard(models.Model):
    _name = 'jewellery.owner.card'
    _description = 'Owner decision card'
    _order = 'priority desc, id'

    kind = fields.Selection(KINDS, required=True, index=True)
    title = fields.Char(required=True)
    detail = fields.Text()
    recommendation = fields.Char()
    impact = fields.Char()
    priority = fields.Integer(default=5)
    res_model = fields.Char()
    res_id = fields.Integer()
    restricted = fields.Boolean(help='Concerns a Private or Royal client; VIP managers only.')
    state = fields.Selection([('open', 'Open'), ('dismissed', 'Dismissed'), ('resolved', 'Resolved')],
                             default='open', index=True)

    def action_open(self):
        self.ensure_one()
        if not (self.res_model and self.res_id):
            return False
        return {'type': 'ir.actions.act_window', 'res_model': self.res_model, 'res_id': self.res_id,
                'view_mode': 'form', 'target': 'current'}

    def action_dismiss(self):
        self.write({'state': 'dismissed'})

    # ---- generation -------------------------------------------------
    @api.model
    def _desired(self):
        """Return list of dicts for every card that should exist now."""
        env = self.env
        out = []
        cur = env.company.currency_id
        fmt = lambda v: '%s %s' % (cur.name, format(v, ',.0f'))
        today = fields.Date.context_today(self)
        Rate = env['jewellery.gold.rate'].sudo()

        for r in Rate.search([('state', '=', 'draft'), ('company_id', '=', env.company.id)]):
            out.append(dict(kind='rate', res_model=r._name, res_id=r.id, priority=10,
                            title=_('Approve gold rate %.2f per gram (24K)') % r.rate_per_gram,
                            detail=_('Prices stay on the previous approved rate until a different person approves this one.'),
                            recommendation=_('Review and approve or reject'), impact=''))

        approved = Rate.search([('state', '=', 'approved'), ('company_id', '=', env.company.id)],
                               order='effective_at desc, id desc', limit=2)
        quants = env['stock.quant'].sudo().search([
            ('location_id.usage', '=', 'internal'), ('quantity', '>', 0), ('lot_id', '!=', False),
            ('lot_id.product_id.product_tmpl_id.is_jewellery', '=', True)])
        lots = quants.mapped('lot_id')
        fine = sum((l.net_weight_g or 0.0) * float(l.karat or 0) / 24.0 for l in lots)
        if approved:
            now = approved[0].rate_per_gram
            detail = _('%(n)s pieces in stock hold %(g).1f g of fine gold, worth %(v)s at the approved rate.',
                       n=len(lots), g=fine, v=fmt(fine * now))
            impact = ''
            if len(approved) == 2 and approved[1].rate_per_gram:
                prev = approved[1].rate_per_gram
                delta = fine * (now - prev)
                impact = _('%(s)s%(v)s vs previous rate (%(p).1f%%)', s='+' if delta >= 0 else '-',
                           v=fmt(abs(delta)), p=(now - prev) / prev * 100)
            out.append(dict(kind='exposure', res_model='', res_id=0, priority=4,
                            title=_('Stock value today'), detail=detail,
                            recommendation=_('No action unless the move is outside your limit'), impact=impact))

        for occ in env['jewellery.occasion'].sudo().search([]):
            nxt = occ._next_date(today)
            if today <= nxt <= today + timedelta(days=occ.lead_days):
                p = occ.partner_id
                out.append(dict(kind='vip', res_model='res.partner', res_id=p.id, priority=8,
                                restricted=p.jewellery_restricted,
                                title=_('%(k)s for %(n)s on %(d)s', k=dict(occ._fields['kind'].selection)[occ.kind],
                                        n=p.name, d=nxt),
                                detail=_('Relationship manager: %s. A draft is waiting; nothing is sent automatically.')
                                % (p.relationship_manager_id.name or _('none')),
                                recommendation=_('Check the gift plan with the relationship manager'),
                                impact=''))
        for m in env['jewellery.approval.memo'].sudo().search([('state', '=', 'out'),
                                                              ('return_by', '<=', today + timedelta(days=2))]):
            late = m.return_by < today
            out.append(dict(kind='memo', res_model=m._name, res_id=m.id, priority=9 if late else 7,
                            restricted=m.partner_id.jewellery_restricted,
                            title=_('%(m)s %(w)s', m=m.name, w=_('overdue') if late else _('due back soon')),
                            detail=_('%(n)s pieces with %(c)s, return by %(d)s.', n=len(m.lot_ids),
                                     c=m.partner_id.name, d=m.return_by),
                            recommendation=_('Contact the client personally'),
                            impact=_('Insured value %s') % fmt(m.insured_value)))
        for og in env['jewellery.old.gold'].sudo().search([('state', '=', 'to_approve')]):
            out.append(dict(kind='exchange', res_model=og._name, res_id=og.id, priority=10,
                            title=_('Approve old-gold exchange %s') % og.name,
                            detail=_('%(g).2f g gross at %(k)sK, valued at the rate saved when it was taken in.',
                                     g=og.gross_weight_g, k=og.karat),
                            recommendation=_('A different person from the one who took it in must approve'),
                            impact=fmt(og.value)))
        days = int(env['ir.config_parameter'].sudo().get_param('mumtaz_jewellery.slow_days', 90))
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = lots.filtered(lambda l: l.create_date and l.create_date < cutoff)
        if old and approved:
            val = sum((l.net_weight_g or 0.0) * float(l.karat or 0) / 24.0 for l in old) * approved[0].rate_per_gram
            out.append(dict(kind='slow', res_model='', res_id=0, priority=3,
                            title=_('%(n)s pieces unsold for over %(d)s days', n=len(old), d=days),
                            detail=_(', ').join(old.mapped('name')[:8]),
                            recommendation=_('Move to another boutique, mark down, remake or melt'),
                            impact=_('Metal value %s') % fmt(val)))
        return out

    @api.model
    def refresh(self):
        cards = self.sudo().search([])
        key = lambda c: (c['kind'], c['res_model'] or '', c['res_id'] or 0)
        existing = {key(c): c for c in cards}
        desired = {key(d): d for d in self._desired()}
        for k, d in desired.items():
            c = existing.get(k)
            if c:
                if c.state != 'dismissed':
                    c.write({**d, 'state': 'open'})
            else:
                self.sudo().create(d)
        for k, c in existing.items():
            if k not in desired and c.state == 'open':
                c.state = 'resolved'
        return True

    def action_refresh(self):
        self.refresh()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
