"""The kiosk's door: public, read-only except for one request.

No session, no client data, no internal ids: a piece is addressed by its
serial, a request by its reference. Everything runs as the public user
under sudo over a fixed, narrow set of reads.
"""
import base64
import json
import logging

from odoo.exceptions import UserError
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)
PREFIX = '/jawhar/public/kiosk'
CATEGORIES = ('bangle', 'chain', 'necklace', 'ring', 'earrings', 'bracelet', 'pendant', 'set', 'coin')


def _json(data, status=200):
    return request.make_json_response({'ok': True, 'data': data}, status=status)


def _fail(status, code, message):
    return request.make_json_response({'ok': False, 'error': {'code': code, 'message': message}}, status=status)


def _body():
    raw = request.httprequest.get_data(as_text=True)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _piece(lot, detail=False):
    try:
        b = lot.get_price_breakdown()
        price = float(b['total'])
    except Exception:  # noqa: BLE001 -- a piece that cannot be priced is not shown
        return None
    data = {
        'serial': lot.name, 'design': lot.product_id.name, 'category': lot.product_id.jewellery_category or None,
        'karat': lot.karat, 'net_weight_g': lot.net_weight_g, 'price_incl_vat': price,
        'currency': lot.company_id.currency_id.name or request.env.company.currency_id.name,
        'stones': bool(lot.stone_weight_g), 'certificate': bool(lot.certificate_ref),
        'image_url': (PREFIX + '/pieces/%s/image' % lot.name) if lot.product_id.image_1024 else None,
        'tryon_url': (PREFIX + '/pieces/%s/tryon' % lot.name) if lot.product_id.jewellery_tryon_image else None,
        'dims': {'length_mm': lot.product_id.jewellery_length_mm or None,
                 'inner_diameter_mm': lot.product_id.jewellery_inner_diameter_mm or None,
                 'width_mm': lot.product_id.jewellery_width_mm or None},
    }
    if detail:
        try:
            rate = request.env(su=True)['jewellery.gold.rate'].get_current(lot.company_id or request.env.company).rate_per_gram
        except UserError:
            rate = 0.0
        data.update({'gross_weight_g': lot.gross_weight_g, 'stone_weight_g': lot.stone_weight_g,
                     'making_type': lot.making_type, 'rate_per_gram': rate})
    return data


class PublicKiosk(Controller):

    @route(PREFIX + '/agent', type='http', auth='public', methods=['GET'], csrf=False)
    def agent(self, **kw):
        """The kiosk's conversational agent id: public by nature (it sits in
        the page), configured per tenant."""
        aid = request.env(su=True)['ir.config_parameter'].get_param('mumtaz_jewellery.voice_agent_noor')
        return _json({'agent_id': aid or None, 'name': 'Noor'})

    @route(PREFIX + '/rate', type='http', auth='public', methods=['GET'], csrf=False)
    def rate(self, **kw):
        env = request.env(su=True)
        try:
            r = env['jewellery.gold.rate'].get_current(env.company)
        except UserError:
            return _json({'rate': None})
        return _json({'rate': {'rate_per_gram': r.rate_per_gram, 'currency': r.currency_id.name,
                               'approved_at': r.approved_at or r.effective_at}})

    @route(PREFIX + '/pieces', type='http', auth='public', methods=['GET'], csrf=False)
    def pieces(self, q=None, category=None, karat=None, max_price=None, limit=6, **kw):
        env = request.env(su=True)
        domain = [('product_id.is_jewellery', '=', True), ('product_qty', '>', 0)]
        if category in CATEGORIES:
            domain.append(('product_id.jewellery_category', '=', category))
        if karat in ('24', '22', '21', '18', '14', '9'):
            domain.append(('karat', '=', karat))
        if q:
            q = str(q)[:60]
            cat = next((c for c in CATEGORIES if c in q.lower()), None)
            if cat and not category:
                domain.append(('product_id.jewellery_category', '=', cat))
            else:
                domain += ['|', ('name', 'ilike', q), ('product_id.name', 'ilike', q)]
        Tray = env['jewellery.tray']
        lots = [l for l in env['stock.lot'].search(domain, order='name', limit=200) if Tray._lot_public(l)]
        out = [p for p in (_piece(l) for l in lots) if p]
        try:
            cap = float(max_price) if max_price not in (None, '') else None
        except ValueError:
            cap = None
        if cap:
            out = [p for p in out if p['price_incl_vat'] <= cap]
        out.sort(key=lambda p: p['price_incl_vat'])
        try:
            n = max(1, min(12, int(limit)))
        except (TypeError, ValueError):
            n = 6
        return _json({'items': out[:n], 'total': len(out)})

    @route(PREFIX + '/pieces/<string:serial>', type='http', auth='public', methods=['GET'], csrf=False)
    def piece(self, serial, **kw):
        env = request.env(su=True)
        lot = env['stock.lot'].search([('name', '=', serial[:40]), ('product_id.is_jewellery', '=', True)], limit=1)
        if not lot or not env['jewellery.tray']._lot_public(lot):
            return _fail(404, 'not_found', 'Not on the shelf.')
        data = _piece(lot, detail=True)
        return _json(data) if data else _fail(404, 'not_found', 'Not on the shelf.')

    @route(PREFIX + '/pieces/<string:serial>/image', type='http', auth='public', methods=['GET'], csrf=False)
    def piece_image(self, serial, **kw):
        """The design's photo, for a piece on the shelf. Nothing else about
        the piece travels with it."""
        env = request.env(su=True)
        lot = env['stock.lot'].search([('name', '=', serial[:40]), ('product_id.is_jewellery', '=', True)], limit=1)
        if not lot or not lot.product_id.image_1024 or not env['jewellery.tray']._lot_public(lot):
            return request.not_found()
        data = base64.b64decode(lot.product_id.image_1024)
        return request.make_response(data, headers=[('Content-Type', 'image/png' if data[:4] == b'\x89PNG' else 'image/jpeg'),
                                                    ('Cache-Control', 'public, max-age=3600')])

    @route(PREFIX + '/pieces/<string:serial>/tryon', type='http', auth='public', methods=['GET'], csrf=False)
    def piece_tryon(self, serial, **kw):
        """The design's cutout on a transparent background, for the try-on."""
        env = request.env(su=True)
        lot = env['stock.lot'].search([('name', '=', serial[:40]), ('product_id.is_jewellery', '=', True)], limit=1)
        if not lot or not lot.product_id.jewellery_tryon_image or not env['jewellery.tray']._lot_public(lot):
            return request.not_found()
        data = base64.b64decode(lot.product_id.jewellery_tryon_image)
        return request.make_response(data, headers=[('Content-Type', 'image/png'), ('Cache-Control', 'public, max-age=3600')])

    @route(PREFIX + '/request', type='http', auth='public', methods=['POST'], csrf=False)
    def make_request(self, **kw):
        body = _body()
        if body is None:
            return _fail(400, 'bad_json', 'The request body must be a JSON object.')
        try:
            out = request.env(su=True)['jewellery.kiosk.request'].create_public(
                kind=body.get('kind'), serial=body.get('serial'), client_name=body.get('name'), phone=body.get('phone'),
                preferred_time=body.get('preferred_time'), address=body.get('address'), slot=body.get('slot'),
                note=body.get('note'), lang=body.get('lang') or 'en', channel=body.get('channel') or 'store',
                fit=body.get('fit'))
        except UserError as exc:
            return _fail(400, 'invalid', str(exc))
        return _json(out, status=201)
