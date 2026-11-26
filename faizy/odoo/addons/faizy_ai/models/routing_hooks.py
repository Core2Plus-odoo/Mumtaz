"""Where work enters and leaves, and the activity it creates or closes.

Routing table: FAIZY HQ05 §4.1 (R1–R8, R10) and, since 19.0.1.4.0, leads
(R13, §25): a CRM lead is a work item for its salesperson. Every hook is a
side effect: a routing failure is logged and never blocks the business action
itself.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models

from .routing import (
    LEAD_TYPES, T_APPLICATION, T_ASSIGN, T_COMPLETION_MSG, T_ESCALATION, T_FOLLOW_UP,
    T_INBOUND, T_LEAD_FOLLOW_UP, T_LEAD_QUALIFY, T_ORDER_DRAFT, T_PROOF, T_REPLY,
)

_logger = logging.getLogger(__name__)

ALL_ORDER_TYPES = (T_ASSIGN, T_FOLLOW_UP, T_PROOF, T_ESCALATION)


def _safe(fn, what, record):
    try:
        fn()
    except Exception:  # noqa: BLE001 - routing must never block the real action
        _logger.exception('FAIZY routing failed (%s) for %s', what, record)


class FaizyAIDraftRouting(models.Model):
    _inherit = 'faizy.ai.draft'

    DRAFT_ROUTES = {
        'customer_message': ('care', T_REPLY,
                             'Check Urdu, facts and hours, then approve or reject with a reason.'),
        'order_create': ('ops', T_ORDER_DRAFT,
                         'Confirm service, address and date, then approve or reject.'),
        'order_update': ('ops', T_ORDER_DRAFT,
                         'Confirm the change to the order, then approve or reject.'),
        'other': ('escalation', T_ESCALATION,
                  'Decide. Operations and care act after your decision.'),
    }

    def _route_new(self):
        Routing = self.env['faizy.routing']
        for draft in self:
            role, act, note = self.DRAFT_ROUTES.get(draft.kind, self.DRAFT_ROUTES['other'])
            _safe(lambda: Routing._route(draft, role, act, draft.name, self.env._(note)),
                  'new draft', draft)

    def _close_routes(self, feedback):
        Routing = self.env['faizy.routing']
        for draft in self:
            _safe(lambda: Routing._close(draft, (T_REPLY, T_ORDER_DRAFT, T_ESCALATION),
                                         feedback), 'close draft', draft)

    @api.model_create_multi
    def create(self, vals_list):
        drafts = super().create(vals_list)
        drafts.filtered(lambda d: d.state == 'draft')._route_new()
        return drafts

    def action_approve(self):
        res = super().action_approve()
        # A message waiting to be sent by hand is still care's open work.
        self.filtered(lambda d: d.state != 'to_send')._close_routes(
            self.env._('Approved by %s.', self.env.user.name))
        return res

    def action_reject(self):
        res = super().action_reject()
        self._close_routes(self.env._('Rejected by %s.', self.env.user.name))
        return res

    def action_mark_sent_manually(self):
        res = super().action_mark_sent_manually()
        self._close_routes(self.env._('Sent by hand by %s.', self.env.user.name))
        return res

    @api.model
    def _cron_stale_drafts(self):
        """Superseded by the escalation job; kept so the existing scheduled
        action keeps working. Routes any waiting draft that has no open
        activity yet (for drafts created before routing existed)."""
        waiting = self.search([('state', '=', 'draft')])
        waiting.filtered(lambda d: not d.activity_ids)._route_new()
        return len(waiting)


class FaizyAIInboundRouting(models.Model):
    _inherit = 'faizy.ai.inbound'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        Routing = self.env['faizy.routing']
        for rec in records.filtered(lambda r: r.state == 'new'):
            _safe(lambda: Routing._route(
                rec, 'care', T_INBOUND,
                self.env._('Reply needed: %s', rec.partner_id.display_name or rec.phone or rec.name),
                self.env._('Reply through a draft, or create an order draft for Operations.')),
                'inbound', rec)
        return records

    def action_handled(self):
        res = super().action_handled()
        for rec in self:
            _safe(lambda: self.env['faizy.routing']._close(rec, (T_INBOUND,), self.env._('Handled.')),
                  'close inbound', rec)
        return res

    def action_ignore(self):
        res = super().action_ignore()
        for rec in self:
            _safe(lambda: self.env['faizy.routing']._close(rec, (T_INBOUND,), self.env._('Ignored.')),
                  'close inbound', rec)
        return res


class FaizyOrderRouting(models.Model):
    _inherit = 'faizy.order'

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        Routing = self.env['faizy.routing']
        for order in orders.filtered(lambda o: not o.is_sample and o.state == 'pending'):
            _safe(lambda: Routing._route(
                order, 'ops', T_ASSIGN, self.env._('Assign: %s', order.display_name),
                self.env._('Pick a Faizy or vendor by city and service, then Assign.'),
                urgent=order.priority == '1'), 'new order', order)
        return orders

    def write(self, vals):
        res = super().write(vals)
        # faizy_pilot (when installed) records its review in evidence_state;
        # approval is the end of the "Review proof & receipt" work item.
        if vals.get('evidence_state') == 'approved':
            for order in self:
                _safe(lambda: self.env['faizy.routing']._close(
                    order, (T_PROOF,), self.env._('Evidence approved.')), 'evidence approved', order)
        if vals.get('proof_image'):
            Routing = self.env['faizy.routing']
            for order in self.filtered(lambda o: o.state == 'in_progress' and not o.is_sample):
                _safe(lambda: Routing._route(
                    order, 'ops', T_PROOF, self.env._('Review proof: %s', order.display_name),
                    self.env._('Check the photo and receipt match the order, then Complete.')),
                    'proof', order)
        return res

    def action_assign(self):
        res = super().action_assign()
        for order in self:
            _safe(lambda: self.env['faizy.routing']._close(order, (T_ASSIGN,), self.env._('Assigned.')),
                  'close assign', order)
        return res

    def action_start(self):
        res = super().action_start()
        for order in self:
            _safe(lambda: self.env['faizy.routing']._close(
                order, (T_ASSIGN, T_FOLLOW_UP), self.env._('Started.')), 'close start', order)
        return res

    def action_complete(self):
        res = super().action_complete()
        Routing = self.env['faizy.routing']
        for order in self.filtered(lambda o: o.state == 'completed'):
            _safe(lambda: Routing._close(order, (T_ASSIGN, T_FOLLOW_UP, T_PROOF),
                                         self.env._('Completed.')), 'close complete', order)
            if not order.is_sample:
                _safe(lambda: Routing._route(
                    order, 'care', T_COMPLETION_MSG,
                    self.env._('Completion message: %s', order.display_name),
                    self.env._('Send the customer the completion message with the proof, '
                      'through a reply draft or by hand.')), 'completion message', order)
        return res

    def action_cancel(self):
        res = super().action_cancel()
        for order in self:
            _safe(lambda: self.env['faizy.routing']._close(order, ALL_ORDER_TYPES,
                                                           self.env._('Order cancelled.')),
                  'close cancel', order)
        return res


class FaizyApplicationRouting(models.Model):
    _inherit = 'faizy.application'

    @api.model_create_multi
    def create(self, vals_list):
        apps = super().create(vals_list)
        Routing = self.env['faizy.routing']
        for app in apps.filtered(lambda a: not a.is_sample):
            _safe(lambda: Routing._route(
                app, 'ops', T_APPLICATION, self.env._('Review application: %s', app.display_name),
                self.env._('Verify ID and references, then approve or reject.')), 'application', app)
        return apps

    def action_approve(self):
        res = super().action_approve()
        for app in self:
            _safe(lambda: self.env['faizy.routing']._close(app, (T_APPLICATION,), self.env._('Approved.')),
                  'close application', app)
        return res

    def action_reject(self):
        res = super().action_reject()
        for app in self:
            _safe(lambda: self.env['faizy.routing']._close(app, (T_APPLICATION,), self.env._('Rejected.')),
                  'close application', app)
        return res


class CrmLeadRouting(models.Model):
    """R13: a lead is work for its salesperson (standard ``user_id``).

    Assignment is the standard Salesperson field, nothing else. A lead that
    arrives with no salesperson, or one owned by an AI agent or a portal user,
    goes to the customer-care role holder. The open FAIZY activities follow
    the salesperson when the lead is reassigned, so "my leads" and "my work
    today" always agree.
    """
    _inherit = 'crm.lead'

    @api.model
    def _faizy_eligible(self, user):
        return bool(user and user.active and not user.share
                    and not user.has_group('faizy_ai.group_ai_agent'))

    def _faizy_lead_owner(self, user):
        """The staff member who should hold this lead's work: the salesperson
        if it is a real staff account; otherwise the leader of the sales team
        that owns the lead's source (§26, one pipeline per executive); otherwise
        the customer-care role holder."""
        if self._faizy_eligible(user):
            return user
        team = self.env['crm.team'].browse()
        if self:
            team = self.env['crm.team']._faizy_team_for_source(self.faizy_lead_source)
            if not team and self.team_id.faizy_lead_sources:
                team = self.team_id
        if team and self._faizy_eligible(team.user_id):
            return team.user_id
        return self.env['faizy.routing']._role_user('care')

    @api.model
    def _faizy_first_stage(self):
        """The pipeline's first stage (Odoo 19 stages are global, no team)."""
        return self.env['crm.stage'].sudo().search([], order='sequence, id', limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        Routing = self.env['faizy.routing']
        for lead in leads:
            owner = lead._faizy_lead_owner(lead.user_id)
            vals = {}
            if owner != lead.user_id:
                vals['user_id'] = owner.id
            team = self.env['crm.team']._faizy_team_for_source(lead.faizy_lead_source)
            if team and lead.team_id != team and (not lead.team_id or owner == team.user_id):
                vals['team_id'] = team.id
            if vals:
                lead.sudo().write(vals)
            if lead.active and not lead.stage_id.is_won:
                _safe(lambda: Routing._route(
                    lead, 'care', T_LEAD_QUALIFY, self.env._('Qualify lead: %s', lead.name),
                    self.env._('Contact them, confirm what the family needs, then move the lead '
                               'to Qualified or mark it Lost.'),
                    user=owner), 'new lead', lead)
        return leads

    def write(self, vals):
        res = super().write(vals)
        Routing = self.env['faizy.routing']
        for lead in self:
            if 'user_id' in vals:
                _safe(lambda: lead._faizy_follow_owner(), 'lead owner', lead)
            if vals.get('active') is False:
                _safe(lambda: Routing._close(lead, LEAD_TYPES, self.env._('Lead lost.')),
                      'lead lost', lead)
            elif 'stage_id' in vals:
                if lead.stage_id.is_won:
                    _safe(lambda: Routing._close(lead, LEAD_TYPES, self.env._('Lead won.')),
                          'lead won', lead)
                elif lead.stage_id != lead._faizy_first_stage():
                    _safe(lambda: lead._faizy_qualified(), 'lead qualified', lead)
        return res

    def _faizy_follow_owner(self):
        self.ensure_one()
        owner = self._faizy_lead_owner(self.user_id)
        if owner != self.user_id:
            self.sudo().write({'user_id': owner.id})
            return
        types = [self.env.ref(x) for x in LEAD_TYPES]
        open_items = self.sudo().activity_ids.filtered(lambda a: a.activity_type_id in types)
        open_items.filtered(lambda a: a.user_id != owner).write({'user_id': owner.id})

    def _faizy_qualified(self):
        """Past the first stage: qualification is done, the follow-up starts,
        due tomorrow so today's list is not flooded by every qualified lead."""
        self.ensure_one()
        Routing = self.env['faizy.routing']
        Routing._close(self, (T_LEAD_QUALIFY,), self.env._('Qualified.'))
        Routing._route(
            self, 'care', T_LEAD_FOLLOW_UP, self.env._('Follow up lead: %s', self.name),
            self.env._('Agree the plan and the next step with the customer.'),
            user=self._faizy_lead_owner(self.user_id),
            deadline=fields.Date.context_today(self) + timedelta(days=1))
