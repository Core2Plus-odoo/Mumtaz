"""The client's side of a Private Tray: a phone, a link, no account.

Everything here runs for the public user and is scoped by the token alone:
the tray behind a live link and nothing else. The payload carries no client
data and no internal ids; a line is addressed by its public ref.
"""
import json
import logging

from odoo.exceptions import UserError
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)
PREFIX = '/jawhar/public/tray'


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


class PublicTray(Controller):

    def _tray(self, token):
        tray = request.env['jewellery.tray']._find_by_token(token)
        return tray

    @route(PREFIX + '/<string:token>', type='http', auth='public', methods=['GET'], csrf=False)
    def tray(self, token, **kw):
        tray = self._tray(token)
        if not tray:
            return _fail(404, 'not_found', 'This selection is no longer available. Ask your advisor for a new link.')
        return _json(tray._public_payload())

    @route(PREFIX + '/<string:token>/feedback', type='http', auth='public', methods=['POST'], csrf=False)
    def feedback(self, token, **kw):
        tray = self._tray(token)
        if not tray:
            return _fail(404, 'not_found', 'This selection is no longer available.')
        body = _body()
        if body is None:
            return _fail(400, 'bad_json', 'The body must be a JSON object.')
        try:
            tray._public_feedback(body.get('ref'), body.get('kind'), body.get('question'))
        except UserError as e:
            return _fail(400, 'invalid', str(e.args[0]) if e.args else 'Invalid.')
        return _json(tray._public_payload())

    @route(PREFIX + '/<string:token>/viewing', type='http', auth='public', methods=['POST'], csrf=False)
    def viewing(self, token, **kw):
        tray = self._tray(token)
        if not tray:
            return _fail(404, 'not_found', 'This selection is no longer available.')
        body = _body()
        if body is None:
            return _fail(400, 'bad_json', 'The body must be a JSON object.')
        try:
            tray._public_request_viewing(body.get('preferred'), body.get('note'))
        except UserError as e:
            return _fail(400, 'invalid', str(e.args[0]) if e.args else 'Invalid.')
        return _json(tray._public_payload())
