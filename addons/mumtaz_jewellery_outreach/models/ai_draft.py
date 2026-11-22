"""An outreach draft is a follow-up tied to an occasion, and the send is a
person's act: the draft is handed to her as a link that opens the text in
her own WhatsApp or mail client. The server never sends a message."""
import re
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import UserError

MESSAGE_KINDS = ('followup', 'outreach')


class AiDraft(models.Model):
    _inherit = 'jewellery.ai.draft'

    kind = fields.Selection(selection_add=[('outreach', 'Occasion message')], ondelete={'outreach': 'cascade'})
    state = fields.Selection(selection_add=[('sent', 'Sent by a person')], ondelete={'sent': 'set default'})
    occasion_id = fields.Many2one('jewellery.occasion', ondelete='set null', index=True)
    occasion_year = fields.Integer(help='The year of the occasion this draft is for: one draft per occasion per year.')
    sent_by_id = fields.Many2one('res.users', string='Sent by', readonly=True, copy=False)
    sent_at = fields.Datetime(readonly=True, copy=False)
    sent_channel = fields.Selection([('note', 'Call made / note'), ('whatsapp', 'WhatsApp'), ('email', 'Email')],
                                    readonly=True, copy=False)
    send_note = fields.Char(copy=False)
    consent_status = fields.Selection(related='partner_id.marketing_consent')

    @api.depends('partner_id.no_marketing', 'partner_id.marketing_consent', 'kind', 'channel')
    def _compute_consent_ok(self):
        super()._compute_consent_ok()
        for d in self:
            # Withdrawn consent is a do-not-contact, whatever the flag says.
            if d.kind in MESSAGE_KINDS and d.channel != 'note' and d.partner_id.marketing_consent == 'withdrawn':
                d.consent_ok = False

    def _digits(self, phone):
        digits = re.sub(r'\D', '', phone or '')
        if digits.startswith('00'):
            digits = digits[2:]
        return digits

    def handoff(self, channel):
        """The link that opens the approved text in the person's own app.
        Nothing is transmitted by building it."""
        self.ensure_one()
        p = self.partner_id
        if channel == 'whatsapp':
            digits = self._digits(p.phone)
            return {'channel': channel, 'to': p.phone or None,
                    'url': ('https://wa.me/%s?text=%s' % (digits, quote(self.body or ''))) if digits else None}
        if channel == 'email':
            return {'channel': channel, 'to': p.email or None,
                    'url': ('mailto:%s?subject=%s&body=%s' % (p.email, quote(self.subject or ''), quote(self.body or '')))
                    if p.email else None}
        return {'channel': 'note', 'to': None, 'url': None}

    def action_mark_sent(self, channel=None, note=None):
        """A person sends the approved text herself and says so here. The
        approval must still bind to this text; a message channel needs the
        client's recorded consent; a restricted client's message goes only
        through her relationship manager, deputy or a VIP manager."""
        self.ensure_one()
        channel = channel or self.channel
        if channel not in ('note', 'whatsapp', 'email'):
            raise UserError(_('Channel is note, whatsapp or email.'))
        if self.state != 'approved':
            raise UserError(_('%s is not approved; only an approved draft is sent.') % self.name)
        if self.approved_digest != self.body_digest:
            raise UserError(_('The text changed after approval. Approve the current text first.'))
        p = self.partner_id
        if channel != 'note':
            if not p:
                raise UserError(_('A message needs a client.'))
            if p.no_marketing or p.marketing_consent != 'given':
                raise UserError(_(
                    'No recorded consent for %s. Ask her, record the consent on her file, then send; '
                    'until then a call is the way.') % p.display_name)
            if p.jewellery_restricted and not (
                    self.env.user in (p.relationship_manager_id, p.deputy_id)
                    or self.env.user.has_group('mumtaz_jewellery_vip.group_vip_manager')):
                raise UserError(_('Only the relationship manager, the deputy or a VIP manager sends to %s.') % p.display_name)
        handoff = self.handoff(channel)
        if channel != 'note' and not handoff['url']:
            raise UserError(_('%s has no %s on file.') % (p.display_name, _('phone number') if channel == 'whatsapp' else _('email address')))
        self.write({'state': 'sent', 'sent_by_id': self.env.user.id, 'sent_at': fields.Datetime.now(),
                    'sent_channel': channel, 'send_note': (note or '')[:200] or False})
        if p:
            label = dict(self._fields['sent_channel'].selection)[channel]
            p.message_post(body=_('%(name)s: %(what)s by %(user)s via %(channel)s.%(note)s',
                                  name=self.name, what=_('call noted') if channel == 'note' else _('message sent'),
                                  user=self.env.user.name, channel=label,
                                  note=(' ' + note) if note else ''),
                           message_type='comment', subtype_xmlid='mail.mt_note')
        return handoff
