from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Fields that record an approval decision. They may only be set by
# action_approve / action_reject, which run the maker-checker checks first.
DECISION_FIELDS = ('state', 'approved_by_id', 'approved_at')

# Context flag those two methods set so their own write is let through. It is
# deliberately not a public API: anything that sets it has bypassed the
# maker-checker checks.
DECISION_CONTEXT = 'jewellery_rate_decision'


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
        default='draft', required=True, tracking=True, copy=False)
    approved_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)

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

    # -- the decision fields are writable only through the two buttons ----
    #
    # Without this, maker-checker was advisory: `state` is read-only in the
    # views only, and the ACL grants the Jewellery User group write and
    # create, so a rate could reach 'approved' through the ORM or RPC without
    # action_approve ever running. The guard holds for sudo as well, because
    # system code has no business approving a rate either; a rate feed enters
    # a draft and a person decides on it.
    def _write_decision(self, values):
        """The one sanctioned path to the decision fields."""
        return self.with_context(**{DECISION_CONTEXT: True}).write(values)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state', 'draft') != 'draft':
                raise UserError(_(
                    'A gold rate is created as a draft and then approved by a '
                    'different user. It cannot be created already approved.'))
            preset = [name for name in ('approved_by_id', 'approved_at')
                      if vals.get(name)]
            if preset:
                raise UserError(_(
                    'The approval fields (%s) are set by approving the rate, '
                    'not when it is created.') % ', '.join(preset))
        return super().create(vals_list)

    def write(self, values):
        if not self.env.context.get(DECISION_CONTEXT):
            touched = [name for name in DECISION_FIELDS if name in values]
            if touched:
                raise UserError(_(
                    'A gold rate is approved or rejected with the Approve and '
                    'Reject buttons, which require a different user from the '
                    'one who entered it. These fields cannot be written '
                    'directly: %s.') % ', '.join(touched))
        return super().write(values)

    def action_approve(self):
        self._check_can_decide()
        self._write_decision({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approved_at': fields.Datetime.now(),
        })

    def action_reject(self):
        self._check_can_decide()
        self._write_decision({'state': 'rejected'})

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
