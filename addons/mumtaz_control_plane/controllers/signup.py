from werkzeug.exceptions import NotFound

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request


class MumtazSignupController(http.Controller):
    """The public door for "register my organization".

    Closed by default: it answers only when the system parameter
    ``mumtaz_control_plane.public_signup`` is ``1``. It records a request for
    a person to review. It cannot create a tenant, a subscription or a
    database, whatever is posted to it.
    """

    @http.route("/mumtaz/cp/signup", type="jsonrpc", auth="public",
                methods=["POST"], csrf=False)
    def signup(self, **payload):
        # A website visitor has no rights on the model. The method validates
        # the input and can only create a pending request.
        # sudo: public intake; visitors hold no access rights and only a pending request is created
        Request = request.env["mumtaz.signup.request"].sudo()
        if not Request._public_signup_enabled():
            raise NotFound()
        try:
            Request._register_public(payload)
        except (UserError, ValidationError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True}
