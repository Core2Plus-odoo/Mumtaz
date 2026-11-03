import json

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .utils import (
    G_COMMS, G_OPS, can_approve, has_stale_number, is_approver, normalize_phone,
    within_hours,
)

# What an AI agent may touch on a draft it owns while the draft is still a draft.
AI_DRAFT_FIELDS = {'subject', 'body', 'payload', 'partner_id', 'order_id', 'kind', 'agent_id'}

# Order fields an approved order_update may write, and actions it may call.
ORDER_WRITE_FIELDS = {'worker_id', 'vendor_id', 'scheduled_date', 'priority', 'description'}
ORDER_ACTIONS = {'action_confirm', 'action_assign', 'action_start'}
# Order create: optional fields copied from the payload.
ORDER_CREATE_FIELDS = {'scheduled_date', 'family_member_id', 'priority', 'street', 'privacy_mode'}


class FaizyAIDraft(models.Model):
    _name = 'faizy.ai.draft'
    _description = 'Faizy AI draft (needs approval)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    subject = fields.Char(required=True, tracking=True)
    agent_id = fields.Many2one('faizy.ai.agent', string='Drafted by', tracking=True,
                               default=lambda self: self._default_agent())
    kind = fields.Selection([
        ('customer_message', 'Customer WhatsApp message'),
        ('order_create', 'New order'),
        ('order_update', 'Order update'),
        ('other', 'Other (done by hand after approval)'),
    ], required=True, default='customer_message', tracking=True)
    body = fields.Text(help='Message text for customer messages; description for new orders.')
    payload = fields.Text(
        default='{}',
        help='JSON. customer_message: phone, message_type, template_name, lang. '
             'order_create: service_id, title, city, scheduled_date. '
             'order_update: write {worker_id, vendor_id, scheduled_date}, action.')
    partner_id = fields.Many2one('res.partner', string='Customer', tracking=True)
    order_id = fields.Many2one('faizy.order', string='Order')
    result_order_id = fields.Many2one('faizy.order', readonly=True, copy=False)
    message_ref_id = fields.Many2one('faizy.whatsapp.message', string='Queued message',
                                     readonly=True, copy=False)

    state = fields.Selection([
        ('draft', 'Waiting for approval'),
        ('approved', 'Approved, held until working hours'),
        ('executed', 'Done'),
        ('rejected', 'Rejected'),
    ], default='draft', required=True, tracking=True, index=True)
    approver_id = fields.Many2one('res.users', readonly=True, copy=False, tracking=True)
    approved_date = fields.Datetime(readonly=True, copy=False)
    executed_date = fields.Datetime(readonly=True, copy=False)
    reject_reason = fields.Text(copy=False)
    approver_group = fields.Char(compute='_compute_approver_group')

    # ------------------------------------------------------------------ helpers
    @api.model
    def _default_agent(self):
        return self.env['faizy.ai.agent'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)

    @api.depends('subject', 'kind')
    def _compute_name(self):
        labels = dict(self._fields['kind'].selection)
        for draft in self:
            draft.name = '[%s] %s' % (labels.get(draft.kind, ''), draft.subject or '')

    @api.depends('kind')
    def _compute_approver_group(self):
        for draft in self:
            draft.approver_group = {
                'customer_message': 'Customer communications (Mashood)',
                'order_create': 'Faizy / Operations (Raza)',
                'order_update': 'Faizy / Operations (Raza)',
                'other': 'Faizy / Manager (Umer)',
            }.get(draft.kind, '')

    def _payload_dict(self):
        self.ensure_one()
        try:
            data = json.loads(self.payload or '{}')
        except ValueError as exc:
            raise ValidationError(_('Payload must be valid JSON: %s', exc)) from exc
        if not isinstance(data, dict):
            raise ValidationError(_('Payload must be a JSON object.'))
        return data

    @api.constrains('payload', 'body', 'kind')
    def _check_content(self):
        for draft in self:
            data = draft._payload_dict()
            stale = has_stale_number((draft.body or '') + json.dumps(data))
            if stale:
                raise ValidationError(_(
                    'Outdated phone number in draft (%s). The only WhatsApp number is '
                    '+92 334 2726048.', ', '.join(stale)))
            if draft.kind == 'order_update':
                action = data.get('action')
                if action and action not in ORDER_ACTIONS:
                    raise ValidationError(_(
                        'Action %s is not allowed in a draft. Completing or cancelling an '
                        'order is done by a person.', action))
                bad = set(data.get('write', {})) - ORDER_WRITE_FIELDS
                if bad:
                    raise ValidationError(_('Fields not allowed in a draft: %s',
                                            ', '.join(sorted(bad))))

    # ------------------------------------------------------------------ ORM guards
    @api.model_create_multi
    def create(self, vals_list):
        if not is_approver(self.env):
            for vals in vals_list:
                vals['state'] = 'draft'
        return super().create(vals_list)

    def write(self, vals):
        if not is_approver(self.env):
            blocked = set(vals) - AI_DRAFT_FIELDS
            if blocked or any(d.state != 'draft' for d in self):
                raise AccessError(_(
                    'AI agents can only edit the content of their own drafts that are still '
                    'waiting for approval.'))
        return super().write(vals)

    # ------------------------------------------------------------------ approval
    def _check_approver(self):
        self.ensure_one()
        group = {'customer_message': G_COMMS, 'order_create': G_OPS,
                 'order_update': G_OPS}.get(self.kind)
        if group:
            ok = can_approve(self.env, group)
        else:
            ok = is_approver(self.env)
        if not ok:
            raise AccessError(_('You are not an approver for this kind of draft (%s).',
                                self.approver_group))

    def action_approve(self):
        for draft in self:
            if draft.state != 'draft':
                raise UserError(_('Only drafts waiting for approval can be approved.'))
            draft._check_approver()
            draft.write({'state': 'approved', 'approver_id': self.env.uid,
                         'approved_date': fields.Datetime.now()})
            draft._execute_if_possible()

    def action_reject(self):
        for draft in self:
            if draft.state not in ('draft', 'approved'):
                raise UserError(_('Only open drafts can be rejected.'))
            draft._check_approver()
            if not draft.reject_reason:
                raise UserError(_('Write the reason in "Reject reason" first.'))
            draft.write({'state': 'rejected', 'approver_id': self.env.uid})

    def _execute_if_possible(self):
        self.ensure_one()
        if self.kind == 'customer_message' and not within_hours(self.env):
            self.message_post(body=_(
                'Approved. The customer message is held until Faizy working hours '
                '(10am to 9pm Karachi).'))
            return False
        getattr(self, '_execute_%s' % self.kind)()
        self.write({'state': 'executed', 'executed_date': fields.Datetime.now()})
        return True

    # ------------------------------------------------------------------ executors
    def _execute_customer_message(self):
        self.ensure_one()
        data = self._payload_dict()
        if not self.body or not self.body.strip():
            raise UserError(_('The message text is empty.'))
        if not self.partner_id:
            raise UserError(_('Choose the customer first.'))
        raw_phone = data.get('phone') or self.partner_id.phone
        digits = normalize_phone(raw_phone)
        if len(digits) < 10:
            raise UserError(_('No valid WhatsApp number for %s.', self.partner_id.display_name))
        Message = self.env['faizy.whatsapp.message'].sudo()
        types = dict(Message._fields['message_type']._description_selection(self.env))
        message_type = data.get('message_type', 'generic')
        if message_type not in types or message_type == 'otp':
            raise UserError(_('Message type %s is not allowed in a draft.', message_type))
        vals = {
            'phone': '+' + digits,
            'body': self.body,
            'message_type': message_type,
            'state': 'queued',   # faizy_core's cron sends queued messages
            'partner_id': self.partner_id.id,
            'order_id': (self.order_id or self.env['faizy.order']).id,
        }
        if data.get('template_name'):
            vals['template_name'] = data['template_name']
        if data.get('lang') in ('en', 'ur'):
            vals['lang'] = data['lang']
        message = Message.create(vals)
        self.message_ref_id = message
        self.message_post(body=_('Queued WhatsApp message %s for sending.', message.id))

    def _execute_order_create(self):
        self.ensure_one()
        data = self._payload_dict()
        if not self.partner_id:
            raise UserError(_('Choose the customer first.'))
        if not data.get('service_id'):
            raise UserError(_('The draft needs a service_id.'))
        vals = {
            'partner_id': self.partner_id.id,
            'service_id': int(data['service_id']),
            'title': data.get('title') or self.subject,
            'city': data.get('city') or 'Karachi',
            'description': self.body,
        }
        for key in ORDER_CREATE_FIELDS:
            if data.get(key):
                vals[key] = data[key]
        order = self.env['faizy.order'].sudo().create(vals)
        self.result_order_id = order
        self.message_post(body=_('Created order %s.', order.display_name))

    def _execute_order_update(self):
        self.ensure_one()
        data = self._payload_dict()
        order = self.order_id.sudo()
        if not order:
            raise UserError(_('Choose the order first.'))
        write_vals = {k: v for k, v in data.get('write', {}).items() if k in ORDER_WRITE_FIELDS}
        if write_vals:
            order.write(write_vals)
        action = data.get('action')
        if action:
            getattr(order, action)()
        self.result_order_id = order
        self.message_post(body=_('Updated order %s.', order.display_name))

    def _execute_other(self):
        self.message_post(body=_('Approved. The approver does this part by hand.'))

    # ------------------------------------------------------------------ crons / digest
    @api.model
    def _cron_release_held(self):
        """Release approved customer messages once working hours open."""
        if not within_hours(self.env):
            return 0
        held = self.search([('state', '=', 'approved'), ('kind', '=', 'customer_message')])
        for draft in held:
            draft._execute_if_possible()
        return len(held)

    @api.model
    def _cron_stale_drafts(self):
        """Nudge approvers about drafts waiting more than a day. Internal only."""
        limit = fields.Datetime.now() - relativedelta(days=1)
        stale = self.search([('state', '=', 'draft'), ('create_date', '<', limit)])
        for draft in stale:
            group_xmlid = G_COMMS if draft.kind == 'customer_message' else G_OPS
            group = self.env.ref(group_xmlid, raise_if_not_found=False)
            summary = _('Draft waiting over a day: %s', draft.subject)
            if draft.activity_ids.filtered(lambda a: a.summary == summary):
                continue
            for user in (group.sudo().user_ids[:2] if group else []):
                draft.activity_schedule('mail.mail_activity_data_todo', user_id=user.id,
                                        summary=summary)
        return len(stale)

    @api.model
    def get_digest(self):
        """Read-only snapshot for the Insights and Chief of Staff agents."""
        now = fields.Datetime.now()
        Order = self.env['faizy.order']
        Msg = self.env['faizy.whatsapp.message']
        open_states = ('pending', 'assigned', 'scheduled', 'in_progress')
        open_dom = [('state', 'in', open_states)]
        pending = self.search([('state', '=', 'draft')], order='create_date asc')
        oldest = 0.0
        if pending:
            oldest = round((now - pending[0].create_date).total_seconds() / 3600.0, 1)
        return {
            'generated_at': fields.Datetime.to_string(now),
            'open_orders': Order.search_count(open_dom),
            'unassigned_orders': Order.search_count(
                [('state', '=', 'pending'), ('worker_id', '=', False), ('vendor_id', '=', False)]),
            'overdue_orders': Order.search_count(
                open_dom + [('scheduled_date', '!=', False), ('scheduled_date', '<', now)]),
            'completed_without_proof': Order.search_count(
                [('state', '=', 'completed'), ('proof_image', '=', False)]),
            'completed_last_7_days': Order.search_count(
                [('state', '=', 'completed'), ('write_date', '>=', now - relativedelta(days=7))]),
            'failed_whatsapp_messages': Msg.search_count([('state', '=', 'failed')]),
            'queued_whatsapp_messages': Msg.search_count([('state', '=', 'queued')]),
            'unhandled_inbound': self.env['faizy.ai.inbound'].search_count(
                [('state', '=', 'new')]),
            'pending_drafts': len(pending),
            'held_drafts': self.search_count([('state', '=', 'approved')]),
            'oldest_pending_draft_hours': oldest,
            'subscriptions_past_due': self.env['faizy.subscription'].search_count(
                [('state', '=', 'past_due')]),
            'worker_applicants': self.env['faizy.worker'].search_count(
                [('state', '=', 'applicant')]),
            'bridge_requests_pending': self.env['faizy.bridge.request'].search_count(
                [('state', '=', 'pending')]),
        }
