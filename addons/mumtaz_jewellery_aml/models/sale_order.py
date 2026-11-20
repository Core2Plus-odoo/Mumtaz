"""The counter gate: cash now plus cash in the window against the confirmed
threshold. The readiness check says what would stop the sale; the commit
refuses in the same transaction, so a refused sale never happened."""
from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import config


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _counter_extra_checks(self, partner=None, lot=None, journal=None, amount=None, discount=0.0):
        checks = super()._counter_extra_checks(partner=partner, lot=lot, journal=journal, amount=amount, discount=discount)
        total = 0.0
        if lot:
            try:
                total = float(lot.get_price_breakdown(making_discount_pct=discount or 0.0).get('total') or 0.0)
            except (UserError, TypeError, ValueError):
                total = 0.0
        ev = self.env['jewellery.aml.event'].evaluate(partner, journal, amount, total)
        detail = dict(ev)
        if not ev['ok']:
            detail['message'] = self.env['jewellery.aml.event'].reason_text(ev['reason'], partner)
        checks.append({'key': 'aml', 'ok': ev['ok'], 'detail': detail})
        return checks

    def action_counter_commit(self, journal=None, amount=None):
        self.ensure_one()
        Event = self.env['jewellery.aml.event']
        partner = self.partner_id
        ev = Event.evaluate(partner, journal, amount, self.amount_total)
        if not ev['ok']:
            # The refusal must outlive the error that rolls this request back,
            # so it is written on its own cursor.
            self._aml_persist_refusal(ev)
            raise UserError(Event.reason_text(ev['reason'], partner))
        out = super().action_counter_commit(journal=journal, amount=amount)
        if ev['crosses']:
            Event.sudo().create({
                'kind': 'threshold_crossed', 'partner_id': partner.id, 'order_id': self.id,
                'invoice_id': out['invoice'].id, 'amount_cash': ev['cash_now'], 'cash_window_before': ev['cash_window'],
                'threshold': ev['threshold'], 'window_days': ev['window_days'],
                'kyc_status': ev['kyc']['status'], 'kyc_id_type': ev['kyc']['id_type'], 'kyc_id_last4': ev['kyc']['id_last4'],
                'kyc_id_expiry': ev['kyc']['id_expiry'], 'screening': ev['kyc']['screening'], 'risk_band': ev['kyc']['risk_band'],
                'note': _('Verified by %s') % (partner.kyc_verified_by_id.name or '')})
        return out

    def _aml_persist_refusal(self, ev):
        """Write the refusal on a separate cursor so the UserError that
        follows (which rolls the request back) does not erase it. Under the
        test runner every cursor is the test's own, so nothing is written
        there."""
        if config['test_enable']:
            return
        try:
            with self.env.registry.cursor() as cr:
                env = self.env(cr=cr)
                env['jewellery.aml.event'].sudo().create({
                    'kind': 'refused', 'partner_id': self.partner_id.id, 'amount_cash': ev['cash_now'],
                    'cash_window_before': ev['cash_window'], 'threshold': ev['threshold'], 'window_days': ev['window_days'],
                    'kyc_status': ev['kyc']['status'], 'screening': ev['kyc']['screening'], 'note': ev['reason'],
                    'user_id': self.env.user.id, 'company_id': self.env.company.id})
        except Exception:  # noqa: BLE001 -- the audit must never break the refusal itself
            pass
