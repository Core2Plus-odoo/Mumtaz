from odoo import api, fields, models
from odoo.exceptions import UserError

# Records a checklist may be attached to. 'none' is a standalone checklist
# (daily start/end, weekly review, campaign preparation, service readiness).
ATTACHABLE = [
    ('crm.lead', 'CRM lead'),
    ('faizy.order', 'FAIZY order'),
    ('res.partner', 'Vendor / contact'),
    ('faizy.ai.draft', 'AI draft'),
    ('none', 'Standalone (not tied to a record)'),
]

# Conditional items: the key is evaluated against the record, so a step only
# appears (and only blocks) when it applies.
CONDITIONS = [
    ('always', 'Always'),
    ('org', 'Organisation prospect'),
    ('individual', 'Individual prospect'),
    ('purchase', 'Order involves a purchase'),
]

# The business action a mandatory item protects. Enforced server-side.
GATES = [
    ('', 'No gate'),
    ('verify', 'Before a prospect is Verified'),
    ('qualify', 'Before a lead is Qualified'),
    ('assign', 'Before an order is assigned'),
    ('complete', 'Before an order is completed'),
    ('approve', 'Before a draft is approved'),
]

# Daily / weekly items that fill themselves from existing Odoo records.
AUTO_KEYS = [
    ('', 'Manual'),
    ('overdue', 'No overdue activities'),
    ('due_today', 'Activities due today (info)'),
    ('leads_no_next', 'Open leads without a next action'),
    ('orders_open', 'Open orders (info)'),
    ('evidence_pending', 'Evidence waiting for review (info)'),
    ('drafts_waiting', 'Drafts waiting for approval (info)'),
    ('blocked', 'Blocked checklists (info)'),
]


class FaizyChecklistTemplate(models.Model):
    _name = 'faizy.checklist.template'
    _description = 'FAIZY checklist template'
    _order = 'role, code, version desc'

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True, help='Stable key. A new version keeps the code.')
    version = fields.Integer(default=1, readonly=True, copy=False)
    res_model = fields.Selection(ATTACHABLE, string='Attaches to', required=True, default='crm.lead')
    kind = fields.Selection([
        ('record', 'On a record'),
        ('standalone', 'Standalone, started by hand'),
        ('daily_start', 'Daily: start of shift'),
        ('daily_end', 'Daily: end of shift'),
        ('weekly', 'Weekly review'),
    ], required=True, default='record')
    role = fields.Selection([
        ('cx', 'Digital Marketing & CX (Mashood)'),
        ('ops', 'Business Development & Operations (Raza)'),
        ('any', 'Any staff'),
    ], required=True, default='any')
    state = fields.Selection([
        ('draft', 'Draft'), ('released', 'Released'), ('retired', 'Retired'),
    ], default='draft', required=True, readonly=True, copy=False)
    description = fields.Text()
    user_ids = fields.Many2many(
        'res.users', string='Recurring for',
        help='Daily and weekly checklists are created for these people, once per period. '
             'Empty means nobody gets one: assigning staff is an explicit decision.')
    item_ids = fields.One2many('faizy.checklist.template.item', 'template_id', copy=True)

    _code_version_uniq = models.Constraint(
        'unique(code, version)', 'This template code already has that version.')

    def action_release(self):
        for tpl in self:
            if not tpl.item_ids:
                raise UserError(self.env._('Add at least one item before releasing.'))
            tpl.state = 'released'

    def action_new_version(self):
        """Edit by versioning: finished checklists keep the wording they were done with."""
        self.ensure_one()
        latest = self.search([('code', '=', self.code)], order='version desc', limit=1)
        new = self.copy({'version': latest.version + 1, 'state': 'draft'})
        self.state = 'retired'
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name,
            'res_id': new.id, 'view_mode': 'form',
        }

    def write(self, vals):
        locked = {'name', 'code', 'res_model', 'kind', 'role', 'item_ids'}
        if locked & set(vals):
            for tpl in self:
                if tpl.state != 'draft' and not self.env.context.get('faizy_template_seed'):
                    raise UserError(self.env._(
                        'A released template cannot be edited. Use "New version" so finished '
                        'checklists keep the wording they were completed with.'))
        return super().write(vals)

    @api.model
    def _latest(self, code):
        return self.search([('code', '=', code), ('state', '=', 'released')],
                           order='version desc', limit=1)


class FaizyChecklistTemplateItem(models.Model):
    _name = 'faizy.checklist.template.item'
    _description = 'FAIZY checklist template item'
    _order = 'sequence, id'

    template_id = fields.Many2one('faizy.checklist.template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, string='Step')
    sop = fields.Text(string='How to do it', help='Short SOP shown inline on the checklist.')
    mandatory = fields.Boolean(default=True)
    condition = fields.Selection(CONDITIONS, default='always', required=True)
    evidence_required = fields.Boolean(
        help='A link to the existing record, a URL or a short note is needed before this can be ticked.')
    restricted = fields.Boolean(
        help='Needs a Faizy Manager who is not the checklist owner (financial, policy or sensitive exception).')
    gate = fields.Selection(GATES, default='')
    auto_key = fields.Selection(AUTO_KEYS, default='')

    def write(self, vals):
        for item in self:
            if item.template_id.state != 'draft' and not self.env.context.get('faizy_template_seed'):
                raise UserError(self.env._('Released template items cannot be edited. Use "New version".'))
        return super().write(vals)

    def unlink(self):
        for item in self:
            if item.template_id.state != 'draft' and not self.env.context.get('faizy_template_seed'):
                raise UserError(self.env._('Released template items cannot be removed. Use "New version".'))
        return super().unlink()
