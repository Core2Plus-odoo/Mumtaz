"""Identity and screening on the client record. The document number is
never stored: the type, the last four characters and the expiry are enough
to say that a person checked it. Nothing here enters a model request."""
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

KYC_STATUS = [('none', 'Not verified'), ('verified', 'Verified'), ('expired', 'Expired'), ('refused', 'Refused')]
ID_TYPES = [('emirates_id', 'Emirates ID'), ('national_id', 'National ID'), ('passport', 'Passport'),
            ('iqama', 'Iqama'), ('other', 'Other')]
SCREENING = [('not_screened', 'Not screened'), ('clear', 'Clear'), ('match', 'Match: compliance decision')]
RISK = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
_LAST4 = re.compile(r'^[A-Za-z0-9]{4}$')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    kyc_status = fields.Selection(KYC_STATUS, string='Identity', default='none', required=True, tracking=True, index=True)
    kyc_id_type = fields.Selection(ID_TYPES, string='Document')
    kyc_id_last4 = fields.Char(string='Document, last 4', size=4, help='The last four characters only; the number itself is never stored.')
    kyc_id_expiry = fields.Date(string='Document expiry')
    kyc_verified_by_id = fields.Many2one('res.users', string='Identity verified by', readonly=True, copy=False)
    kyc_verified_at = fields.Datetime(readonly=True, copy=False)
    kyc_note = fields.Char(copy=False)
    kyc_expired = fields.Boolean(compute='_compute_kyc_expired')
    aml_screening_status = fields.Selection(SCREENING, string='Screening', default='not_screened', required=True, tracking=True)
    aml_screened_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    aml_screened_at = fields.Datetime(readonly=True, copy=False)
    aml_risk_band = fields.Selection(RISK, string='Risk band', tracking=True)
    aml_note = fields.Char(copy=False)
    aml_cash_window_total = fields.Monetary(compute='_compute_aml_cash_window', string='Cash in the window',
                                            currency_field='company_currency_id')

    @api.depends('kyc_status', 'kyc_id_expiry')
    def _compute_kyc_expired(self):
        today = fields.Date.context_today(self)
        for p in self:
            p.kyc_expired = p.kyc_status == 'verified' and bool(p.kyc_id_expiry) and p.kyc_id_expiry < today

    def _compute_aml_cash_window(self):
        Event = self.env['jewellery.aml.event']
        for p in self:
            p.aml_cash_window_total = p.aml_cash_in_window(Event.config()['window_days'])

    def aml_cash_in_window(self, window_days):
        """Cash the client paid us inside the window: inbound payments on a
        cash journal, not cancelled. Read with sudo: the sum is a compliance
        figure, not a document the person may not see."""
        self.ensure_one()
        if not self.id:
            return 0.0
        since = fields.Date.context_today(self) - timedelta(days=max(1, int(window_days)))
        payments = self.env['account.payment'].sudo().search([
            ('partner_id', 'child_of', self.commercial_partner_id.id or self.id),
            ('payment_type', '=', 'inbound'), ('journal_id.type', '=', 'cash'),
            ('state', 'not in', ('draft', 'canceled', 'rejected')), ('date', '>=', since)])
        cur = self.env.company.currency_id
        return sum(pm.currency_id._convert(pm.amount, cur, pm.company_id, pm.date) for pm in payments)

    def action_verify_identity(self, id_type, last4, expiry, note=None):
        """A person has seen the document. Only its type, last four
        characters and expiry are kept."""
        self.ensure_one()
        if id_type not in dict(ID_TYPES):
            raise UserError(_('Document type is one of: %s.') % ', '.join(k for k, _l in ID_TYPES))
        last4 = (last4 or '').strip()
        if not _LAST4.match(last4):
            raise UserError(_('Give exactly the last four characters of the document, nothing more.'))
        expiry = fields.Date.to_date(expiry) if expiry else False
        if not expiry:
            raise UserError(_('The document expiry date is needed.'))
        if expiry < fields.Date.context_today(self):
            raise UserError(_('This document expired on %s; an expired document does not verify identity.') % expiry)
        self.check_access('write')
        self.write({'kyc_status': 'verified', 'kyc_id_type': id_type, 'kyc_id_last4': last4.upper(),
                    'kyc_id_expiry': expiry, 'kyc_verified_by_id': self.env.user.id,
                    'kyc_verified_at': fields.Datetime.now(), 'kyc_note': (note or '')[:200] or False})
        self.message_post(body=_('Identity verified by %(user)s: %(doc)s ending %(last4)s, expires %(exp)s.',
                                 user=self.env.user.name, doc=dict(ID_TYPES)[id_type], last4=last4.upper(), exp=expiry),
                          message_type='comment', subtype_xmlid='mail.mt_note')
        self.env['jewellery.aml.event'].sudo().create({
            'kind': 'kyc_verified', 'partner_id': self.id, 'user_id': self.env.user.id,
            'kyc_status': 'verified', 'kyc_id_type': id_type, 'kyc_id_last4': last4.upper(), 'kyc_id_expiry': expiry,
            'note': (note or '')[:200] or False})
        return True

    def action_record_screening(self, status, risk_band=None, note=None):
        """A manager records the screening result and the risk band. A match
        is a compliance decision: the counter refuses cash above the
        threshold until a person clears it here."""
        self.ensure_one()
        if status not in dict(SCREENING):
            raise UserError(_('Screening is one of: %s.') % ', '.join(k for k, _l in SCREENING))
        if risk_band and risk_band not in dict(RISK):
            raise UserError(_('Risk band is low, medium or high.'))
        if not self.env.user.has_group('mumtaz_jewellery.group_jewellery_manager'):
            raise AccessError(_('Only a jewellery manager records a screening result.'))
        self.check_access('write')
        self.write({'aml_screening_status': status, 'aml_risk_band': risk_band or self.aml_risk_band,
                    'aml_screened_by_id': self.env.user.id, 'aml_screened_at': fields.Datetime.now(),
                    'aml_note': (note or '')[:200] or False})
        self.message_post(body=_('Screening recorded by %(user)s: %(status)s%(risk)s.%(note)s',
                                 user=self.env.user.name, status=dict(SCREENING)[status],
                                 risk=(', risk %s' % dict(RISK)[risk_band]) if risk_band else '',
                                 note=(' ' + note) if note else ''),
                          message_type='comment', subtype_xmlid='mail.mt_note')
        self.env['jewellery.aml.event'].sudo().create({
            'kind': 'screening', 'partner_id': self.id, 'user_id': self.env.user.id,
            'screening': status, 'risk_band': risk_band or False, 'note': (note or '')[:200] or False})
        return True

    def kyc_dict(self):
        self.ensure_one()
        return {
            'status': 'expired' if self.kyc_expired else self.kyc_status,
            'id_type': self.kyc_id_type or None, 'id_last4': self.kyc_id_last4 or None,
            'id_expiry': self.kyc_id_expiry or None, 'expired': self.kyc_expired,
            'verified_by': {'id': self.kyc_verified_by_id.id, 'name': self.kyc_verified_by_id.name} if self.kyc_verified_by_id else None,
            'verified_at': self.kyc_verified_at or None, 'note': self.kyc_note or None,
            'screening': self.aml_screening_status, 'risk_band': self.aml_risk_band or None,
            'screened_by': {'id': self.aml_screened_by_id.id, 'name': self.aml_screened_by_id.name} if self.aml_screened_by_id else None,
            'screened_at': self.aml_screened_at or None, 'aml_note': self.aml_note or None,
            'cash_in_window': self.aml_cash_window_total,
        }
