"""Mumtaz SSO bridge.

The control panel (app.mumtaz.digital) mints a short-lived token:

    payload = base64url(json{"db","login","exp"})   # padding stripped
    token   = payload + "." + hex(hmac_sha256(secret, payload))

and links the user to /mumtaz/sso?token=...  This controller verifies the
token against the per-DB shared secret (ir.config_parameter
'mumtaz.sso_secret'), then establishes a password-less Odoo session for the
matching user. The secret is planted in each tenant DB at provision time and
must equal ODOO_SSO_SECRET in the control panel's environment.
"""
import base64
import hashlib
import hmac
import json
import logging
import time

from odoo import SUPERUSER_ID, api, http
from odoo.http import request
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)

LOGIN_URL = "/web/login"


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class MumtazSSO(http.Controller):
    @http.route("/mumtaz/sso", type="http", auth="none", csrf=False,
                sitemap=False, save_session=True)
    def sso(self, token=None, **kw):
        if not token or "." not in token:
            return request.redirect(LOGIN_URL)
        payload_b64, _, sig = token.partition(".")
        try:
            data = json.loads(_b64url_decode(payload_b64))
        except Exception:
            return request.redirect(LOGIN_URL)
        db = data.get("db")
        login = data.get("login")
        if not db or not login:
            return request.redirect(LOGIN_URL)
        try:
            if float(data.get("exp", 0)) < time.time():
                return request.redirect(LOGIN_URL)
        except (TypeError, ValueError):
            return request.redirect(LOGIN_URL)

        # Bind explicitly to the target DB — host-based dbfilter is ambiguous
        # once multiple tenant databases match. Use the low-level Registry
        # (the odoo.registry() helper is blocked when list_db=False).
        try:
            registry = Registry(db)
        except Exception:
            _logger.warning("Mumtaz SSO: unknown database %s", db, exc_info=True)
            return request.redirect(LOGIN_URL)

        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            secret = env["ir.config_parameter"].sudo().get_param("mumtaz.sso_secret") or ""
            if not secret:
                _logger.warning("Mumtaz SSO: no mumtaz.sso_secret set in %s", db)
                return request.redirect(LOGIN_URL)
            expected = hmac.new(secret.encode(), payload_b64.encode(),
                                hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, sig or ""):
                _logger.warning("Mumtaz SSO: bad signature (login=%s db=%s)", login, db)
                return request.redirect(LOGIN_URL)
            user = env["res.users"].search(
                [("login", "=", login), ("active", "=", True)], limit=1)
            if not user:
                _logger.warning("Mumtaz SSO: no active user %s in %s", login, db)
                return request.redirect(LOGIN_URL)
            uid = user.id
            session_token = user._compute_session_token(request.session.sid)

        # Establish the authenticated session and hand off to the web client.
        request.session.db = db
        request.session.uid = uid
        request.session.login = login
        request.session.session_token = session_token
        try:
            request.update_env(user=uid)
        except Exception:
            pass
        _logger.info("Mumtaz SSO: authenticated %s in %s", login, db)
        return request.redirect("/odoo")
