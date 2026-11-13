from odoo import api, fields, models


class FaizyAIAgent(models.Model):
    _name = 'faizy.ai.agent'
    _description = 'Faizy AI agent'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    role = fields.Selection([
        ('cos', 'Chief of Staff'),
        ('insights', 'Insights / analytics'),
        ('ops', 'Operations coordinator'),
        ('customer', 'Customer care drafts'),
        ('content', 'Content strategy'),
        ('script', 'Scriptwriter'),
        ('visuals', 'Visuals and storyboard'),
        ('voice', 'Voice'),
        ('edit', 'Edit and QC'),
    ], required=True)
    user_id = fields.Many2one(
        'res.users', string='API user',
        help='Restricted user this agent logs in as. Put it in the group '
             '"Faizy AI / Agent (API user)" only.')
    supervisor_id = fields.Many2one(
        'res.users', string='Supervisor',
        help='Person who looks after this agent and approves its drafts.')
    instructions = fields.Text()
    draft_ids = fields.One2many('faizy.ai.draft', 'agent_id')
    draft_count = fields.Integer(compute='_compute_drafts')
    pending_count = fields.Integer(compute='_compute_drafts')

    _unique_code = models.Constraint('UNIQUE(code)', 'Agent code must be unique.')

    @api.depends('draft_ids.state')
    def _compute_drafts(self):
        for agent in self:
            agent.draft_count = len(agent.draft_ids)
            agent.pending_count = len(agent.draft_ids.filtered(lambda d: d.state == 'draft'))
