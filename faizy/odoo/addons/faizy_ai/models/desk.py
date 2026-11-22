"""My desk: the numbers behind one person's day (HQ05 §24).

Same pattern as faizy.dashboard (BI-01): a TransientModel with computed
fields on an ordinary form, every tile opening the real list. Nothing is
stored, nothing is a second task system. "Done" is read from the standard
activity-done message (mail.message with mail_activity_type_id), so what
counts is exactly what the person closed on the record.
"""
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models

from .routing import LEAD_TYPES, T_COMPLETION_MSG, T_LEAD_QUALIFY, T_REPLY
from .utils import G_MANAGER


class FaizyMyDesk(models.TransientModel):
    _name = 'faizy.my.desk'
    _description = 'FAIZY my desk: today and this week'

    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True)
    is_manager = fields.Boolean(compute='_compute_kpis')

    # ── Work items (mail.activity, FAIZY types) ────────────────────────
    work_open = fields.Integer(string='Waiting for me', compute='_compute_kpis')
    work_due_today = fields.Integer(string='Due today', compute='_compute_kpis')
    work_overdue = fields.Integer(string='Overdue', compute='_compute_kpis')
    work_escalated = fields.Integer(string='Escalated', compute='_compute_kpis')
    done_today = fields.Integer(string='Done today', compute='_compute_kpis')
    done_week = fields.Integer(string='Done this week', compute='_compute_kpis')
    done_week_html = fields.Html(compute='_compute_kpis', sanitize=False)

    # ── Leads (standard crm.lead, my salesperson) ──────────────────────
    leads_mine = fields.Integer(string='My open leads', compute='_compute_kpis')
    leads_waiting = fields.Integer(string='Leads waiting on me', compute='_compute_kpis')
    leads_qualified_week = fields.Integer(string='Leads I qualified this week', compute='_compute_kpis')
    leads_won_month = fields.Integer(string='My leads won this month', compute='_compute_kpis')

    # ── Outcomes (team-wide, what the desks exist for) ─────────────────
    replies_week = fields.Integer(string='Replies I approved this week', compute='_compute_kpis')
    completion_msgs_week = fields.Integer(string='Completion messages I sent this week',
                                          compute='_compute_kpis')
    orders_completed_week = fields.Integer(string='Orders completed this week (team)',
                                           compute='_compute_kpis')

    team_html = fields.Html(compute='_compute_kpis', sanitize=False)

    # ------------------------------------------------------------------ helpers
    def _faizy_types(self):
        return self.env['mail.activity.type'].sudo().search([('faizy_route', '=', True)])

    def _done_count(self, partner, since, types=None):
        domain = [('author_id', '=', partner.id), ('date', '>=', since),
                  ('mail_activity_type_id', 'in', (types or self._faizy_types()).ids)]
        return self.env['mail.message'].sudo().search_count(domain)

    @api.depends('user_id')
    def _compute_kpis(self):
        Activity = self.env['mail.activity'].sudo()
        Lead = self.env['crm.lead'].sudo()
        today = fields.Date.context_today(self)
        day_start = fields.Datetime.to_datetime(today)
        week_start = fields.Datetime.to_datetime(today - timedelta(days=today.weekday()))
        month_start = fields.Datetime.to_datetime(today.replace(day=1))
        types = self._faizy_types()
        lead_types = self.env['mail.activity.type'].sudo().browse(
            [self.env.ref(x).id for x in LEAD_TYPES])
        t_qualify = self.env.ref(T_LEAD_QUALIFY)
        t_reply = self.env.ref(T_REPLY)
        t_completion = self.env.ref(T_COMPLETION_MSG)
        orders_week = self.env['faizy.order'].sudo().search_count([
            ('state', '=', 'completed'), ('is_sample', '=', False),
            ('date_completed', '>=', week_start)])

        for desk in self:
            user = desk.user_id
            partner = user.partner_id
            mine = Activity.search([('user_id', '=', user.id), ('activity_type_id', 'in', types.ids)])
            desk.is_manager = user.has_group(G_MANAGER)
            desk.work_open = len(mine)
            desk.work_due_today = len(mine.filtered(lambda a: a.date_deadline == today))
            desk.work_overdue = len(mine.filtered(lambda a: a.date_deadline < today))
            desk.work_escalated = len(mine.filtered('faizy_escalated'))
            desk.done_today = desk._done_count(partner, day_start)
            desk.done_week = desk._done_count(partner, week_start)
            rows = self.env['mail.message'].sudo()._read_group(
                [('author_id', '=', partner.id), ('date', '>=', week_start),
                 ('mail_activity_type_id', 'in', types.ids)],
                ['mail_activity_type_id'], ['__count'])
            desk.done_week_html = Markup('<ul>%s</ul>') % Markup('').join(
                Markup('<li>%s: %s</li>') % (escape(t.name), n) for t, n in rows) if rows else ''

            desk.leads_mine = Lead.search_count([('user_id', '=', user.id), ('stage_id.is_won', '=', False)])
            desk.leads_waiting = Lead.search_count([
                ('user_id', '=', user.id), ('activity_ids.activity_type_id', 'in', lead_types.ids)])
            desk.leads_qualified_week = desk._done_count(partner, week_start, t_qualify)
            desk.leads_won_month = Lead.search_count([
                ('user_id', '=', user.id), ('stage_id.is_won', '=', True),
                ('date_closed', '>=', month_start)])

            desk.replies_week = desk._done_count(partner, week_start, t_reply)
            desk.completion_msgs_week = desk._done_count(partner, week_start, t_completion)
            desk.orders_completed_week = orders_week
            desk.team_html = desk._team_html(types, week_start) if desk.is_manager else ''

    def _team_html(self, types, week_start):
        Routing = self.env['faizy.routing']
        Activity = self.env['mail.activity'].sudo()
        today = fields.Date.context_today(self)
        rows = []
        for role, label in (('care', 'Customer care'), ('ops', 'Operations'), ('escalation', 'Escalation')):
            user = Routing._role_user(role)
            mine = Activity.search([('user_id', '=', user.id), ('activity_type_id', 'in', types.ids)])
            rows.append(Markup('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>') % (
                escape(label), escape(user.name), len(mine),
                len(mine.filtered(lambda a: a.date_deadline < today or a.faizy_escalated)),
                self._done_count(user.partner_id, week_start, types)))
        return Markup('<table class="table table-sm"><thead><tr><th>Role</th><th>Holder</th>'
                      '<th>Waiting</th><th>Overdue or escalated</th><th>Done this week</th>'
                      '</tr></thead><tbody>%s</tbody></table>') % Markup('').join(rows)

    # ------------------------------------------------------------------ drill-through
    def _open(self, name, model, domain, view_mode='list,form', context=None):
        return {'type': 'ir.actions.act_window', 'name': name, 'res_model': model,
                'view_mode': view_mode, 'domain': domain, 'target': 'current',
                'context': context or {}}

    def _my_work_domain(self):
        return [('user_id', '=', self.env.user.id), ('activity_type_id.faizy_route', '=', True)]

    def action_open_work(self):
        action = self.env.ref('faizy_ai.action_faizy_my_work').sudo().read()[0]
        return action

    def action_open_overdue(self):
        today = fields.Date.context_today(self)
        return self._open(self.env._('Overdue'), 'mail.activity',
                          self._my_work_domain() + [('date_deadline', '<', today)],
                          view_mode='list')

    def action_open_escalated(self):
        return self._open(self.env._('Escalated'), 'mail.activity',
                          self._my_work_domain() + [('faizy_escalated', '=', True)], view_mode='list')

    def action_open_leads(self):
        return self.env.ref('faizy_ai.action_faizy_my_leads').sudo().read()[0]

    def action_open_leads_waiting(self):
        return self.env.ref('faizy_ai.action_faizy_leads_waiting').sudo().read()[0]

    def action_open_orders_week(self):
        today = fields.Date.context_today(self)
        week_start = fields.Datetime.to_datetime(today - timedelta(days=today.weekday()))
        return self._open(self.env._('Completed this week'), 'faizy.order',
                          [('state', '=', 'completed'), ('date_completed', '>=', week_start)])
