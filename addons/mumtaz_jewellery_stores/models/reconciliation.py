"""The daily gold reconciliation, per store, in fine grams. A run snapshots
what the store should hold; a person scans what is there; the variance is
stated in pieces and fine grams with the missing serials named; a manager
closes it with a note."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .store import fine_grams


class GoldReconciliation(models.Model):
    _name = 'jewellery.gold.reconciliation'
    _description = 'Daily gold reconciliation (fine grams)'
    _order = 'date desc, id desc'

    name = fields.Char(default=lambda s: _('New'), copy=False, readonly=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    warehouse_id = fields.Many2one('stock.warehouse', string='Store', required=True, index=True)
    date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    state = fields.Selection([('open', 'Open'), ('closed', 'Closed')], default='open', required=True, index=True)
    line_ids = fields.One2many('jewellery.gold.reconciliation.line', 'reconciliation_id')
    expected_count = fields.Integer(compute='_compute_totals', store=True)
    expected_fine_g = fields.Float(compute='_compute_totals', store=True, digits=(16, 3))
    counted_count = fields.Integer(compute='_compute_totals', store=True)
    counted_fine_g = fields.Float(compute='_compute_totals', store=True, digits=(16, 3))
    variance_fine_g = fields.Float(compute='_compute_totals', store=True, digits=(16, 3),
                                   help='Counted minus expected: negative means metal is missing.')
    missing_count = fields.Integer(compute='_compute_totals', store=True)
    extra_serials = fields.Char(help='Serials scanned that the store was not expected to hold.')
    note = fields.Char()
    opened_by_id = fields.Many2one('res.users', readonly=True, default=lambda s: s.env.user)
    closed_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    closed_at = fields.Datetime(readonly=True, copy=False)

    _sql_constraints = [('one_per_store_day', 'unique(warehouse_id, date)', 'One reconciliation per store per day.')]

    @api.depends('line_ids.found', 'line_ids.fine_g')
    def _compute_totals(self):
        for r in self:
            r.expected_count = len(r.line_ids)
            r.expected_fine_g = sum(r.line_ids.mapped('fine_g'))
            found = r.line_ids.filtered('found')
            r.counted_count = len(found)
            r.counted_fine_g = sum(found.mapped('fine_g'))
            r.variance_fine_g = r.counted_fine_g - r.expected_fine_g
            r.missing_count = r.expected_count - r.counted_count

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('jewellery.gold.reconciliation') or _('New')
        return super().create(vals_list)

    @api.model
    def open_for(self, warehouse, date=None):
        """Today's run for a store: the one already open, or a fresh snapshot
        of every piece the store should hold right now."""
        date = date or fields.Date.context_today(self)
        existing = self.search([('warehouse_id', '=', warehouse.id), ('date', '=', date)], limit=1)
        if existing:
            return existing
        rec = self.create({'warehouse_id': warehouse.id, 'date': date})
        self.env['jewellery.gold.reconciliation.line'].create([
            {'reconciliation_id': rec.id, 'lot_id': l.id, 'fine_g': fine_grams(l)} for l in warehouse.jewellery_lots()])
        return rec

    def action_count(self, serials):
        """What a person scanned, by serial. Known serials are found; unknown
        ones are listed as extras for a manager to look at. Scanning again
        adds to the count; it never un-finds a piece."""
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_('%s is closed.') % self.name)
        wanted = {(s or '').strip().upper() for s in (serials or []) if (s or '').strip()}
        by_serial = {l.lot_id.name.upper(): l for l in self.line_ids}
        extras = []
        for s in sorted(wanted):
            line = by_serial.get(s)
            if line:
                line.found = True
            else:
                extras.append(s)
        old = [x for x in (self.extra_serials or '').split(',') if x]
        self.extra_serials = ','.join(sorted(set(old) | set(extras))) or False
        return self.recon_dict()

    def action_close(self, note=None):
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_('%s is already closed.') % self.name)
        if not self.env.user.has_group('mumtaz_jewellery.group_jewellery_manager'):
            raise UserError(_('Only a manager closes a reconciliation.'))
        if self.variance_fine_g and not (note or self.note):
            raise UserError(_('%s has a variance of %.3f g; say what was decided before closing.') % (self.name, self.variance_fine_g))
        self.write({'state': 'closed', 'note': (note or self.note or '')[:300] or False,
                    'closed_by_id': self.env.user.id, 'closed_at': fields.Datetime.now()})
        return True

    def recon_dict(self, detail=False):
        self.ensure_one()
        data = {
            'id': self.id, 'name': self.name, 'state': self.state, 'date': self.date,
            'store': {'id': self.warehouse_id.id, 'name': self.warehouse_id.name},
            'expected_count': self.expected_count, 'expected_fine_g': round(self.expected_fine_g, 3),
            'counted_count': self.counted_count, 'counted_fine_g': round(self.counted_fine_g, 3),
            'variance_fine_g': round(self.variance_fine_g, 3), 'missing_count': self.missing_count,
            'extra_serials': [x for x in (self.extra_serials or '').split(',') if x], 'note': self.note or None,
            'opened_by': self.opened_by_id.name or None, 'closed_by': self.closed_by_id.name or None, 'closed_at': self.closed_at or None,
        }
        if detail:
            data['lines'] = [{'id': l.id, 'serial': l.lot_id.name, 'design': l.lot_id.product_id.name, 'karat': l.lot_id.karat,
                              'fine_g': round(l.fine_g, 3), 'found': l.found} for l in self.line_ids.sorted(lambda l: l.lot_id.name)]
            data['missing'] = [l['serial'] for l in data['lines'] if not l['found']]
        return data


class GoldReconciliationLine(models.Model):
    _name = 'jewellery.gold.reconciliation.line'
    _description = 'Reconciliation line: one piece expected'
    _order = 'id'

    reconciliation_id = fields.Many2one('jewellery.gold.reconciliation', required=True, ondelete='cascade', index=True)
    lot_id = fields.Many2one('stock.lot', string='Piece', required=True)
    fine_g = fields.Float(digits=(16, 3), string='Fine grams')
    found = fields.Boolean(default=False)
