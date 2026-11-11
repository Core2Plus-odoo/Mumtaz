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

    def action_return(self):
        self.write({'state': 'returned'})

    def action_sold(self):
        self.write({'state': 'sold'})

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
