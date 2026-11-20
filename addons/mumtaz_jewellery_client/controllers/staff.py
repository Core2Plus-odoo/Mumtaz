"""Staff side: the live sign-in code on the client's record, so a person
can give it to her. The server never sends it."""
from odoo.http import Controller, request

from odoo.addons.mumtaz_jewellery_api.controllers.api import _get, _r, endpoint


class JawharClientStaffApi(Controller):

    @_r('/clients/<int:client_id>/app')
    @endpoint()
    def client_app(self, client_id, **kw):
        p = _get('res.partner', client_id)
        Session = request.env['jewellery.client.session']
        open_sessions = Session.sudo().search_count([('partner_id', '=', p.id), ('token_digest', '!=', False), ('revoked', '=', False)])
        return {'codes': Session.pending_codes(p), 'open_sessions': open_sessions, 'phone': p.phone or None}
