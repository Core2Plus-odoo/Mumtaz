"""Stores through the door: each store's holding, transfers between them,
the daily reconciliation. Everything runs as the signed-in user; store
staff see their own store."""
from odoo import fields
from odoo.http import Controller, request

from odoo.addons.mumtaz_jewellery_api.controllers.api import ApiError, _body, _get, _int, _r, endpoint


def _warehouses():
    W = request.env['stock.warehouse']
    return W.search([*W._check_company_domain(request.env.company)], order='sequence, id')


class JawharStoresApi(Controller):

    @_r('/stores')
    @endpoint()
    def stores(self, **kw):
        mine = request.env.user.jewellery_store_id
        return {'items': [w.jewellery_summary() for w in _warehouses()], 'my_store': {'id': mine.id, 'name': mine.name} if mine else None}

    @_r('/stores/<int:store_id>/pieces')
    @endpoint()
    def store_pieces(self, store_id, **kw):
        w = _get('stock.warehouse', store_id)
        lots = w.jewellery_lots().sorted('name')
        from odoo.addons.mumtaz_jewellery_api.controllers.api import _piece_dict
        return {'items': [_piece_dict(l) for l in lots[:_int(kw.get('limit'), 200, 1, 500)]], 'total': len(lots)}

    @_r('/transfers')
    @endpoint()
    def transfers(self, **kw):
        state = kw.get('state')
        domain = [] if not state or state == 'all' else [('state', '=', state)]
        recs = request.env['jewellery.transfer'].search(domain, order='id desc', limit=_int(kw.get('limit'), 50))
        return {'items': [t.transfer_dict() for t in recs], 'count': len(recs)}

    @_r('/transfers', methods=['POST'])
    @endpoint()
    def transfer_create(self, **kw):
        body = _body()
        src = _get('stock.warehouse', body.get('from_id') or 0)
        dst = _get('stock.warehouse', body.get('to_id') or 0)
        serials = [(s or '').strip() for s in (body.get('serials') or []) if (s or '').strip()]
        if not serials:
            raise ApiError(400, 'validation', 'serials: at least one piece.')
        Lot = request.env['stock.lot']
        lots = Lot.search([('name', 'in', serials), ('product_id.is_jewellery', '=', True)])
        missing = sorted(set(s.upper() for s in serials) - set(l.name.upper() for l in lots))
        if missing:
            raise ApiError(400, 'validation', 'No such piece: %s.' % ', '.join(missing))
        t = request.env['jewellery.transfer'].create({
            'from_warehouse_id': src.id, 'to_warehouse_id': dst.id, 'lot_ids': [(6, 0, lots.ids)],
            'note': (body.get('note') or '')[:200] or False})
        if body.get('dispatch'):
            t.action_dispatch()
        return t.transfer_dict(), 201

    @_r('/transfers/<int:transfer_id>/dispatch', methods=['POST'])
    @endpoint()
    def transfer_dispatch(self, transfer_id, **kw):
        t = _get('jewellery.transfer', transfer_id)
        t.action_dispatch()
        return t.transfer_dict()

    @_r('/transfers/<int:transfer_id>/receive', methods=['POST'])
    @endpoint()
    def transfer_receive(self, transfer_id, **kw):
        t = _get('jewellery.transfer', transfer_id)
        t.action_receive()
        return t.transfer_dict()

    @_r('/transfers/<int:transfer_id>/lost', methods=['POST'])
    @endpoint()
    def transfer_lost(self, transfer_id, **kw):
        t = _get('jewellery.transfer', transfer_id)
        t.action_report_lost((_body().get('note') or '')[:200] or None)
        return t.transfer_dict()

    @_r('/reconciliations')
    @endpoint()
    def reconciliations(self, **kw):
        domain = []
        if kw.get('store_id'):
            domain.append(('warehouse_id', '=', int(kw['store_id'])))
        if kw.get('state'):
            domain.append(('state', '=', kw['state']))
        recs = request.env['jewellery.gold.reconciliation'].search(domain, limit=_int(kw.get('limit'), 30))
        return {'items': [r.recon_dict() for r in recs], 'count': len(recs)}

    @_r('/reconciliations', methods=['POST'])
    @endpoint()
    def reconciliation_open(self, **kw):
        body = _body()
        w = _get('stock.warehouse', body.get('store_id') or 0)
        date = fields.Date.to_date(body['date']) if body.get('date') else None
        rec = request.env['jewellery.gold.reconciliation'].open_for(w, date=date)
        return rec.recon_dict(detail=True), 201

    @_r('/reconciliations/<int:rec_id>')
    @endpoint()
    def reconciliation(self, rec_id, **kw):
        return _get('jewellery.gold.reconciliation', rec_id).recon_dict(detail=True)

    @_r('/reconciliations/<int:rec_id>/count', methods=['POST'])
    @endpoint()
    def reconciliation_count(self, rec_id, **kw):
        rec = _get('jewellery.gold.reconciliation', rec_id)
        serials = _body().get('serials') or []
        if not isinstance(serials, list):
            raise ApiError(400, 'validation', 'serials must be a list.')
        rec.action_count(serials[:2000])
        return rec.recon_dict(detail=True)

    @_r('/reconciliations/<int:rec_id>/close', methods=['POST'])
    @endpoint()
    def reconciliation_close(self, rec_id, **kw):
        rec = _get('jewellery.gold.reconciliation', rec_id)
        rec.action_close((_body().get('note') or '')[:300] or None)
        return rec.recon_dict(detail=True)
