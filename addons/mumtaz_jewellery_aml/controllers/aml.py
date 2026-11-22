"""AML and KYC through the door: the configuration finance confirms, the
client's identity and screening, the event log. Everything runs as the
signed-in user; the counter's readiness and commit carry the gate."""
from odoo.http import Controller, request

from odoo.addons.mumtaz_jewellery_api.controllers.api import ApiError, _body, _get, _int, _m2o, _r, endpoint


def _event_dict(e):
    return {
        'id': e.id, 'at': e.create_date, 'kind': e.kind, 'client': _m2o(e.partner_id), 'restricted': e.restricted,
        'order': _m2o(e.order_id), 'invoice': _m2o(e.invoice_id), 'by': _m2o(e.user_id),
        'amount_cash': e.amount_cash, 'cash_window_before': e.cash_window_before, 'threshold': e.threshold,
        'window_days': e.window_days, 'currency': e.currency_id.name,
        'kyc': {'status': e.kyc_status or None, 'id_type': e.kyc_id_type or None, 'id_last4': e.kyc_id_last4 or None,
                'id_expiry': e.kyc_id_expiry or None, 'screening': e.screening or None, 'risk_band': e.risk_band or None},
        'note': e.note or None,
    }


class JawharAmlApi(Controller):

    @_r('/aml/config')
    @endpoint()
    def aml_config(self, **kw):
        return request.env['jewellery.aml.event'].config()

    @_r('/aml/config', methods=['POST'])
    @endpoint()
    def aml_config_set(self, **kw):
        body = _body()
        if 'threshold' not in body:
            raise ApiError(400, 'validation', 'threshold is required (0 removes it).')
        return request.env['jewellery.aml.event'].set_threshold(
            body.get('threshold'), window_days=body.get('window_days'), note=(body.get('note') or '')[:200] or None)

    @_r('/aml/events')
    @endpoint()
    def aml_events(self, **kw):
        domain = []
        if kw.get('kind'):
            domain.append(('kind', '=', kw['kind']))
        if kw.get('client_id'):
            domain.append(('partner_id', '=', int(kw['client_id'])))
        recs = request.env['jewellery.aml.event'].search(domain, order='id desc', limit=_int(kw.get('limit'), 50))
        return {'items': [_event_dict(e) for e in recs], 'count': len(recs)}

    @_r('/aml/expiring')
    @endpoint()
    def aml_expiring(self, **kw):
        from datetime import timedelta
        from odoo import fields
        today = fields.Date.context_today(request.env['res.partner'])
        days = _int(kw.get('days'), 30, lo=1, hi=365)
        recs = request.env['res.partner'].search([('kyc_status', '=', 'verified'), ('kyc_id_expiry', '!=', False),
                                                  ('kyc_id_expiry', '<=', today + timedelta(days=days))], order='kyc_id_expiry')
        return {'items': [{'client': _m2o(p), 'restricted': p.jewellery_restricted, **p.kyc_dict()} for p in recs]}

    @_r('/clients/<int:client_id>/kyc')
    @endpoint()
    def client_kyc(self, client_id, **kw):
        return _get('res.partner', client_id).kyc_dict()

    @_r('/clients/<int:client_id>/kyc/verify', methods=['POST'])
    @endpoint()
    def client_kyc_verify(self, client_id, **kw):
        p = _get('res.partner', client_id)
        body = _body()
        p.action_verify_identity(body.get('id_type'), body.get('last4'), body.get('expiry'), note=(body.get('note') or '')[:200] or None)
        return p.kyc_dict()

    @_r('/clients/<int:client_id>/kyc/screening', methods=['POST'])
    @endpoint()
    def client_kyc_screening(self, client_id, **kw):
        p = _get('res.partner', client_id)
        body = _body()
        p.action_record_screening(body.get('status'), risk_band=body.get('risk_band') or None, note=(body.get('note') or '')[:200] or None)
        return p.kyc_dict()
