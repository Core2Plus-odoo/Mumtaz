"""The client's door: /jawhar/client/*, public, scoped by her token alone.
No payments, no prices made here, no agent: the page reads the engine and
her own records."""
import base64
import json
import logging

from odoo.exceptions import UserError
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)
PREFIX = '/jawhar/client'


def _json(data, status=200):
    return request.make_response(json.dumps({'ok': status < 400, 'data': data} if status < 400 else data, default=str),
                                 status=status, headers=[('Content-Type', 'application/json'), ('Cache-Control', 'no-store')])


def _fail(status, code, message):
    return _json({'ok': False, 'error': {'code': code, 'message': message}}, status)


def _body():
    try:
        raw = request.httprequest.get_data(as_text=True)
        return json.loads(raw) if raw else {}
    except ValueError:
        return {}


def _session():
    token = request.httprequest.headers.get('X-Client-Token') or _body().get('token')
    return request.env(su=True)['jewellery.client.session'].by_token(token)


def _r(path, methods=('GET',)):
    return route(PREFIX + path, type='http', auth='public', methods=list(methods), csrf=False)


class JawharClientApp(Controller):

    @_r('/code', methods=['POST'])
    def code(self, **kw):
        body = _body()
        try:
            out = request.env(su=True)['jewellery.client.session'].request_code(body.get('phone'), lang=body.get('lang') or 'en')
        except UserError as e:
            return _fail(400, 'invalid', str(e.args[0]))
        return _json(out)

    @_r('/verify', methods=['POST'])
    def verify(self, **kw):
        body = _body()
        out = request.env(su=True)['jewellery.client.session'].verify(body.get('phone'), body.get('code'))
        if not out['ok']:
            return _fail(400, 'invalid', out['error'])
        return _json({'token': out['token'], 'me': out['session'].me()})

    @_r('/me')
    def me(self, **kw):
        s = _session()
        if not s:
            return _fail(401, 'unauthenticated', 'Sign in with your code.')
        return _json(s.me())

    @_r('/home')
    def home(self, **kw):
        s = _session()
        if not s:
            return _fail(401, 'unauthenticated', 'Sign in with your code.')
        env = request.env(su=True)
        rate = None
        try:
            r = env['jewellery.gold.rate'].get_current(env.company)
            rate = {'rate_per_gram': r.rate_per_gram, 'currency': r.currency_id.name, 'approved_at': r.approved_at or r.effective_at}
        except UserError:
            rate = None
        owned = s.owned_pieces()
        return _json({'me': s.me(), 'rate': rate, 'owned': owned,
                      'metal_value_today': round(sum(p['metal_value_today'] or 0 for p in owned), 2) if rate else None,
                      'fine_g': round(sum(p['fine_g'] for p in owned), 3),
                      'trays': s.trays(), 'requests': s.requests()})

    @_r('/trays/<int:tray_id>')
    def tray(self, tray_id, **kw):
        s = _session()
        if not s:
            return _fail(401, 'unauthenticated', 'Sign in with your code.')
        tray = request.env(su=True)['jewellery.tray'].browse(tray_id).exists()
        if not tray or tray.partner_id != s.partner_id:
            return _fail(404, 'not_found', 'No such selection.')
        return _json(tray._public_payload())

    @_r('/pieces/<string:serial>/image')
    def piece_image(self, serial, **kw):
        s = _session()
        if not s:
            return request.not_found()
        serials = {p['serial'] for p in s.owned_pieces()}
        if serial not in serials:
            return request.not_found()
        lot = request.env(su=True)['stock.lot'].search([('name', '=', serial)], limit=1)
        if not lot or not lot.product_id.image_1024:
            return request.not_found()
        data = base64.b64decode(lot.product_id.image_1024)
        return request.make_response(data, headers=[('Content-Type', 'image/png' if data[:4] == b'\x89PNG' else 'image/jpeg'),
                                                    ('Cache-Control', 'private, max-age=3600')])

    @_r('/consent', methods=['POST'])
    def consent(self, **kw):
        s = _session()
        if not s:
            return _fail(401, 'unauthenticated', 'Sign in with your code.')
        status = _body().get('status')
        if status not in ('given', 'withdrawn'):
            return _fail(400, 'validation', 'status is given or withdrawn.')
        try:
            s.partner_id.sudo().action_record_consent(status, source='client_message', note='From the client app')
        except UserError as e:
            return _fail(400, 'invalid', str(e.args[0]))
        return _json(s.me())

    @_r('/signout', methods=['POST'])
    def signout(self, **kw):
        s = _session()
        if s:
            s.action_revoke()
        return _json({'ok': True})
