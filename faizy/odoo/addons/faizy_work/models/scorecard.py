from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import AccessError

G_MANAGER = 'faizy_core.group_faizy_manager'
KPI_START_PARAM = 'faizy.kpi_start'
CONVERSION_TARGET_PARAM = 'faizy.kpi_conversion_target'
BASELINE_DAYS = 14
MIN_WEIGHT_FOR_TOTAL = 60

# component key, label, weight (cx = Mashood, ops = Raza)
WEIGHTS = {
    'cx': [('pipeline', 'Qualified pipeline', 30), ('conversion', 'Conversion', 20),
           ('service', 'Customer experience', 25), ('media', 'Content and media quality', 15),
           ('discipline', 'ERP discipline', 10)],
    'ops': [('pipeline', 'Direct-sales pipeline', 35), ('conversion', 'Conversion', 25),
            ('service', 'Delivery quality', 20), ('media', 'Partner and vendor readiness', 10),
            ('discipline', 'ERP discipline', 10)],
}
# Weekly pilot targets from the staff-work brief.
TARGETS = {
    'cx': {'verified': 15, 'drafts': 10},
    'ops': {'verified': 12, 'drafts': 8, 'discovery': 3},
}
CHECKLIST_CODES = {
    'cx': ('content_quality', 'campaign_preparation'),
    'ops': ('vendor_worker_verification', 'partnership_development', 'service_readiness'),
}


class FaizyWorkScorecard(models.TransientModel):
    _name = 'faizy.work.scorecard'
    _description = 'FAIZY staff scorecard (computed from real records)'

    user_id = fields.Many2one('res.users', string='Employee', required=True,
                              default=lambda self: self.env.user)
    profile = fields.Selection([('cx', 'Digital Marketing & CX'), ('ops', 'BD & Operations')],
                               compute='_compute_scorecard')
    date_to = fields.Date(default=fields.Date.context_today, required=True)
    date_from = fields.Date(
        default=lambda self: fields.Date.context_today(self) - timedelta(days=BASELINE_DAYS),
        required=True)
    status = fields.Char(compute='_compute_scorecard')
    total_display = fields.Char(string='Weighted total', compute='_compute_scorecard')
    report = fields.Html(compute='_compute_scorecard', sanitize=False)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group(G_MANAGER):
            for vals in vals_list:
                vals['user_id'] = self.env.uid
        return super().create(vals_list)

    # ── profile ──────────────────────────────────────────────────────────
    def _profile_of(self, user):
        routing = self.env['faizy.routing']
        if user == routing._role_user('care') and user.has_group('faizy_ai.group_comms'):
            return 'cx'
        if user.has_group('faizy_ai.group_comms') and not user.has_group('faizy_core.group_faizy_ops'):
            return 'cx'
        return 'ops'

    # ── measures, each from real records ─────────────────────────────────
    def _m(self, user, d_from, d_to):
        Lead = self.env['crm.lead'].sudo().with_context(active_test=False)
        window = [('faizy_verified_on', '>=', d_from), ('faizy_verified_on', '<=', d_to)]
        m = {
            'verified': Lead.search_count([('faizy_originator_id', '=', user.id)] + window),
            'drafts': self.env['faizy.ai.draft'].sudo().search_count([
                ('create_uid', '=', user.id), ('kind', '=', 'customer_message'),
                ('create_date', '>=', fields.Datetime.to_datetime(d_from)),
                ('create_date', '<', fields.Datetime.to_datetime(d_to) + timedelta(days=1))]),
            'discovery': Lead.search_count([
                ('user_id', '=', user.id), ('faizy_engaged_on', '>=', d_from),
                ('faizy_engaged_on', '<=', d_to)]),
            'qualified': Lead.search_count([
                ('faizy_originator_id', '=', user.id), ('faizy_qualified_on', '>=', d_from),
                ('faizy_qualified_on', '<=', d_to)]),
        }
        open_leads = Lead.search([('user_id', '=', user.id), ('active', '=', True), ('probability', '<', 100)])
        m['open_leads'] = len(open_leads)
        m['open_leads_next'] = len(open_leads.filtered(lambda ln: ln.activity_ids))
        acts = self.env['mail.activity'].sudo().search([('user_id', '=', user.id)])
        today = fields.Date.context_today(self)
        m['open_acts'] = len(acts)
        m['overdue_acts'] = len(acts.filtered(lambda a: a.date_deadline < today))
        m['any_record'] = bool(
            m['verified'] or m['drafts'] or m['open_leads'] or m['open_acts'] or
            self.env['faizy.checklist'].sudo().search_count([('owner_id', '=', user.id)]))
        return m

    def _ratio_target(self, value, target):
        return min(1.0, value / target) if target else None

    def _components(self, user, profile, d_from, d_to, baseline_done):
        m = self._m(user, d_from, d_to)
        tg = TARGETS[profile]
        env = self.env
        out = {}
        # pipeline
        if not m['any_record'] or (d_to - d_from).days < 6:
            out['pipeline'] = (None, env._('Needs a window of at least 7 days and some activity.'))
        else:
            parts = [(0.6 if profile == 'cx' else 0.5, self._ratio_target(m['verified'], tg['verified'])),
                     (0.4 if profile == 'cx' else 0.3, self._ratio_target(m['drafts'], tg['drafts']))]
            if profile == 'ops':
                parts.append((0.2, self._ratio_target(m['discovery'], tg['discovery'])))
            score = sum(w * v for w, v in parts)
            detail = env._('%(v)s verified prospects (target %(tv)s), %(d)s outreach drafts (target %(td)s)',
                           v=m['verified'], tv=tg['verified'], d=m['drafts'], td=tg['drafts'])
            if profile == 'ops':
                detail += env._(', %(x)s discovery conversations (stretch %(tx)s)',
                                x=m['discovery'], tx=tg['discovery'])
            out['pipeline'] = (100 * score, detail)
        # conversion: needs a baseline and enough verified prospects
        try:
            target = float(self.env['ir.config_parameter'].sudo().get_param(CONVERSION_TARGET_PARAM) or 0.20)
        except ValueError:
            target = 0.20
        if not baseline_done or m['verified'] < 5:
            out['conversion'] = (None, env._(
                'Needs the two-week baseline to finish and at least 5 verified prospects '
                '(now %(v)s verified, %(q)s qualified).', v=m['verified'], q=m['qualified']))
        else:
            rate = m['qualified'] / m['verified']
            out['conversion'] = (100 * min(1.0, rate / target), env._(
                '%(q)s of %(v)s verified prospects qualified (%(r).0f%%, provisional target %(t).0f%%)',
                q=m['qualified'], v=m['verified'], r=100 * rate, t=100 * target))
        # service
        if profile == 'cx':
            if m['open_acts'] < 3:
                out['service'] = (None, env._('Fewer than 3 open activities to measure follow-up on.'))
            else:
                out['service'] = (100.0 * (m['open_acts'] - m['overdue_acts']) / m['open_acts'], env._(
                    '%(o)s of %(n)s open activities overdue', o=m['overdue_acts'], n=m['open_acts']))
        else:
            orders = env['faizy.order'].sudo().search([
                ('state', '=', 'completed'), ('date_completed', '>=', fields.Datetime.to_datetime(d_from)),
                ('date_completed', '<', fields.Datetime.to_datetime(d_to) + timedelta(days=1))])
            if len(orders) < 3:
                out['service'] = (None, env._('Fewer than 3 orders completed in the window.'))
            else:
                clean = orders.filtered(lambda o: o.evidence_state == 'approved' and not o.evidence_exception_reason)
                out['service'] = (100.0 * len(clean) / len(orders), env._(
                    '%(c)s of %(n)s completed orders had approved evidence without an exception',
                    c=len(clean), n=len(orders)))
        # media / partner readiness: first-pass approval of the role's checklists
        cks = env['faizy.checklist'].sudo().search([
            ('owner_id', '=', user.id), ('template_code', 'in', CHECKLIST_CODES[profile]),
            ('state', 'in', ('ready', 'approved'))])
        if len(cks) < 3:
            out['media'] = (None, env._('Fewer than 3 reviewed checklists (%s so far).', len(cks)))
        else:
            first = cks.filtered(lambda c: not c.reject_count)
            out['media'] = (100.0 * len(first) / len(cks), env._(
                '%(f)s of %(n)s checklists accepted without being sent back', f=len(first), n=len(cks)))
        # discipline: every open lead has a next action
        if m['open_leads'] < 3:
            out['discipline'] = (None, env._('Fewer than 3 open leads owned.'))
        else:
            out['discipline'] = (100.0 * m['open_leads_next'] / m['open_leads'], env._(
                '%(a)s of %(n)s open leads have a next action', a=m['open_leads_next'], n=m['open_leads']))
        return out

    @api.depends('user_id', 'date_from', 'date_to')
    def _compute_scorecard(self):
        for rec in self:
            if not rec.user_id or not rec.date_from or not rec.date_to:
                rec.profile = rec.status = rec.total_display = rec.report = False
                continue
            if rec.user_id != self.env.user and not self.env.user.has_group(G_MANAGER):
                raise AccessError(self.env._('You can only open your own scorecard.'))
            profile = rec._profile_of(rec.user_id)
            start = self.env['ir.config_parameter'].sudo().get_param(KPI_START_PARAM)
            today = fields.Date.context_today(rec)
            if not start:
                status, baseline_done = self.env._(
                    'Baseline not started. Scores are informational and are not used to judge anyone.'), False
            else:
                begin = fields.Date.to_date(start)
                if today < begin + timedelta(days=BASELINE_DAYS):
                    status, baseline_done = self.env._(
                        'Baseline period until %s. Scores are informational only.',
                        begin + timedelta(days=BASELINE_DAYS)), False
                else:
                    status, baseline_done = self.env._('Live.'), True
            comps = rec._components(rec.user_id, profile, rec.date_from, rec.date_to, baseline_done)
            weights = WEIGHTS[profile]
            avail = sum(w for key, _l, w in weights if comps[key][0] is not None)
            total = (sum(w * comps[key][0] for key, _l, w in weights if comps[key][0] is not None) / avail
                     if avail >= MIN_WEIGHT_FOR_TOTAL else None)
            rows = []
            for key, label, weight in weights:
                score, detail = comps[key]
                shown = self.env._('Insufficient data') if score is None else '%.0f' % score
                rows.append(
                    '<tr><td>%s</td><td class="text-end">%s%%</td><td class="text-end">%s</td><td>%s</td></tr>'
                    % (escape(label), weight, escape(shown), escape(detail)))
            rec.profile = profile
            rec.status = status
            rec.total_display = (self.env._('Insufficient data') if total is None else '%.0f / 100' % total)
            rec.report = Markup(
                '<table class="table table-sm"><thead><tr><th>Component</th><th class="text-end">Weight</th>'
                '<th class="text-end">Score</th><th>Measured from</th></tr></thead><tbody>%s</tbody></table>'
                '<p class="text-muted small">Every figure counts real records in the window. A percentage of '
                'checklist ticks never decides a score on its own.</p>' % ''.join(rows))
