from markupsafe import Markup, escape

from odoo import api, fields, models

G_MANAGER = 'faizy_core.group_faizy_manager'


def _counts(env, user):
    """Everything on a person's desk, counted from the business records."""
    today = fields.Date.context_today(env['faizy.work.desk'])
    Act = env['mail.activity'].sudo()
    Lead = env['crm.lead'].sudo()
    Check = env['faizy.checklist'].sudo()
    leads = Lead.search([('user_id', '=', user.id), ('active', '=', True), ('probability', '<', 100)])
    return {
        'overdue': Act.search_count([('user_id', '=', user.id), ('date_deadline', '<', today)]),
        'today': Act.search_count([('user_id', '=', user.id), ('date_deadline', '=', today)]),
        'leads': len(leads),
        'leads_no_next': len(leads.filtered(lambda ln: not ln.activity_ids)),
        'to_verify': len(leads.filtered(lambda ln: ln.faizy_prospect_status == 'research')),
        'ck_open': Check.search_count([('owner_id', '=', user.id), ('state', 'in', ('draft', 'in_progress'))]),
        'ck_blocked': Check.search_count([('owner_id', '=', user.id), ('state', '=', 'blocked')]),
        'ck_ready': Check.search_count([('owner_id', '=', user.id), ('state', '=', 'ready')]),
    }


class FaizyWorkDesk(models.TransientModel):
    """My Work: one screen per employee. Everything here is a count of, or a
    link to, the existing record. Nothing is typed into this screen."""
    _name = 'faizy.work.desk'
    _description = 'FAIZY My Work desk'

    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True)
    summary = fields.Html(compute='_compute_summary', sanitize=False)

    @api.depends('user_id')
    def _compute_summary(self):
        for rec in self:
            c = _counts(self.env, rec.user_id or self.env.user)

            def cell(label, n, warn=False):
                cls = 'text-bg-danger' if (warn and n) else 'text-bg-light'
                return '<span class="badge %s me-2 mb-2 fs-6">%s: %s</span>' % (cls, escape(label), n)
            rec.summary = Markup(
                '<div>%s</div>' % ''.join([
                    cell(self.env._('Overdue'), c['overdue'], True),
                    cell(self.env._('Due today'), c['today']),
                    cell(self.env._('Open leads'), c['leads']),
                    cell(self.env._('Leads without a next action'), c['leads_no_next'], True),
                    cell(self.env._('To verify'), c['to_verify']),
                    cell(self.env._('Checklists open'), c['ck_open']),
                    cell(self.env._('Blocked'), c['ck_blocked'], True),
                    cell(self.env._('Ready for review'), c['ck_ready']),
                ]))

    def _act(self, name, model, domain, view='list,form', ctx=None):
        return {'type': 'ir.actions.act_window', 'name': name, 'res_model': model,
                'view_mode': view, 'domain': domain, 'context': ctx or {}}

    def action_my_activities(self):
        return self._act(self.env._('My activities'), 'mail.activity',
                         [('user_id', '=', self.env.uid)], 'list,form', {'default_user_id': self.env.uid})

    def action_my_leads(self):
        return self._act(self.env._('My leads'), 'crm.lead',
                         [('user_id', '=', self.env.uid), ('type', '=', 'opportunity')],
                         'kanban,list,form,activity')

    def action_my_checklists(self):
        return self._act(self.env._('My checklists'), 'faizy.checklist',
                         [('owner_id', '=', self.env.uid), ('state', '!=', 'approved')])

    def action_my_scorecard(self):
        card = self.env['faizy.work.scorecard'].create({'user_id': self.env.uid})
        return {'type': 'ir.actions.act_window', 'res_model': 'faizy.work.scorecard',
                'res_id': card.id, 'view_mode': 'form'}

    @api.model
    def action_open(self):
        desk = self.create({'user_id': self.env.uid})
        return {'type': 'ir.actions.act_window', 'name': self.env._('My Work'),
                'res_model': self._name, 'res_id': desk.id, 'view_mode': 'form'}


class FaizyWorkCommand(models.TransientModel):
    """Founder command centre: both employees side by side, each figure one
    click from the records behind it."""
    _name = 'faizy.work.command'
    _description = 'FAIZY founder command centre'

    summary = fields.Html(compute='_compute_summary', sanitize=False)

    @api.depends_context('uid')
    def _compute_summary(self):
        routing = self.env['faizy.routing']
        people = [
            (self.env._('Digital Marketing & CX'), routing._role_user('care')),
            (self.env._('BD & Operations'), routing._role_user('ops')),
        ]
        order = [('overdue', self.env._('Overdue activities')), ('today', self.env._('Due today')),
                 ('leads', self.env._('Open leads')), ('leads_no_next', self.env._('Leads without next action')),
                 ('to_verify', self.env._('Research candidates')),
                 ('ck_open', self.env._('Checklists open')), ('ck_blocked', self.env._('Blocked')),
                 ('ck_ready', self.env._('Ready for your review'))]
        counts = [(role, user, _counts(self.env, user)) for role, user in people]
        head = ''.join('<th class="text-end">%s<br/><small class="text-muted">%s</small></th>' % (
            escape(user.name), escape(role)) for role, user, _c in counts)
        body = ''.join('<tr><td>%s</td>%s</tr>' % (escape(label), ''.join(
            '<td class="text-end">%s</td>' % c[key] for _r, _u, c in counts)) for key, label in order)
        wa = self.env['ir.config_parameter'].sudo().get_param('faizy.whatsapp_send_mode')
        for rec in self:
            rec.summary = Markup(
                '<table class="table table-sm"><thead><tr><th></th>%s</tr></thead><tbody>%s</tbody></table>'
                '<p class="text-muted small">Customer WhatsApp sending: <b>%s</b>.</p>' % (
                    head, body, 'ON' if wa == 'on' else 'OFF'))

    def _act(self, name, model, domain, view='list,form', ctx=None):
        return {'type': 'ir.actions.act_window', 'name': name, 'res_model': model,
                'view_mode': view, 'domain': domain, 'context': ctx or {}}

    def action_overdue(self):
        today = fields.Date.context_today(self)
        return self._act(self.env._('Overdue activities'), 'mail.activity',
                         [('date_deadline', '<', today)], 'list,form', {'group_by': ['user_id']})

    def action_pipeline(self):
        return self._act(self.env._('Pipeline by owner and prospect status'), 'crm.lead',
                         [('type', '=', 'opportunity')], 'pivot,list,form',
                         {'pivot_row_groupby': ['user_id'], 'pivot_column_groupby': ['faizy_prospect_status'],
                          'search_default_groupby_user': 1})

    def action_checklists(self):
        return self._act(self.env._('Checklists'), 'faizy.checklist',
                         [('state', 'in', ('ready', 'blocked'))], 'list,form', {'group_by': ['owner_id', 'state']})

    def action_scorecards(self):
        card = self.env['faizy.work.scorecard'].create({'user_id': self.env.uid})
        return {'type': 'ir.actions.act_window', 'res_model': 'faizy.work.scorecard',
                'res_id': card.id, 'view_mode': 'form'}

    @api.model
    def action_open(self):
        cc = self.create({})
        return {'type': 'ir.actions.act_window', 'name': self.env._('Founder command centre'),
                'res_model': self._name, 'res_id': cc.id, 'view_mode': 'form'}
