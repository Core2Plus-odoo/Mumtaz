"""The compliance record: every threshold crossing, identity check,
screening and configuration change, written where finance can read and
report on it. The threshold itself is configuration a named finance manager
confirms; the code holds no default and invents no rule."""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

KINDS = [('config', 'Threshold confirmed'), ('kyc_verified', 'Identity verified'), ('screening', 'Screening recorded'),
         ('threshold_crossed', 'Cash threshold reached'), ('refused', 'Sale refused')]
P_THRESHOLD = 'mumtaz_jewellery.aml_cash_threshold'
P_WINDOW = 'mumtaz_jewellery.aml_cash_window_days'
P_BY = 'mumtaz_jewellery.aml_confirmed_by'
P_AT = 'mumtaz_jewellery.aml_confirmed_at'
P_NOTE = 'mumtaz_jewellery.aml_confirmed_note'


class AmlEvent(models.Model):
    _name = 'jewellery.aml.event'
    _description = 'AML / KYC event'
    _order = 'id desc'

    kind = fields.Selection(KINDS, required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    partner_id = fields.Many2one('res.partner', string='Client', index=True, ondelete='set null')
    restricted = fields.Boolean(related='partner_id.jewellery_restricted')
    order_id = fields.Many2one('sale.order', ondelete='set null')
    invoice_id = fields.Many2one('account.move', ondelete='set null')
    user_id = fields.Many2one('res.users', string='By', required=True, default=lambda s: s.env.user)
    amount_cash = fields.Monetary(currency_field='currency_id', help='Cash taken in this sale.')
    cash_window_before = fields.Monetary(currency_field='currency_id', help="The client's cash in the window before this sale.")
    threshold = fields.Monetary(currency_field='currency_id')
    window_days = fields.Integer()
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    kyc_status = fields.Char()
    kyc_id_type = fields.Char()
    kyc_id_last4 = fields.Char()
    kyc_id_expiry = fields.Date()
    screening = fields.Char()
    risk_band = fields.Char()
    note = fields.Char()

    # -- the configuration ---------------------------------------------------
    @api.model
    def config(self):
        P = self.env['ir.config_parameter'].sudo()
        raw = P.get_param(P_THRESHOLD)
        try:
            threshold = float(raw) if raw else 0.0
        except ValueError:
            threshold = 0.0
        try:
            window = int(P.get_param(P_WINDOW) or 0) or 365
        except ValueError:
            window = 365
        by = self.env['res.users'].sudo().browse(int(P.get_param(P_BY) or 0)).exists()
        return {
            'configured': threshold > 0, 'threshold': threshold, 'window_days': window,
            'currency': self.env.company.currency_id.name,
            'confirmed_by': {'id': by.id, 'name': by.name} if by else None,
            'confirmed_at': P.get_param(P_AT) or None, 'note': P.get_param(P_NOTE) or None,
            'can_configure': self._is_finance(),
        }

    @api.model
    def _is_finance(self):
        u = self.env.user
        return u.has_group('mumtaz_jewellery.group_jewellery_manager') and u.has_group('account.group_account_invoice')

    @api.model
    def set_threshold(self, threshold, window_days=None, note=None):
        """The named finance manager confirms the values. Dated and signed
        in the parameters and in the event log; zero removes the threshold."""
        if not self._is_finance():
            raise AccessError(_('Only a jewellery manager with the accounting role confirms the AML cash threshold.'))
        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            raise UserError(_('The threshold is an amount.'))
        if threshold < 0:
            raise UserError(_('The threshold cannot be negative; zero removes it.'))
        window = int(window_days) if window_days not in (None, '') else self.config()['window_days']
        if window < 1 or window > 3660:
            raise UserError(_('The window is a number of days between 1 and 3660.'))
        P = self.env['ir.config_parameter'].sudo()
        P.set_param(P_THRESHOLD, repr(threshold) if threshold else '')
        P.set_param(P_WINDOW, str(window))
        P.set_param(P_BY, str(self.env.user.id))
        P.set_param(P_AT, fields.Datetime.now().isoformat(timespec='seconds'))
        P.set_param(P_NOTE, (note or '')[:200])
        self.sudo().create({'kind': 'config', 'threshold': threshold, 'window_days': window,
                            'note': (note or '')[:200] or False})
        return self.config()

    # -- the gate ------------------------------------------------------------
    @api.model
    def evaluate(self, partner, journal, amount, total):
        """What the counter would do with this payment. Pure reading: the
        threshold, the cash now, the client's cash in the window, and
        whether identity and screening allow the sale when it crosses."""
        cfg = self.config()
        cash_now = 0.0
        if journal and journal.type == 'cash':
            cash_now = float(total if amount is None else amount)
        out = {'configured': cfg['configured'], 'threshold': cfg['threshold'], 'window_days': cfg['window_days'],
               'currency': cfg['currency'], 'cash_now': cash_now, 'cash_window': 0.0, 'crosses': False,
               'ok': True, 'reason': None, 'kyc': None}
        if not partner:
            return out
        out['kyc'] = partner.kyc_dict()
        if not cfg['configured']:
            out['reason'] = 'not_configured'
            return out
        out['cash_window'] = partner.aml_cash_in_window(cfg['window_days'])
        if cash_now <= 0:
            return out
        if out['cash_window'] + cash_now < cfg['threshold'] - 0.005:
            return out
        out['crosses'] = True
        if partner.aml_screening_status == 'match':
            out.update(ok=False, reason='screening_match')
        elif partner.kyc_status != 'verified':
            out.update(ok=False, reason='kyc_required')
        elif partner.kyc_expired:
            out.update(ok=False, reason='kyc_expired')
        return out

    @api.model
    def reason_text(self, reason, partner=None):
        name = partner.display_name if partner else _('this client')
        return {
            'screening_match': _('%s has a screening match. Cash at or above the threshold needs a compliance decision; a manager clears it on her record.') % name,
            'kyc_required': _('Cash at or above the threshold needs a verified identity for %s. Check her document and record it on her file, or take the payment another way.') % name,
            'kyc_expired': _("%s's identity document has expired. Verify a current one, or take the payment another way.") % name,
        }.get(reason, reason or '')
