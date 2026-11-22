"""Internal work routing for FAIZY staff (HQ05 §4, PR (b)).

Every piece of incoming work becomes a standard mail.activity on the real
record: the owner, deadline, what to do and a link to the record, all in the
person's Activities counter and their desk. No second task system.

Who gets what is read from three role holders (Settings → FAIZY → Work
routing), never hard-coded. If a role holder is empty or archived, routing
falls back to the role's group, then to the escalation owner, then to the
administrator, so work is never left without an owner.
"""
import logging
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models

from .utils import G_COMMS, G_MANAGER, G_OPS, within_hours

_logger = logging.getLogger(__name__)

ROLE_PARAMS = {
    'care': 'faizy_ai.care_user_id',
    'ops': 'faizy_ai.ops_user_id',
    'escalation': 'faizy_ai.escalation_user_id',
}
ROLE_GROUPS = {'care': G_COMMS, 'ops': G_OPS, 'escalation': G_MANAGER}

# Activity types created by this module (data/routing_data.xml).
T_REPLY = 'faizy_ai.act_approve_reply'
T_ORDER_DRAFT = 'faizy_ai.act_approve_order'
T_ASSIGN = 'faizy_ai.act_assign_faizy'
T_FOLLOW_UP = 'faizy_ai.act_follow_up_job'
T_PROOF = 'faizy_ai.act_review_proof'
T_COMPLETION_MSG = 'faizy_ai.act_completion_message'
T_INBOUND = 'faizy_ai.act_handle_inbound'
T_ESCALATION = 'faizy_ai.act_approve_escalation'
T_APPLICATION = 'faizy_ai.act_review_application'
T_LEAD_QUALIFY = 'faizy_ai.act_qualify_lead'
T_LEAD_FOLLOW_UP = 'faizy_ai.act_follow_up_lead'

# What "done" means for each kind of work item. Written once here, applied to
# the activity type's Default Note by _apply_checklists (first install and the
# 19.0.1.4.0 migration) and appended to every routed activity, so the person
# sees the steps on the item itself. Umer can edit a checklist in Settings →
# Activity Types; an edited note is never overwritten.
CHECKLISTS = {
    T_REPLY: (
        'Facts match the order and the knowledge notes',
        'Reads naturally in the customer\'s language; no stale phone number',
        'Inside 10:00–21:00 Karachi, or it will be held',
        'Approve, or reject with the reason the agent should learn from',
    ),
    T_ORDER_DRAFT: (
        'Service, family member and address are right',
        'Date and slot are possible for a Faizy in that city',
        'Plan allowance or a confirmed price covers it',
        'Approve, or reject with the reason',
    ),
    T_ASSIGN: (
        'Pick a Faizy or vendor active in the order\'s city and service',
        'Confirm the slot with them on WhatsApp',
        'Click Assign; the customer gets the confirmation from care',
    ),
    T_FOLLOW_UP: (
        'Call the Faizy: started, delayed or not coming?',
        'Reschedule the slot or reassign the job',
        'Tell care if the customer must be informed',
    ),
    T_PROOF: (
        'Photo shows the job done for the right family member',
        'Receipt matches the purchase value on the order',
        'Approve the evidence, or reject with what to redo',
    ),
    T_COMPLETION_MSG: (
        'Proof and receipt are approved',
        'Message names what was done and when',
        'Send through a reply draft, or by hand from the official phone, then mark sent',
    ),
    T_INBOUND: (
        'Identify the customer and the family member',
        'Reply through a draft, or create an order draft for Operations',
        'Mark handled; ignore only spam',
    ),
    T_ESCALATION: (
        'Read the item and the reason it was escalated',
        'Decide, and write the decision on the record',
        'Care or Operations act after your decision',
    ),
    T_APPLICATION: (
        'CNIC and photo are legible and match',
        'References called',
        'City and services set; approve or reject',
    ),
    T_LEAD_QUALIFY: (
        'Contact on WhatsApp inside 10:00–21:00 Karachi',
        'Confirm family city, expat country and the service they need',
        'Fill the Faizy tab on the lead',
        'Move to Qualified, or mark Lost with the reason',
    ),
    T_LEAD_FOLLOW_UP: (
        'Send the plan options that fit; no prices until approved',
        'Agree the next step and the date',
        'Won: create the customer and the first order; Lost: give the reason',
    ),
}
LEAD_TYPES = (T_LEAD_QUALIFY, T_LEAD_FOLLOW_UP)


def checklist_html(xmlid):
    items = CHECKLISTS.get(xmlid) or ()
    if not items:
        return ''
    return Markup('<p><b>Checklist</b></p><ul>%s</ul>') % Markup('').join(
        Markup('<li>%s</li>') % escape(item) for item in items)


class MailActivityType(models.Model):
    _inherit = 'mail.activity.type'

    faizy_route = fields.Boolean(
        string='FAIZY work item',
        help='Shown on the FAIZY desks and watched by the escalation job.')
    faizy_escalation_hours = fields.Float(
        string='Escalate after (hours)',
        help='Open this long without being done, the item escalates to the '
             'escalation owner. 0 means it never escalates.')
    faizy_urgent_escalation_hours = fields.Float(
        string='Escalate urgent after (hours)',
        help='Used instead of the normal window when the order is marked urgent.')


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    faizy_escalated = fields.Boolean(readonly=True, copy=False)
    faizy_urgent = fields.Boolean(readonly=True, copy=False)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    faizy_care_user_id = fields.Many2one(
        'res.users', string='Customer care approver',
        config_parameter=ROLE_PARAMS['care'],
        help='Gets reply approvals, inbound messages and completion messages (Mashood).')
    faizy_ops_user_id = fields.Many2one(
        'res.users', string='Operations approver',
        config_parameter=ROLE_PARAMS['ops'],
        help='Gets new orders, order drafts, overdue jobs, proof review and '
             'applications (Raza).')
    faizy_escalation_user_id = fields.Many2one(
        'res.users', string='Escalation owner',
        config_parameter=ROLE_PARAMS['escalation'],
        help='Gets escalations and anything overdue (Umer).')


class FaizyRouting(models.AbstractModel):
    _name = 'faizy.routing'
    _description = 'FAIZY internal work routing'

    # ------------------------------------------------------------------ owners
    @api.model
    def _role_user(self, role):
        """The active user who owns a role, with fallbacks. Never empty."""
        Users = self.env['res.users'].sudo()
        raw = self.env['ir.config_parameter'].sudo().get_param(ROLE_PARAMS[role])
        if raw and raw.isdigit():
            user = Users.browse(int(raw)).exists()
            if user and user.active and not user.share:
                return user
        group = self.env.ref(ROLE_GROUPS[role], raise_if_not_found=False)
        if group:
            members = group.sudo().all_user_ids.filtered(
                lambda u: u.active and not u.share and u.id != self.env.ref('base.user_root').id
            ).sorted('id')
            if members:
                return members[:1]
        if role != 'escalation':
            return self._role_user('escalation')
        return self.env.ref('base.user_admin')

    # ------------------------------------------------------------------ route / close
    @api.model
    def _route(self, record, role, act_xmlid, summary, note='', urgent=False,
               user=None, deadline=None):
        """Create one open activity of this type on the record, unless one is
        already open. Returns the activity (new or existing).

        ``user`` overrides the role holder (a lead follows its salesperson);
        ``deadline`` defaults to today. The type's checklist (Default Note) is
        appended to the note so the steps travel with the item."""
        record = record.sudo()
        act_type = self.env.ref(act_xmlid)
        existing = record.activity_ids.filtered(lambda a: a.activity_type_id == act_type)
        if existing:
            return existing[:1]
        user = user or self._role_user(role)
        body = Markup('<p>%s</p>') % note if note else Markup('')
        if act_type.default_note:
            body += Markup(act_type.default_note)
        activity = record.activity_schedule(
            act_xmlid,
            date_deadline=deadline or fields.Date.context_today(self),
            summary=summary,
            note=body,
            user_id=user.id,
        )
        if urgent:
            activity.faizy_urgent = True
        return activity

    @api.model
    def _close(self, record, act_xmlids, feedback=''):
        """Mark open activities of these types on the record as done."""
        types = [self.env.ref(x) for x in act_xmlids]
        todo = record.sudo().activity_ids.filtered(lambda a: a.activity_type_id in types)
        if todo:
            todo.action_feedback(feedback=feedback or self.env._('Done in FAIZY.'))

    @api.model
    def _apply_checklists(self):
        """Put each checklist on its activity type's Default Note, only where
        the note is still empty. Run at first install and by the 19.0.1.4.0
        migration; safe to run again."""
        done = 0
        for xmlid in CHECKLISTS:
            act_type = self.env.ref(xmlid, raise_if_not_found=False)
            if act_type and not act_type.default_note:
                act_type.sudo().default_note = checklist_html(xmlid)
                done += 1
        return done

    # ------------------------------------------------------------------ crons
    @api.model
    def _cron_escalate(self):
        """Escalate overdue FAIZY work to the escalation owner, once per item.

        Runs every 30 minutes but acts only inside FAIZY working hours, so
        nothing pages Umer at night; items that went overdue overnight escalate
        when the hours open. The window is measured from when the activity was
        created, in clock hours.
        """
        if not within_hours(self.env):
            return 0
        now = fields.Datetime.now()
        escalation_type = self.env.ref(T_ESCALATION)
        owner = self._role_user('escalation')
        candidates = self.env['mail.activity'].sudo().search([
            ('activity_type_id.faizy_route', '=', True),
            ('activity_type_id', '!=', escalation_type.id),
            ('faizy_escalated', '=', False),
        ])
        count = 0
        for activity in candidates:
            act_type = activity.activity_type_id
            hours = (act_type.faizy_urgent_escalation_hours
                     if activity.faizy_urgent and act_type.faizy_urgent_escalation_hours
                     else act_type.faizy_escalation_hours)
            if not hours or activity.create_date + timedelta(hours=hours) > now:
                continue
            record = self.env[activity.res_model].sudo().browse(activity.res_id).exists()
            activity.faizy_escalated = True
            if not record:
                continue
            reason = self.env._(
                '%(type)s for %(user)s open longer than %(hours)s h: %(summary)s',
                type=act_type.name, user=activity.user_id.name, hours=hours,
                summary=activity.summary or '')
            if owner != activity.user_id:
                record.activity_schedule(
                    T_ESCALATION, date_deadline=fields.Date.context_today(self),
                    summary=self.env._('Escalated: %s', activity.summary or act_type.name),
                    note=reason, user_id=owner.id)
            record.message_post(
                body=self.env._('Escalated to %(owner)s: %(reason)s',
                                owner=owner.name, reason=reason),
                message_type='comment', subtype_xmlid='mail.mt_note')
            count += 1
        return count

    @api.model
    def _cron_overdue_jobs(self):
        """R5: a job whose slot passed more than an hour ago and has not started."""
        limit = fields.Datetime.now() - timedelta(hours=1)
        late = self.env['faizy.order'].sudo().search([
            ('state', 'in', ('assigned', 'scheduled')),
            ('scheduled_date', '!=', False),
            ('scheduled_date', '<', limit),
            ('is_sample', '=', False),
        ])
        for order in late:
            self._route(order, 'ops', T_FOLLOW_UP,
                        self.env._('Not started: %s', order.display_name),
                        self.env._('The slot has passed. Call the Faizy and start the job '
                                   'or reschedule it.'),
                        urgent=order.priority == '1')
        return len(late)

    @api.model
    def _summary_for(self, user):
        Activity = self.env['mail.activity'].sudo()
        mine = Activity.search([('user_id', '=', user.id),
                                ('activity_type_id.faizy_route', '=', True)])
        today = fields.Date.context_today(self)
        overdue = mine.filtered(lambda a: a.date_deadline < today or a.faizy_escalated)
        oldest = 0.0
        if mine:
            first = min(mine.mapped('create_date'))
            oldest = round((fields.Datetime.now() - first).total_seconds() / 3600.0, 1)
        lines = [
            self.env._('Waiting for you: %s', len(mine)),
            self.env._('Overdue or escalated: %s', len(overdue)),
            self.env._('Oldest waiting: %s h', oldest),
        ]
        leads = self.env['crm.lead'].sudo().search_count([
            ('user_id', '=', user.id),
            ('activity_ids.activity_type_id', 'in', [self.env.ref(x).id for x in LEAD_TYPES])])
        if leads:
            lines.append(self.env._('Leads waiting on you: %s', leads))
        if user == self._role_user('ops'):
            unassigned = self.env['faizy.order'].sudo().search_count([
                ('state', '=', 'pending'), ('worker_id', '=', False),
                ('vendor_id', '=', False), ('is_sample', '=', False)])
            lines.append(self.env._('Unassigned orders: %s', unassigned))
        if user == self._role_user('care'):
            lines.append(self.env._('Replies to approve: %s', self.env['faizy.ai.draft'].sudo().search_count(
                [('state', '=', 'draft'), ('kind', '=', 'customer_message')])))
            lines.append(self.env._('To send by hand: %s', self.env['faizy.ai.draft'].sudo().search_count(
                [('state', '=', 'to_send')])))
        return lines

    @api.model
    def _cron_morning_summary(self):
        """One in-app message per role holder each morning. Never email or WhatsApp:
        message_notify lands in the Odoo Inbox for users set to "Handle in Odoo"."""
        users = self.env['res.users']
        for role in ('care', 'ops', 'escalation'):
            users |= self._role_user(role)
        for user in users:
            lines = self._summary_for(user)
            body = Markup('<p>%s</p><ul>%s</ul>') % (
                self.env._('Good morning, %s. Today in FAIZY:', user.name),
                Markup('').join(Markup('<li>%s</li>') % escape(line) for line in lines))
            self.env['mail.thread'].sudo().message_notify(
                partner_ids=user.partner_id.ids,
                subject=self.env._('FAIZY: your work today'),
                body=body,
                email_layout_xmlid='mail.mail_notification_light',
            )
        return len(users)
