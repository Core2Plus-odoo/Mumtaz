from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ApprovalMemo(models.Model):
    _name = 'jewellery.approval.memo'
    _description = 'Pieces on approval (memo)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_out desc, id desc'

    name = fields.Char(default=lambda s: _('New'), copy=False, readonly=True)
    partner_id = fields.Many2one('res.partner', required=True, tracking=True)
    lot_ids = fields.Many2many('stock.lot', string='Pieces')
    date_out = fields.Date(default=fields.Date.context_today, required=True)
    return_by = fields.Date(required=True, tracking=True)
    state = fields.Selection([('out', 'Out on approval'), ('returned', 'Returned'), ('sold', 'Sold')],
                             default='out', tracking=True)
    insured_value = fields.Float(compute='_compute_value', digits=(16, 2))

    @api.depends('lot_ids')
    def _compute_value(self):
        for m in self:
            total = 0.0
            for lot in m.lot_ids:
                try:
                    total += lot.get_price_breakdown()['total']
                except UserError:
                    pass
            m.insured_value = total

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if not v.get('name') or v['name'] == _('New'):
                v['name'] = self.env['ir.sequence'].next_by_code('jewellery.approval.memo') or _('New')
        return super().create(vals_list)

    # --- stock ------------------------------------------------------------
    # A memo used to write a state field and nothing else, so a piece sitting
    # in a client's house still counted as on the shelf: stock value
    # overstated what was held, and a count could not reconcile. The piece is
    # still ours, so it moves to an internal location rather than out to a
    # customer -- ownership and valuation unchanged, shelf count correct.

    def _approval_location(self):
        return self.env.ref(
            'mumtaz_jewellery_vip.location_on_approval',
            raise_if_not_found=False)

    def _lot_current_location(self, lot):
        """Where the piece is now, by its quant. None if it is not in stock."""
        quant = self.env['stock.quant'].sudo().search([
            ('lot_id', '=', lot.id),
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'internal'),
        ], limit=1)
        return quant.location_id if quant else None

    def _move_pieces(self, destination, reference):
        """Move every piece on this memo to ``destination``, one serial each.

        Silently skips a piece that is not in stock: a memo may legitimately
        list a piece that was never received, and refusing to record the
        return of the others would be worse than an incomplete move.
        """
        destination = destination or self._approval_location()
        if not destination:
            return False
        moved = self.env['stock.move']
        for memo in self:
            for lot in memo.lot_ids:
                source = memo._lot_current_location(lot)
                if not source or source == destination:
                    continue
                move = self.env['stock.move'].sudo().create({
                    'name': '%s: %s' % (reference, lot.name),
                    'product_id': lot.product_id.id,
                    'product_uom_qty': 1.0,
                    'location_id': source.id,
                    'location_dest_id': destination.id,
                    'company_id': self.env.company.id,
                })
                move._action_confirm()
                move._action_assign()
                move.move_line_ids.write({'lot_id': lot.id, 'quantity': 1.0})
                if not move.move_line_ids:
                    self.env['stock.move.line'].sudo().create({
                        'move_id': move.id,
                        'product_id': lot.product_id.id,
                        'lot_id': lot.id,
                        'quantity': 1.0,
                        'location_id': source.id,
                        'location_dest_id': destination.id,
                    })
                move.picked = True
                move._action_done()
                moved |= move
        return moved

    def action_out(self):
        """Hand the pieces to the client: shelf -> On approval."""
        for memo in self:
            if memo.state != 'out':
                raise UserError(_(
                    'Memo %s is already %s.') % (memo.name, memo.state))
        self._move_pieces(self._approval_location(), _('On approval'))
        return True

    def action_return(self):
        """The client gives them back: On approval -> the shop."""
        for memo in self:
            if memo.state != 'out':
                raise UserError(_(
                    'Memo %(name)s is %(state)s, so there is nothing to '
                    'return.', name=memo.name, state=memo.state))
        warehouse = self.env['stock.warehouse'].sudo().search(
            [('company_id', '=', self.env.company.id)], limit=1)
        if warehouse:
            self._move_pieces(warehouse.lot_stock_id, _('Returned from approval'))
        self.write({'state': 'returned'})
        return True

    def action_sold(self):
        """She keeps them: On approval -> Customers, as any sale would."""
        for memo in self:
            if memo.state != 'out':
                raise UserError(_(
                    'Memo %(name)s is %(state)s, so it cannot be sold.',
                    name=memo.name, state=memo.state))
        customers = self.env.ref('stock.stock_location_customers',
                                 raise_if_not_found=False)
        if customers:
            self._move_pieces(customers, _('Sold from approval'))
        self.write({'state': 'sold'})
        return True

    @api.model
    def _cron_remind(self):
        today = fields.Date.context_today(self)
        for m in self.sudo().search([('state', '=', 'out'), ('return_by', '<=', today + timedelta(days=2))]):
            p = m.partner_id
            owner = p.relationship_manager_id or self.env.ref('base.user_admin')
            m.activity_schedule('mail.mail_activity_data_todo', date_deadline=m.return_by,
                                summary=_('Pieces on approval due back: %s') % m.name,
                                note=_('%(n)s pieces with %(c)s. Insured value %(v).2f. Contact the client personally.',
                                       n=len(m.lot_ids), c=p.name, v=m.insured_value),
                                user_id=owner.id)
