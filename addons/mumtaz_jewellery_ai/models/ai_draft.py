import hashlib
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

KINDS = [('tray', 'Tray'), ('followup', 'Follow-up')]
STATES = [('pending', 'Waiting for review'), ('approved', 'Approved'),
          ('returned', 'Returned for edit'), ('dismissed', 'Dismissed'),
          ('expired', 'Lapsed')]
CHANNELS = [('note', 'Call note'), ('whatsapp', 'WhatsApp'), ('email', 'Email')]


def digest_of(text):
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()


class AiDraft(models.Model):
    """Prepared work waiting for a person (plan v3 wireframe 29).

    Approval binds to the exact payload: the digest the approver saw must be
    the digest of the draft now, so an edit after approval -- or a changed
    body while the inbox was open -- needs review again. Approving a
    follow-up marks it ready for a person to send. Nothing here sends.
    """

    _name = 'jewellery.ai.draft'
    _description = 'Jawhar AI draft'
    _order = 'id desc'

    name = fields.Char(default=lambda s: _('New'), copy=False, readonly=True)
    kind = fields.Selection(KINDS, required=True, index=True)
    agent = fields.Selection([('zayan', 'Zayan'), ('layla', 'Layla')], required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    partner_id = fields.Many2one('res.partner', string='Client', index=True, ondelete='cascade')
    restricted = fields.Boolean(related='partner_id.jewellery_restricted')
    tray_id = fields.Many2one('jewellery.tray', ondelete='set null')
    channel = fields.Selection(CHANNELS, default='note')
    subject = fields.Char()
    body = fields.Text(help='The exact text a person would send, or the tray summary.')
    body_digest = fields.Char(readonly=True, copy=False)
    reasons = fields.Text(help='Why now: the evidence, one line each.')
    sources = fields.Text(help='Records and timestamps the draft was built from.')
    model_used = fields.Char(default='local')
    state = fields.Selection(STATES, default='pending', required=True, index=True, copy=False)
    owner_id = fields.Many2one('res.users', string='Human owner', required=True,
                               default=lambda s: s.env.user)
    approved_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    approved_digest = fields.Char(readonly=True, copy=False)
    review_note = fields.Text()
    expires_at = fields.Datetime(readonly=True, copy=False)
    consent_ok = fields.Boolean(compute='_compute_consent_ok')
    expired = fields.Boolean(compute='_compute_expired')
    policy_version = fields.Char(required=True)

    @api.depends('partner_id.no_marketing', 'kind', 'channel')
    def _compute_consent_ok(self):
        for d in self:
            # A call note is for the associate, not a message to the client.
            d.consent_ok = d.kind != 'followup' or d.channel == 'note' or not d.partner_id.no_marketing

    @api.depends('expires_at', 'state')
    def _compute_expired(self):
        now = fields.Datetime.now()
        for d in self:
            d.expired = d.state == 'pending' and bool(d.expires_at) and d.expires_at < now

    def _days(self):
        param = self.env['ir.config_parameter'].sudo().get_param('mumtaz_jewellery.ai_draft_days')
        try:
            return max(1, int(param))
        except (TypeError, ValueError):
            return 7

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('jewellery.ai.draft') or _('New')
            vals['body_digest'] = digest_of(vals.get('body'))
            vals.setdefault('expires_at', fields.Datetime.now() + timedelta(days=self._days()))
        return super().create(vals_list)

    def write(self, vals):
        if 'body' in vals:
            # Changed content needs review: back to pending, approval cleared.
            vals = dict(vals, body_digest=digest_of(vals['body']))
            if any(d.state == 'approved' for d in self) or 'state' not in vals:
                vals.update(state='pending', approved_by_id=False, approved_at=False, approved_digest=False)
        return super().write(vals)

    # -- the review -----------------------------------------------------
    def action_approve(self, digest):
        """Approve exactly this payload. The digest is the one the approver
        saw; if the draft changed underneath, the approval does not bind."""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_('%s is not waiting for review.') % self.name)
        if self.expired:
            self.write({'state': 'expired'})
            raise UserError(_('%s has lapsed; ask the agent to prepare it again.') % self.name)
        if not digest or digest != self.body_digest:
            raise UserError(_(
                'The draft changed since you opened it. Read the current text and approve again.'))
        if not self.consent_ok:
            raise UserError(_(
                '%s has asked for no marketing messages. A call note is fine; a message is not.')
                % self.partner_id.display_name)
        self.write({'state': 'approved', 'approved_by_id': self.env.user.id,
                    'approved_at': fields.Datetime.now(), 'approved_digest': digest})
        return True

    def action_return(self, note=None):
        self.ensure_one()
        if self.state not in ('pending', 'approved'):
            raise UserError(_('%s cannot be returned.') % self.name)
        self.write({'state': 'returned', 'review_note': note or self.review_note,
                    'approved_by_id': False, 'approved_at': False, 'approved_digest': False})
        return True

    def action_dismiss(self):
        self.ensure_one()
        self.write({'state': 'dismissed'})
        return True

    def action_edit_body(self, body):
        """An edit by the reviewer: new digest, back to pending."""
        self.ensure_one()
        self.write({'body': body, 'state': 'pending'})
        return True
