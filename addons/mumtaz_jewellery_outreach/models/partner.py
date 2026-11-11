"""Consent is a fact on the client record: not recorded, given, or
withdrawn, with when, how and by whom. It is the one thing that decides
whether a message may leave; nothing an agent writes changes it."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

CONSENT = [('unknown', 'Not recorded'), ('given', 'Given'), ('withdrawn', 'Withdrawn')]
SOURCES = [('in_store', 'In store'), ('phone', 'On the phone'), ('form', 'Signed form'),
           ('client_message', 'The client wrote to us')]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    marketing_consent = fields.Selection(CONSENT, string='Marketing consent', default='unknown',
                                         required=True, tracking=True, index=True)
    consent_date = fields.Date(readonly=True, copy=False)
    consent_source = fields.Selection(SOURCES, string='Consent recorded', copy=False)
    consent_by_id = fields.Many2one('res.users', string='Recorded by', readonly=True, copy=False)
    consent_note = fields.Char(copy=False)
    may_message = fields.Boolean(compute='_compute_may_message',
                                 help='Recorded consent and no do-not-contact flag: a message may be sent by a person.')

    @api.depends('marketing_consent', 'no_marketing')
    def _compute_may_message(self):
        for p in self:
            p.may_message = p.marketing_consent == 'given' and not p.no_marketing

    def action_record_consent(self, status, source=None, note=None):
        """A person records what the client said. 'withdrawn' also sets the
        do-not-contact flag; 'given' clears it, since the client just said
        so. Written to the chatter so the record carries its own history."""
        self.ensure_one()
        if status not in dict(CONSENT):
            raise UserError(_('Consent is "given", "withdrawn" or "unknown".'))
        if status != 'unknown' and source not in dict(SOURCES):
            raise UserError(_('Say how the consent was recorded: in store, on the phone, a signed form, or a message from the client.'))
        self.check_access('write')
        vals = {'marketing_consent': status, 'consent_source': source if status != 'unknown' else False,
                'consent_note': (note or '')[:200] or False,
                'consent_date': fields.Date.context_today(self) if status != 'unknown' else False,
                'consent_by_id': self.env.user.id if status != 'unknown' else False}
        if status == 'withdrawn':
            vals['no_marketing'] = True
        elif status == 'given':
            vals['no_marketing'] = False
        self.write(vals)
        labels = dict(CONSENT)
        self.message_post(body=_('Marketing consent: %(status)s (%(source)s) recorded by %(user)s. %(note)s',
                                 status=labels[status], source=dict(SOURCES).get(source, _('not recorded')),
                                 user=self.env.user.name, note=note or ''),
                          message_type='comment', subtype_xmlid='mail.mt_note')
        return True

    def consent_dict(self):
        self.ensure_one()
        return {
            'status': self.marketing_consent, 'date': self.consent_date or None,
            'source': self.consent_source or None, 'note': self.consent_note or None,
            'recorded_by': {'id': self.consent_by_id.id, 'name': self.consent_by_id.name} if self.consent_by_id else None,
            'no_marketing': self.no_marketing, 'may_message': self.may_message,
        }
