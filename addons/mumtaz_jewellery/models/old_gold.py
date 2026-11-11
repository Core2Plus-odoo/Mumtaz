from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services import pricing
from .product import KARATS

# Fields that record where an intake stands and who approved it, plus the
# valuation taken from the approved gold rate. They may only be set by the
# action_* methods, which run the state and maker-checker checks first.
DECISION_FIELDS = ('state', 'approved_by_id', 'rate_id',
                   'applied_rate_per_g', 'value')

# Context flag those methods set so their own writes are let through. Anything
# else that sets it has bypassed the checks.
DECISION_CONTEXT = 'jewellery_old_gold_decision'


class JewelleryOldGold(models.Model):
    """Old-gold (scrap) exchange: intake, melt loss, valuation, re-issue."""

    _name = 'jewellery.old.gold'
    _description = 'Old Gold Exchange'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(default=lambda s: _('New'), copy=False, readonly=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    partner_id = fields.Many2one('res.partner', string='Customer')
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    gross_weight_g = fields.Float(
        string='Gross weight (g)', digits=(16, 3), required=True)
    karat = fields.Selection(KARATS, required=True, default='22')
    melt_loss_pct = fields.Float(string='Melt loss %')
    buyback_discount_pct = fields.Float(string='Buy-back discount %')
    fine_weight_g = fields.Float(
        string='Fine weight (g)', digits=(16, 4), compute='_compute_value',
        store=True)
    applied_rate_per_g = fields.Float(
        string='Applied rate per gram', digits=(16, 4), readonly=True,
        copy=False)
    rate_id = fields.Many2one(
        'jewellery.gold.rate', string='Rate used', readonly=True, copy=False)
    value = fields.Monetary(
        currency_field='currency_id', readonly=True, tracking=True,
        copy=False)
    state = fields.Selection(
        [('draft', 'Draft'), ('to_approve', 'To approve'),
         ('confirmed', 'Confirmed'), ('issued', 'Issued to production'),
         ('cancelled', 'Cancelled')],
        default='draft', required=True, tracking=True, copy=False)
    approved_by_id = fields.Many2one('res.users', readonly=True, copy=False)

    @api.depends('gross_weight_g', 'karat', 'melt_loss_pct')
    def _compute_value(self):
        for rec in self:
            try:
                out = pricing.old_gold_value(
                    gross_weight_g=rec.gross_weight_g,
                    karat=int(rec.karat or 24),
                    melt_loss_pct=rec.melt_loss_pct,
                    rate_24k_per_g=0,
                )
                rec.fine_weight_g = float(out['fine_weight_g'])
            except ValueError:
                rec.fine_weight_g = 0.0

    # -- the state is moved only by the action_* methods -------------------
    #
    # Same guard as jewellery.gold.rate. Without it the second-person rule
    # above the approval threshold was advisory: `state` is read-only in the
    # views only and the ACL grants the Jewellery User group write, so an
    # intake could be written straight to 'confirmed' through the ORM or RPC,
    # skipping the approver, or skipping action_confirm and so the valuation
    # altogether. The valuation fields are guarded for the same reason: the
    # payout must come from the pricing engine at the approved rate, never
    # from whoever is at the counter. The guard holds for sudo as well.
    def _write_decision(self, values):
        """The one sanctioned path to the state, approver and valuation."""
        return self.with_context(**{DECISION_CONTEXT: True}).write(values)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state', 'draft') != 'draft':
                raise UserError(_(
                    'An old-gold exchange is created as a draft and then '
                    'valued and confirmed. It cannot be created in another '
                    'state.'))
            if vals.get('approved_by_id'):
                raise UserError(_(
                    'The approver is recorded by approving the exchange, not '
                    'when it is created.'))
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'jewellery.old.gold') or _('New')
        return super().create(vals_list)

    def write(self, values):
        if not self.env.context.get(DECISION_CONTEXT):
            touched = [name for name in DECISION_FIELDS if name in values]
            if touched:
                raise UserError(_(
                    'An old-gold exchange is moved on with the buttons, which '
                    'value it at the approved rate and, above the threshold, '
                    'require a different user to approve it. The valuation '
                    'comes from the pricing engine, never from a person. '
                    'These fields cannot be written directly: %s.')
                    % ', '.join(touched))
        return super().write(values)

    def _threshold(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'mumtaz_jewellery.exchange_approval_threshold')
        return float(param) if param else 0.0

    def _price_now(self):
        """Value the intake at the approved rate and snapshot it."""
        for rec in self:
            rate = self.env['jewellery.gold.rate'].get_current(rec.company_id)
            out = pricing.old_gold_value(
                gross_weight_g=rec.gross_weight_g,
                karat=int(rec.karat),
                melt_loss_pct=rec.melt_loss_pct,
                rate_24k_per_g=rate.rate_per_gram,
                buyback_discount_pct=rec.buyback_discount_pct,
            )
            rec._write_decision({
                'rate_id': rate.id,
                'applied_rate_per_g': float(out['applied_rate_per_g']),
                'value': float(out['value']),
            })

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft exchanges can be confirmed.'))
            if rec.gross_weight_g <= 0:
                raise UserError(_('Enter the gross weight.'))
            rec._price_now()
            limit = rec._threshold()
            needs_approval = limit and rec.value >= limit
            rec._write_decision({
                'state': 'to_approve' if needs_approval else 'confirmed'})

    def action_approve(self):
        if not self.env.user.has_group(
                'mumtaz_jewellery.group_jewellery_manager'):
            raise UserError(_('Only a jewellery manager can approve.'))
        for rec in self:
            if rec.state != 'to_approve':
                raise UserError(_('Nothing to approve on %s.') % rec.name)
            if rec.create_uid == self.env.user:
                raise UserError(_(
                    'Maker-checker: a different user must approve an '
                    'exchange you entered.'))
            rec._write_decision({
                'state': 'confirmed',
                'approved_by_id': self.env.user.id,
            })

    def action_issue_to_production(self):
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_('Only confirmed exchanges can be issued.'))
            rec._write_decision({'state': 'issued'})

    def action_cancel(self):
        for rec in self:
            if rec.state == 'issued':
                raise UserError(_('An issued exchange cannot be cancelled.'))
            rec._write_decision({'state': 'cancelled'})
