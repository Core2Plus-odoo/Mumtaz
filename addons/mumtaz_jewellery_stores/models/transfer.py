"""A transfer between stores is two-sided: the sender dispatches, the
receiver receives, and in between the pieces sit in the company's transit
location, owned and valued but on no store's shelf."""
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .store import fine_grams

STATES = [('draft', 'Draft'), ('in_transit', 'In transit'), ('received', 'Received'), ('lost', 'Reported lost')]


class Transfer(models.Model):
    _name = 'jewellery.transfer'
    _description = 'Jewellery transfer between stores'
    _order = 'id desc'

    name = fields.Char(default=lambda s: _('New'), copy=False, readonly=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    from_warehouse_id = fields.Many2one('stock.warehouse', string='From store', required=True)
    to_warehouse_id = fields.Many2one('stock.warehouse', string='To store', required=True)
    lot_ids = fields.Many2many('stock.lot', string='Pieces', domain="[('product_id.is_jewellery', '=', True)]")
    piece_count = fields.Integer(compute='_compute_totals')
    fine_g = fields.Float(compute='_compute_totals', digits=(16, 3), string='Fine grams')
    state = fields.Selection(STATES, default='draft', required=True, index=True, copy=False)
    note = fields.Char()
    dispatched_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    dispatched_at = fields.Datetime(readonly=True, copy=False)
    received_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    received_at = fields.Datetime(readonly=True, copy=False)
    lost_note = fields.Char(readonly=True, copy=False)
    overdue = fields.Boolean(compute='_compute_overdue')

    @api.depends('lot_ids')
    def _compute_totals(self):
        for t in self:
            t.piece_count = len(t.lot_ids)
            t.fine_g = sum(fine_grams(l) for l in t.lot_ids)

    def _days(self):
        try:
            return max(1, int(self.env['ir.config_parameter'].sudo().get_param('mumtaz_jewellery.transfer_days', 2)))
        except (TypeError, ValueError):
            return 2

    @api.depends('state', 'dispatched_at')
    def _compute_overdue(self):
        now = fields.Datetime.now()
        for t in self:
            t.overdue = t.state == 'in_transit' and bool(t.dispatched_at) and (now - t.dispatched_at) > timedelta(days=t._days())

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('jewellery.transfer') or _('New')
        recs = super().create(vals_list)
        for t in recs:
            if t.from_warehouse_id == t.to_warehouse_id:
                raise UserError(_('A transfer goes from one store to another.'))
            if not t.lot_ids:
                raise UserError(_('A transfer carries at least one piece.'))
        return recs

    def _transit_location(self):
        return self.env.ref('mumtaz_jewellery_stores.location_in_transit')

    def _may_act_for(self, warehouse):
        u = self.env.user
        if u.has_group('mumtaz_jewellery.group_jewellery_manager'):
            return True
        return not u.jewellery_store_id or u.jewellery_store_id == warehouse

    def action_dispatch(self):
        """The sending store sends: every piece must be on its shelf and on
        no live order or approval; then it moves to transit."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('%s is already %s.') % (self.name, self.state))
        if not self._may_act_for(self.from_warehouse_id):
            raise UserError(_('Only %s staff or a manager dispatch from that store.') % self.from_warehouse_id.name)
        Tray = self.env['jewellery.tray']
        for lot in self.lot_ids:
            loc = lot.jewellery_current_location()
            if not loc or loc.warehouse_id != self.from_warehouse_id:
                raise UserError(_('%s is not on the shelf at %s.') % (lot.name, self.from_warehouse_id.name))
            if not Tray._lot_available(lot):
                raise UserError(_('%s is on a live order or out on approval; it cannot travel.') % lot.name)
            self.env['stock.lot']._jewellery_move(lot, loc, self._transit_location(), self.name)
        self.write({'state': 'in_transit', 'dispatched_by_id': self.env.user.id, 'dispatched_at': fields.Datetime.now()})
        return True

    def action_receive(self):
        """The receiving store receives: the pieces land on its shelf."""
        self.ensure_one()
        if self.state != 'in_transit':
            raise UserError(_('%s is not in transit.') % self.name)
        if not self._may_act_for(self.to_warehouse_id):
            raise UserError(_('Only %s staff or a manager receive at that store.') % self.to_warehouse_id.name)
        transit = self._transit_location()
        for lot in self.lot_ids:
            loc = lot.jewellery_current_location()
            if loc != transit:
                raise UserError(_('%s is not in transit.') % lot.name)
            self.env['stock.lot']._jewellery_move(lot, transit, self.to_warehouse_id.lot_stock_id, self.name)
        self.write({'state': 'received', 'received_by_id': self.env.user.id, 'received_at': fields.Datetime.now()})
        return True

    def action_report_lost(self, note=None):
        """An exception, not a write-off: the pieces stay in transit, owned
        and valued, until a person finds them or finance decides."""
        self.ensure_one()
        if self.state != 'in_transit':
            raise UserError(_('%s is not in transit.') % self.name)
        if not self.env.user.has_group('mumtaz_jewellery.group_jewellery_manager'):
            raise UserError(_('Only a manager reports a transfer lost.'))
        self.write({'state': 'lost', 'lost_note': (note or '')[:200] or False})
        return True

    def transfer_dict(self):
        self.ensure_one()
        return {
            'id': self.id, 'name': self.name, 'state': self.state, 'overdue': self.overdue, 'note': self.note or None,
            'from': {'id': self.from_warehouse_id.id, 'name': self.from_warehouse_id.name},
            'to': {'id': self.to_warehouse_id.id, 'name': self.to_warehouse_id.name},
            'pieces': [{'id': l.id, 'serial': l.name, 'design': l.product_id.name, 'karat': l.karat, 'net_weight_g': l.net_weight_g,
                        'fine_g': round(fine_grams(l), 3)} for l in self.lot_ids],
            'piece_count': self.piece_count, 'fine_g': round(self.fine_g, 3),
            'dispatched_by': {'id': self.dispatched_by_id.id, 'name': self.dispatched_by_id.name} if self.dispatched_by_id else None,
            'dispatched_at': self.dispatched_at or None,
            'received_by': {'id': self.received_by_id.id, 'name': self.received_by_id.name} if self.received_by_id else None,
            'received_at': self.received_at or None, 'lost_note': self.lost_note or None,
        }
