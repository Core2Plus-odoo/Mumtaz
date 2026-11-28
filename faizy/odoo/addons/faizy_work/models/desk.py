"""Checklist numbers on the one desk (§27).

faizy_ai's My desk (`faizy.my.desk`) is the per-person screen. Faizy Work adds
its own figures to it instead of a second screen: open, blocked and
ready-for-review checklists, research candidates to verify, and the way to
the scorecard. The founder's "Checklists to review" and scorecards hang off
faizy_ai's Command Centre.
"""
from odoo import api, fields, models


class FaizyMyDesk(models.TransientModel):
    _inherit = 'faizy.my.desk'

    ck_open = fields.Integer(string='Checklists open', compute='_compute_kpis')
    ck_blocked = fields.Integer(string='Checklists blocked', compute='_compute_kpis')
    ck_ready = fields.Integer(string='Ready for review', compute='_compute_kpis')
    leads_to_verify = fields.Integer(string='Research candidates to verify', compute='_compute_kpis')
    ck_team_ready = fields.Integer(string='Checklists ready for my review', compute='_compute_kpis')

    @api.depends('user_id')
    def _compute_kpis(self):
        super()._compute_kpis()
        Check = self.env['faizy.checklist'].sudo()
        Lead = self.env['crm.lead'].sudo()
        for desk in self:
            uid = desk.user_id.id
            desk.ck_open = Check.search_count([('owner_id', '=', uid), ('state', 'in', ('draft', 'in_progress'))])
            desk.ck_blocked = Check.search_count([('owner_id', '=', uid), ('state', '=', 'blocked')])
            desk.ck_ready = Check.search_count([('owner_id', '=', uid), ('state', '=', 'ready')])
            desk.leads_to_verify = Lead.search_count([
                ('user_id', '=', uid), ('active', '=', True), ('faizy_prospect_status', '=', 'research')])
            desk.ck_team_ready = Check.search_count([('state', 'in', ('ready', 'blocked'))]) if desk.is_manager else 0

    def action_open_checklists(self):
        return self._open(self.env._('My checklists'), 'faizy.checklist',
                          [('owner_id', '=', self.env.uid), ('state', '!=', 'approved')])

    def action_open_checklists_blocked(self):
        return self._open(self.env._('Blocked'), 'faizy.checklist',
                          [('owner_id', '=', self.env.uid), ('state', '=', 'blocked')])

    def action_open_leads_to_verify(self):
        return self._open(self.env._('Research candidates'), 'crm.lead', [
            ('user_id', '=', self.env.uid), ('faizy_prospect_status', '=', 'research')],
            view_mode='list,kanban,form')

    def action_open_checklists_review(self):
        return self.env.ref('faizy_work.action_checklists_review').sudo().read()[0]

    def action_open_scorecard(self):
        card = self.env['faizy.work.scorecard'].create({'user_id': self.env.uid})
        return {'type': 'ir.actions.act_window', 'res_model': 'faizy.work.scorecard',
                'res_id': card.id, 'view_mode': 'form', 'target': 'current'}
