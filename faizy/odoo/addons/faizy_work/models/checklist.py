from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

G_MANAGER = 'faizy_core.group_faizy_manager'
G_OPS = 'faizy_core.group_faizy_ops'

EVIDENCE_MODELS = [
    ('crm.lead', 'CRM lead'),
    ('faizy.order', 'FAIZY order'),
    ('faizy.ai.draft', 'AI draft'),
    ('res.partner', 'Contact / vendor'),
    ('ir.attachment', 'Attachment'),
    ('account.move', 'Invoice / bill'),
]


class FaizyChecklist(models.Model):
    _name = 'faizy.checklist'
    _description = 'FAIZY checklist'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(compute='_compute_name', store=True)
    template_id = fields.Many2one('faizy.checklist.template', required=True, readonly=True, ondelete='restrict')
    template_code = fields.Char(related='template_id.code', store=True)
    template_version = fields.Integer(related='template_id.version', store=True)
    kind = fields.Selection(related='template_id.kind', store=True)
    res_model = fields.Char(index=True, readonly=True)
    res_id = fields.Many2oneReference(model_field='res_model', index=True, readonly=True)
    record_name = fields.Char(compute='_compute_record_name')
    owner_id = fields.Many2one(
        'res.users', string='Accountable owner', required=True, tracking=True,
        default=lambda self: self.env.user, index=True)
    due_date = fields.Date(tracking=True)
    period_key = fields.Char(readonly=True, help='Daily or weekly checklists: the period they cover.')
    scope_key = fields.Char(readonly=True, copy=False, index=True)
    state = fields.Selection([
        ('draft', 'Not started'),
        ('in_progress', 'In progress'),
        ('blocked', 'Blocked'),
        ('ready', 'Ready for review'),
        ('approved', 'Approved'),
    ], default='draft', required=True, tracking=True, index=True)
    blocked_reason = fields.Text(tracking=True)
    reject_count = fields.Integer(readonly=True, copy=False)
    reviewer_id = fields.Many2one('res.users', readonly=True, copy=False)
    reviewed_on = fields.Datetime(readonly=True, copy=False)
    ready_on = fields.Datetime(readonly=True, copy=False)
    line_ids = fields.One2many('faizy.checklist.line', 'checklist_id', copy=False)
    mandatory_total = fields.Integer(compute='_compute_progress')
    mandatory_done = fields.Integer(compute='_compute_progress')
    progress = fields.Float(compute='_compute_progress', string='Progress %')
    missing_summary = fields.Char(compute='_compute_progress')
    can_review = fields.Boolean(compute='_compute_can_review')

    _scope_uniq = models.Constraint(
        'unique(scope_key)',
        'This checklist already exists for that record or period. Open the existing one.')

    # ── computes ─────────────────────────────────────────────────────────
    @api.depends('template_id', 'res_model', 'res_id', 'period_key')
    def _compute_name(self):
        for rec in self:
            rec.name = ' · '.join(filter(None, [
                rec.template_id.name, rec.period_key or '']))

    def _compute_record_name(self):
        for rec in self:
            name = False
            if rec.res_model and rec.res_id and rec.res_model in self.env:
                target = self.env[rec.res_model].sudo().browse(rec.res_id).exists()
                name = target.display_name if target else False
            rec.record_name = name

    @api.depends('line_ids.state', 'line_ids.mandatory', 'line_ids.applicable')
    def _compute_progress(self):
        for rec in self:
            req = rec.line_ids.filtered(lambda ln: ln.mandatory and ln.applicable)
            done = req.filtered(lambda ln: ln.state == 'done')
            rec.mandatory_total = len(req)
            rec.mandatory_done = len(done)
            rec.progress = (100.0 * len(done) / len(req)) if req else 100.0
            todo = (req - done).mapped('name')
            rec.missing_summary = ('; '.join(todo[:3]) + ('…' if len(todo) > 3 else '')) if todo else ''

    @api.depends_context('uid')
    @api.depends('owner_id')
    def _compute_can_review(self):
        manager = self.env.user.has_group(G_MANAGER)
        for rec in self:
            rec.can_review = manager and rec.owner_id != self.env.user

    # ── write protection: state moves only through the actions ──────────
    def _w(self, vals):
        return self.with_context(faizy_ck_internal=True).write(vals)

    def write(self, vals):
        if not self.env.su and not self.env.context.get('faizy_ck_internal'):
            free = {k for k in vals if k.startswith(('message_', 'activity_'))}
            allowed = {'due_date'} | free
            if self.env.user.has_group(G_MANAGER):
                allowed.add('owner_id')
            if set(vals) - allowed:
                raise AccessError(self.env._(
                    'A checklist changes state only through its buttons: Ready for Review, '
                    'Approve, Send back, Block or Reopen.'))
        return super().write(vals)

    # ── creation / idempotence ───────────────────────────────────────────
    @api.model
    def _make_scope_key(self, vals):
        return ':'.join([
            str(vals.get('template_code') or ''), str(vals.get('res_model') or ''),
            str(vals.get('res_id') or 0), str(vals.get('owner_id') or 0),
            str(vals.get('period_key') or '')])

    @api.model
    def _start(self, template, record=None, owner=None, period_key=None, due_date=None):
        """Create the checklist for this template and record or period, or
        return the one that already exists. Safe to call repeatedly: this is
        what makes the recurring jobs idempotent."""
        owner = owner or self.env.user
        vals = {
            'template_code': template.code,
            'res_model': record._name if record else False,
            'res_id': record.id if record else False,
            'owner_id': owner.id,
            'period_key': period_key or False,
        }
        key = self._make_scope_key(vals)
        if record is not None and record:
            # One checklist per template and record, whoever the owner is.
            key = self._make_scope_key(dict(vals, owner_id=0))
        existing = self.sudo().search([('scope_key', '=', key)], limit=1)
        if existing:
            return existing
        checklist = self.sudo().create({
            'template_id': template.id,
            'res_model': vals['res_model'],
            'res_id': vals['res_id'],
            'owner_id': owner.id,
            'period_key': vals['period_key'],
            'due_date': due_date,
            'scope_key': key,
            'line_ids': [(0, 0, {
                'sequence': it.sequence, 'name': it.name, 'sop': it.sop,
                'mandatory': it.mandatory, 'condition': it.condition,
                'evidence_required': it.evidence_required, 'restricted': it.restricted,
                'gate': it.gate, 'auto_key': it.auto_key,
            }) for it in template.item_ids],
        })
        checklist._autofill()
        return checklist.with_env(self.env)

    # ── rules ────────────────────────────────────────────────────────────
    def _check_open(self):
        for rec in self:
            if rec.state == 'approved':
                raise UserError(self.env._('This checklist is approved. Reopen it (with a reason) to change it.'))

    def _gate_missing(self, gate):
        """Names of mandatory, applicable items behind this gate that are not done."""
        self.ensure_one()
        return self.line_ids.filtered(
            lambda ln: ln.gate == gate and ln.mandatory and ln.applicable and ln.state != 'done'
        ).mapped('name')

    # ── autofill from existing records ───────────────────────────────────
    def _autofill(self):
        today = fields.Date.context_today(self)
        for rec in self:
            user = rec.owner_id
            Act = self.env['mail.activity'].sudo()
            for line in rec.line_ids.filtered(lambda ln: ln.auto_key and ln.state in ('todo', 'done')):
                key, note, ok = line.auto_key, False, None
                if key == 'overdue':
                    n = Act.search_count([('user_id', '=', user.id), ('date_deadline', '<', today)])
                    note, ok = self.env._('%s overdue activities', n), n == 0
                elif key == 'due_today':
                    n = Act.search_count([('user_id', '=', user.id), ('date_deadline', '=', today)])
                    note = self.env._('%s activities due today', n)
                elif key == 'leads_no_next':
                    leads = self.env['crm.lead'].sudo().search([
                        ('user_id', '=', user.id), ('active', '=', True),
                        ('probability', '<', 100)])
                    n = len(leads.filtered(lambda ln: not ln.activity_ids))
                    note, ok = self.env._('%s open leads without a next action', n), n == 0
                elif key == 'orders_open':
                    n = self.env['faizy.order'].sudo().search_count(
                        [('state', 'in', ('assigned', 'in_progress'))])
                    note = self.env._('%s orders assigned or in progress', n)
                elif key == 'evidence_pending':
                    n = self.env['faizy.order'].sudo().search_count([('evidence_state', '=', 'submitted')])
                    note = self.env._('%s orders with evidence waiting for review', n)
                elif key == 'drafts_waiting':
                    n = self.env['faizy.ai.draft'].sudo().search_count([('state', '=', 'draft')])
                    note = self.env._('%s drafts waiting for approval', n)
                elif key == 'blocked':
                    n = self.sudo().search_count([('owner_id', '=', user.id), ('state', '=', 'blocked')])
                    note = self.env._('%s blocked checklists', n)
                vals = {'auto_note': note}
                if ok is True and line.state == 'todo':
                    vals.update(state='done', done_by=False, done_on=fields.Datetime.now(), auto_done=True)
                elif ok is False and line.state == 'done' and line.auto_done:
                    vals.update(state='todo', done_on=False, auto_done=False)
                line.with_context(faizy_line_internal=True).write(vals)
            if rec.state == 'draft' and rec.line_ids.filtered(lambda ln: ln.state == 'done'):
                rec._w({'state': 'in_progress'})

    def action_refresh(self):
        self._check_open()
        self._autofill()
        return True

    # ── workflow ─────────────────────────────────────────────────────────
    def action_ready(self):
        for rec in self:
            rec._check_open()
            rec._autofill()
            missing = rec.line_ids.filtered(lambda ln: ln.mandatory and ln.applicable and ln.state != 'done')
            if missing:
                raise UserError(self.env._(
                    'Not ready: %s', '; '.join(missing.mapped('name'))))
            rec._w({'state': 'ready', 'ready_on': fields.Datetime.now()})
            rec.message_post(body=self.env._('%s marked this checklist Ready for Review.', self.env.user.name))
            escalation = self.env['faizy.routing']._role_user('escalation')
            summary = self.env._('Review checklist: %s', rec.name)
            if not rec.activity_ids.filtered(lambda a: a.summary == summary):
                rec.sudo().activity_schedule(
                    'mail.mail_activity_data_todo', summary=summary,
                    date_deadline=fields.Date.context_today(self), user_id=escalation.id,
                    note=self.env._('Opened from the checklist; approve or send back with a reason.'))
        return True

    def action_approve(self):
        if not self.env.user.has_group(G_MANAGER):
            raise AccessError(self.env._('Only a Faizy Manager approves a checklist.'))
        for rec in self:
            if rec.owner_id == self.env.user:
                raise UserError(self.env._('You cannot approve your own checklist.'))
            if rec.state != 'ready':
                raise UserError(self.env._('Only a checklist that is Ready for Review can be approved.'))
            rec._w({'state': 'approved', 'reviewer_id': self.env.user.id,
                    'reviewed_on': fields.Datetime.now()})
            rec.activity_ids.sudo().action_feedback(
                feedback=self.env._('Approved by %s.', self.env.user.name))
            rec.message_post(body=self.env._('Approved by %s.', self.env.user.name))
        return True

    def _transition_with_reason(self, action, reason):
        reason = (reason or '').strip()
        if not reason:
            raise UserError(self.env._('A reason is required.'))
        for rec in self:
            if action == 'reject':
                if not self.env.user.has_group(G_MANAGER) or rec.owner_id == self.env.user:
                    raise AccessError(self.env._('Only a Faizy Manager, not the owner, can send a checklist back.'))
                rec._w({'state': 'in_progress', 'reject_count': rec.reject_count + 1})
                rec.activity_ids.sudo().action_feedback(feedback=self.env._('Sent back: %s', reason))
                rec.message_post(body=self.env._('Sent back by %(u)s: %(r)s', u=self.env.user.name, r=reason))
            elif action == 'reopen':
                if rec.state not in ('approved', 'ready'):
                    raise UserError(self.env._('Only an approved or ready checklist needs reopening.'))
                rec._w({'state': 'in_progress'})
                rec.message_post(body=self.env._('Reopened by %(u)s: %(r)s', u=self.env.user.name, r=reason))
            elif action == 'block':
                rec._check_open()
                rec._w({'state': 'blocked', 'blocked_reason': reason})
                rec.message_post(body=self.env._('Blocked by %(u)s: %(r)s', u=self.env.user.name, r=reason))
                escalation = self.env['faizy.routing']._role_user('escalation')
                rec.sudo().activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=self.env._('Blocked: %s', rec.name),
                    date_deadline=fields.Date.context_today(self), user_id=escalation.id,
                    note=reason)
            elif action == 'unblock':
                if rec.state != 'blocked':
                    raise UserError(self.env._('This checklist is not blocked.'))
                rec._w({'state': 'in_progress', 'blocked_reason': False})
                rec.activity_ids.sudo().action_feedback(feedback=self.env._('Unblocked: %s', reason))
                rec.message_post(body=self.env._('Unblocked by %(u)s: %(r)s', u=self.env.user.name, r=reason))
        return True

    def action_open_reason_wizard(self):
        return {
            'type': 'ir.actions.act_window', 'res_model': 'faizy.checklist.reason',
            'view_mode': 'form', 'target': 'new',
            'context': {'default_checklist_id': self.id,
                        'default_action': self.env.context.get('reason_action', 'block')},
        }

    def action_open_record(self):
        self.ensure_one()
        if not (self.res_model and self.res_id):
            return False
        return {'type': 'ir.actions.act_window', 'res_model': self.res_model,
                'res_id': self.res_id, 'view_mode': 'form'}

    # ── periodic ─────────────────────────────────────────────────────────
    @api.model
    def _cron_periodic(self):
        """Create today's start/end checklists and this week's review for every
        person assigned to a recurring template. Idempotent: running it twice a
        day, or after a restart, creates nothing new."""
        today = fields.Date.context_today(self)
        week = today.isocalendar()
        keys = {
            'daily_start': today.isoformat(), 'daily_end': today.isoformat(),
            'weekly': f'{week[0]}-W{week[1]:02d}',
        }
        templates = self.env['faizy.checklist.template'].sudo().search([
            ('state', '=', 'released'), ('kind', 'in', list(keys))])
        latest = {}
        for tpl in templates.sorted('version'):
            latest[tpl.code] = tpl
        made = 0
        for tpl in latest.values():
            for user in tpl.user_ids.filtered(lambda u: u.active and not u.share):
                before = self.sudo().search_count([('template_code', '=', tpl.code), ('owner_id', '=', user.id)])
                self._start(tpl, owner=user, period_key=keys[tpl.kind], due_date=today)
                made += self.sudo().search_count(
                    [('template_code', '=', tpl.code), ('owner_id', '=', user.id)]) - before
        return made


class FaizyChecklistLine(models.Model):
    _name = 'faizy.checklist.line'
    _description = 'FAIZY checklist line'
    _order = 'sequence, id'

    checklist_id = fields.Many2one('faizy.checklist', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, string='Step', readonly=True)
    sop = fields.Text(string='How to do it', readonly=True)
    mandatory = fields.Boolean(readonly=True)
    condition = fields.Selection([
        ('always', 'Always'), ('org', 'Organisation prospect'),
        ('individual', 'Individual prospect'), ('purchase', 'Order involves a purchase')],
        default='always', readonly=True)
    applicable = fields.Boolean(compute='_compute_applicable')
    evidence_required = fields.Boolean(readonly=True)
    restricted = fields.Boolean(readonly=True)
    gate = fields.Char(readonly=True)
    auto_key = fields.Char(readonly=True)
    auto_note = fields.Char(readonly=True)
    auto_done = fields.Boolean(readonly=True)
    state = fields.Selection([
        ('todo', 'To do'), ('done', 'Done'), ('blocked', 'Blocked'),
    ], default='todo', required=True)
    done_by = fields.Many2one('res.users', readonly=True)
    done_on = fields.Datetime(readonly=True)
    note = fields.Char(string='Note')
    evidence_ref = fields.Reference(EVIDENCE_MODELS, string='Evidence record')
    evidence_url = fields.Char(string='Evidence link')
    owner_id = fields.Many2one(related='checklist_id.owner_id')

    # ── computes ─────────────────────────────────────────────────────────
    def _compute_applicable(self):
        for line in self:
            line.applicable = line._condition_met()

    def _condition_met(self):
        self.ensure_one()
        cond = self.condition or 'always'
        if cond == 'always':
            return True
        ck = self.checklist_id
        if not (ck.res_model and ck.res_id and ck.res_model in self.env):
            return True
        rec = self.env[ck.res_model].sudo().browse(ck.res_id).exists()
        if not rec:
            return True
        if cond in ('org', 'individual'):
            kind = getattr(rec, 'faizy_prospect_kind', False) or 'organisation'
            return kind == ('organisation' if cond == 'org' else 'individual')
        if cond == 'purchase':
            return (getattr(rec, 'purchase_value', 0) or 0) > 0
        return True

    # ── write protection: only the actions below change a line ──────────
    def write(self, vals):
        editable = {'note', 'evidence_ref', 'evidence_url'}
        if not self.env.context.get('faizy_line_internal') and not self.env.su:
            if set(vals) - editable:
                raise AccessError(self.env._('Use the checklist buttons to change a step.'))
            self.mapped('checklist_id')._check_open()
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise AccessError(self.env._('Checklist steps cannot be deleted.'))
        return super().unlink()

    # ── actions ──────────────────────────────────────────────────────────
    def _has_evidence(self):
        self.ensure_one()
        return bool(self.evidence_ref or (self.evidence_url or '').strip() or (self.note or '').strip())

    def action_done(self):
        user = self.env.user
        for line in self:
            ck = line.checklist_id
            ck._check_open()
            if ck.state == 'blocked':
                raise UserError(self.env._('This checklist is blocked. Unblock it first.'))
            if not line.applicable:
                raise UserError(self.env._('"%s" does not apply to this record.', line.name))
            if line.evidence_required and not line._has_evidence():
                raise UserError(self.env._(
                    '"%s" needs evidence: link the record, paste a link, or write a short note.', line.name))
            if line.restricted and (not user.has_group(G_MANAGER) or ck.owner_id == user):
                raise UserError(self.env._(
                    '"%s" is a restricted step. A Faizy Manager other than the owner completes it.', line.name))
            line.with_context(faizy_line_internal=True).write({
                'state': 'done', 'done_by': user.id, 'done_on': fields.Datetime.now(), 'auto_done': False})
            if ck.state == 'draft':
                ck._w({'state': 'in_progress'})
        return True

    def action_undo(self):
        """Take a tick back. The chatter keeps who ticked it and when."""
        for line in self:
            ck = line.checklist_id
            ck._check_open()
            if line.state == 'done' and ck.state != 'blocked':
                ck.message_post(body=self.env._(
                    'Step "%(s)s" un-ticked by %(u)s (it had been done by %(d)s).',
                    s=line.name, u=self.env.user.name, d=line.done_by.name or self.env._('the system')))
                line.with_context(faizy_line_internal=True).write({
                    'state': 'todo', 'done_by': False, 'done_on': False, 'auto_done': False})
        return True


class FaizyChecklistReason(models.TransientModel):
    _name = 'faizy.checklist.reason'
    _description = 'Reason for a checklist state change'

    checklist_id = fields.Many2one('faizy.checklist', required=True)
    action = fields.Selection([
        ('block', 'Block (with escalation)'), ('unblock', 'Unblock'),
        ('reject', 'Send back'), ('reopen', 'Reopen'),
    ], required=True)
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        self.checklist_id._transition_with_reason(self.action, self.reason)
        return {'type': 'ir.actions.act_window_close'}
