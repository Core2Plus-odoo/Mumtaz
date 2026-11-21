"""The public website's door: one POST, no session, no internal ids.

Kept apart from /jawhar/public/kiosk so nginx can open exactly this prefix
to the internet while the rest of /jawhar stays behind the demo password.
"""
import json
import logging

from odoo.exceptions import UserError
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)
PREFIX = '/jawhar/public/site'


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


class PublicSite(Controller):

    @route(PREFIX + '/demo-request', type='http', auth='public', methods=['POST'], csrf=False)
    def demo_request(self, **kw):
        body = _body()
        if body is None:
            return _fail(400, 'bad_json', 'Send a JSON object.')
        if (body.get('website') or '').strip():
            # honeypot: a field no person sees; a bot that fills it is told "thank you" and nothing is written
            return _json({'reference': 'received'})
        try:
            out = request.env['jewellery.demo.request'].create_public(
                body.get('company'), body.get('name'), body.get('email'), bool(body.get('consent')),
                phone=body.get('phone'), role=body.get('role'), country=body.get('country') or 'ae',
                stores=body.get('stores') or '1', message=body.get('message'), lang=body.get('lang') or 'en',
                source_page=body.get('page'))
        except UserError as e:
            status = 429 if 'already have' in str(e) else 400
            return _fail(status, 'rejected', str(e))
        _logger.info('jawhar site: demo request %s from %s', out['reference'], request.httprequest.remote_addr)
        return _json(out)
