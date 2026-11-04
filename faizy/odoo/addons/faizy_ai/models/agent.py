from dateutil.relativedelta import relativedelta

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
    approved_30d = fields.Integer(compute='_compute_drafts', string='Approved (30 days)')
    rejected_30d = fields.Integer(compute='_compute_drafts', string='Rejected (30 days)')
    approval_rate = fields.Float(compute='_compute_drafts', string='Approval rate (30 days)',
                                 help='Share of decided drafts that were approved, in percent.')

    _unique_code = models.Constraint('UNIQUE(code)', 'Agent code must be unique.')

    @api.depends('draft_ids.state')
    def _compute_drafts(self):
        for agent in self:
            agent.draft_count = len(agent.draft_ids)
            agent.pending_count = len(agent.draft_ids.filtered(lambda d: d.state == 'draft'))
            since = fields.Datetime.now() - relativedelta(days=30)
            recent = agent.draft_ids.filtered(lambda d: d.create_date and d.create_date >= since)
            rejected = len(recent.filtered(lambda d: d.state == 'rejected'))
            approved = len(recent.filtered(lambda d: d.state in ('approved', 'executed')))
            agent.approved_30d = approved
            agent.rejected_30d = rejected
            decided = approved + rejected
            agent.approval_rate = (approved * 100.0 / decided) if decided else 0.0

    def get_brief(self):
        """What this agent should read before it drafts.

        Returns its instructions, the knowledge notes meant for it (or for
        everyone), and its most recent rejected drafts with the reason, so it
        stops repeating the same mistake. Read-only.
        """
        self.ensure_one()
        notes = self.env['faizy.ai.knowledge'].search(
            ['|', ('agent_ids', '=', False), ('agent_ids', 'in', self.id)])
        since = fields.Datetime.now() - relativedelta(days=30)
        lessons = self.env['faizy.ai.draft'].search([
            ('agent_id', '=', self.id), ('state', '=', 'rejected'),
            ('create_date', '>=', since)], order='create_date desc', limit=10)
        return {
            'agent': self.code,
            'instructions': self.instructions or '',
            'knowledge': [
                {'name': n.name, 'category': n.category, 'body': n.body} for n in notes],
            'lessons': [
                {'kind': d.kind, 'subject': d.subject, 'reason': d.reject_reason}
                for d in lessons],
            'approval_rate_30d': self.approval_rate,
        }
