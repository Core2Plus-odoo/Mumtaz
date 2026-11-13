"""Kiosk requests for staff: list, confirm, decline. Same door, same audit."""
from odoo.http import Controller, request

from .api import ApiError, _body, _get, _int, _m2o, _r, endpoint


def _req_dict(r):
    return {
        'id': r.id, 'name': r.name, 'kind': r.kind, 'state': r.state, 'channel': r.channel, 'lang': r.lang,
        'piece': {'id': r.lot_id.id, 'serial': r.serial, 'product': _m2o(r.lot_id.product_id), 'karat': r.lot_id.karat},
        'price_quoted': r.price_quoted, 'client_name': r.client_name, 'phone': r.phone,
        'preferred_time': r.preferred_time or None, 'address': r.address or None, 'slot': r.slot or None,
        'delivery_date': r.delivery_date, 'note': r.note or None, 'fit_notes': r.fit_notes or None, 'created_at': r.create_date,
        'client': _m2o(r.partner_id), 'lead': _m2o(r.lead_id), 'order': _m2o(r.order_id),
        'decided_by': _m2o(r.decided_by_id), 'decided_at': r.decided_at, 'decline_reason': r.decline_reason or None,
        'available': request.env['jewellery.tray']._lot_available(r.lot_id),
    }


class JawharKioskApi(Controller):

    @_r('/kiosk/requests')
    @endpoint()
    def kiosk_requests(self, state='requested', limit=50, **kw):
        domain = [] if state == 'all' else [('state', '=', state)]
        recs = request.env['jewellery.kiosk.request'].search(domain, order='id desc', limit=_int(limit, 50))
        return {'items': [_req_dict(r) for r in recs], 'count': len(recs)}

    @_r('/kiosk/requests/<int:req_id>')
    @endpoint()
    def kiosk_request(self, req_id, **kw):
        return _req_dict(_get('jewellery.kiosk.request', req_id))

    @_r('/kiosk/requests/<int:req_id>/confirm', methods=['POST'])
    @endpoint()
    def kiosk_confirm(self, req_id, **kw):
        r = _get('jewellery.kiosk.request', req_id)
        r.action_confirm()
        return _req_dict(r)

    @_r('/kiosk/requests/<int:req_id>/decline', methods=['POST'])
    @endpoint()
    def kiosk_decline(self, req_id, **kw):
        r = _get('jewellery.kiosk.request', req_id)
        reason = (_body().get('reason') or '')[:200]
        if not reason:
            raise ApiError(400, 'validation', 'Say why, in a few words: the client is called back with it.')
        r.action_decline(reason)
        return _req_dict(r)
