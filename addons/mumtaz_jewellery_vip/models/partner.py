from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

TIERS = [('standard', 'Standard'), ('preferred', 'Preferred'),
         ('private', 'Private'), ('royal', 'Royal / Protocol')]
RESTRICTED = ('private', 'royal')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    jewellery_tier = fields.Selection(TIERS, string='Client tier', default='standard',
                                      tracking=True, index=True)
    relationship_manager_id = fields.Many2one('res.users', string='Relationship manager', tracking=True)
    deputy_id = fields.Many2one('res.users', string='Deputy (cover)')
    discreet_billing = fields.Boolean(help='Private invoices; bill-to contact may differ from the client.')
    no_marketing = fields.Boolean(string='No marketing messages')
    preferred_karats = fields.Char(help='Comma separated, e.g. 22,21')
    typical_budget = fields.Float(string='Typical spend')
    taste_notes = fields.Text(string='Taste and preferences')
    jewellery_restricted = fields.Boolean(compute='_compute_restricted')
    ai_autonomy_cap = fields.Integer(
        compute='_compute_restricted', string='AI autonomy ceiling',
        help='1 observe, 2 draft, 3 act with approval. Private and Royal clients are capped at 2: '
             'AI prepares, a person sends.')
    lifetime_value = fields.Monetary(compute='_compute_ltv', currency_field='company_currency_id')
    company_currency_id = fields.Many2one('res.currency', compute='_compute_company_currency')
    occasion_ids = fields.One2many('jewellery.occasion', 'partner_id')
    memo_ids = fields.One2many('jewellery.approval.memo', 'partner_id')
    suggestion_ids = fields.One2many('jewellery.offer.suggestion', 'partner_id')

    def _compute_company_currency(self):
        for p in self:
            p.company_currency_id = self.env.company.currency_id

    @api.depends('jewellery_tier')
    def _compute_restricted(self):
        for p in self:
            r = p.jewellery_tier in RESTRICTED
            p.jewellery_restricted = r
            p.ai_autonomy_cap = 2 if r else 3

    def _compute_ltv(self):
        Sale = self.env['sale.order'].sudo()
        for p in self:
            orders = Sale.search([('partner_id', '=', p.id), ('state', '=', 'sale')])
            p.lifetime_value = sum(orders.mapped('amount_total'))

    @api.constrains('jewellery_tier', 'relationship_manager_id')
    def _check_rm(self):
        for p in self:
            if p.jewellery_tier in RESTRICTED and not p.relationship_manager_id:
                raise ValidationError(_('Private and Royal clients need a named relationship manager.'))

    def _check_tier_change(self, vals):
        if 'jewellery_tier' in vals and vals['jewellery_tier'] in RESTRICTED:
            if not self.env.su and not self.env.user.has_group('mumtaz_jewellery_vip.group_vip_manager'):
                raise AccessError(_('Only a VIP manager can place a client in the Private or Royal tier.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_tier_change(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._check_tier_change(vals)
        if any(f in vals for f in ('jewellery_tier', 'relationship_manager_id', 'deputy_id')) \
                and not self.env.su and any(p.jewellery_restricted for p in self) \
                and not self.env.user.has_group('mumtaz_jewellery_vip.group_vip_manager'):
            raise AccessError(_('Only a VIP manager can change tier or ownership of Private and Royal clients.'))
        return super().write(vals)

    def web_read(self, specification):
        res = super().web_read(specification)
        restricted = self.filtered(lambda p: p.sudo().jewellery_tier in RESTRICTED)
        if restricted:
            self.env['jewellery.vip.access.log'].sudo().create([
                {'partner_id': p.id, 'user_id': self.env.user.id, 'action': 'view'} for p in restricted])
        return res

    def action_suggest_pieces(self):
        self.ensure_one()
        self.env['jewellery.offer.suggestion'].generate_for(self)
        return True
