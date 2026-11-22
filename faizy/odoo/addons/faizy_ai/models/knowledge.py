from odoo import fields, models


class FaizyAIKnowledge(models.Model):
    """A note the AI agents read before they draft.

    Guidance only. The hard rules (send window, blocked numbers, who may
    approve, what a draft may change) are enforced in code and cannot be
    edited here.
    """
    _name = 'faizy.ai.knowledge'
    _description = 'Faizy AI knowledge note'
    _order = 'category, sequence, id'

    name = fields.Char(required=True)
    category = fields.Selection([
        ('brand', 'Brand facts and tone'),
        ('procedure', 'Procedure'),
        ('template', 'Reply or post template'),
        ('rule', 'House rule'),
    ], required=True, default='procedure')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    body = fields.Text(required=True)
    agent_ids = fields.Many2many(
        'faizy.ai.agent', string='Only for these agents',
        help='Leave empty to show this note to every agent.')
