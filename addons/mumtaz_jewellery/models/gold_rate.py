from odoo import _, api, fields, models
from odoo.exceptions import UserError


class JewelleryGoldRate(models.Model):
    """24K gold rate per gram. Approved rows are the only price source."""

    _name = 'jewellery.gold.rate'
    _description = 'Gold Rate (24K per gram)'
    _inherit = ['mail.thread']
    _order = 'effective_at desc, id desc'

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda s: s.env.company.currency_id)
    rate_per_gram = fields.Float(
        string='24K rate per gram', digits=(16, 4), required=True,
        tracking=True)
    effective_at = fields.Datetime(
        default=fields.Datetime.now, required=True, tracking=True)
    source = fields.Selection(
        [('manual', 'Manual'), ('feed', 'Rate feed')],
        default='manual', required=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('approved', 'Approved'),
         ('rejected', 'Rejected')],
        default='draft', required=True, tracking=True)
    approved_by_id = fields.Many2one('res.users', readonly=True)
    approved_at = fields.Datetime(readonly=True)

    @api.constrains('rate_per_gram')
    def _check_rate(self):
        for rec in self:
            if rec.rate_per_gram <= 0:
                raise UserError(_('The gold rate must be greater than zero.'))

    def _check_can_decide(self):
        if not self.env.user.has_group(
                'mumtaz_jewellery.group_jewellery_manager'):
            raise UserError(_('Only a jewellery manager can approve rates.'))
        allow_self = self.env['ir.config_parameter'].sudo().get_param(
            'mumtaz_jewellery.allow_self_approval') == '1'
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft rates can be approved or rejected.'))
            if not allow_self and rec.create_uid == self.env.user:
                raise UserError(_(
                    'Maker-checker: a different user must approve a rate '
                    'you entered.'))

    def action_approve(self):
        self._check_can_decide()
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approved_at': fields.Datetime.now(),
        })

    def action_reject(self):
        self._check_can_decide()
        self.write({'state': 'rejected'})

    @api.model
    def get_current(self, company=None):
        """Latest approved rate in force for ``company``. Raises if none."""
        company = company or self.env.company
        rate = self.search([
            ('state', '=', 'approved'),
            ('company_id', '=', company.id),
            ('effective_at', '<=', fields.Datetime.now()),
        ], limit=1)
        if not rate:
            raise UserError(_(
                'No approved gold rate is in force. Enter a rate and have '
                'it approved before pricing.'))
        return rate
