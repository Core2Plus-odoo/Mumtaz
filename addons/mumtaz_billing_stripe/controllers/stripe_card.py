import json
import logging

from odoo import http
from odoo.http import request, Response

from ..models.stripe_client import StripeError

_logger = logging.getLogger(__name__)

_ALLOWED_GROUPS = (
    "mumtaz_control_plane.group_mumtaz_billing_admin",
    "mumtaz_control_plane.group_mumtaz_super_admin",
)


def _user_allowed():
    return any(request.env.user.has_group(g) for g in _ALLOWED_GROUPS)


class MumtazStripeCard(http.Controller):

    @http.route("/mumtaz/stripe/card/<int:tenant_id>", type="http",
                auth="user", methods=["GET"], website=False)
    def card_page(self, tenant_id, **kwargs):
        if not _user_allowed():
            return Response("Forbidden", status=403)

        tenant = request.env["mumtaz.tenant"].browse(tenant_id)
        if not tenant.exists():
            return Response("Tenant not found", status=404)

        client = request.env["mumtaz.stripe.client"]
        settings = request.env["mumtaz.stripe.settings"].sudo().get_singleton()
        pk = settings.publishable_key or ""
        if not client._is_configured() or not pk:
            return request.make_response(self._render_error(
                "Stripe is not fully configured. Set STRIPE_SECRET_KEY in "
                "/opt/mumtaz/.env and a publishable key in Stripe Settings."
            ), headers=[("Content-Type", "text/html")])

        try:
            customer_id = tenant.sudo()._ensure_stripe_customer()
            intent = client.create_setup_intent(customer_id)
        except StripeError as exc:
            return request.make_response(
                self._render_error(exc.user_message),
                headers=[("Content-Type", "text/html")],
            )

        html = self._render_card_page(
            tenant=tenant, pk=pk,
            client_secret=intent.get("client_secret", ""),
        )
        return request.make_response(html, headers=[("Content-Type", "text/html")])

    @http.route("/mumtaz/stripe/card/confirm", type="http", auth="user",
                methods=["POST"], csrf=False)
    def card_confirm(self, tenant_id=None, setup_intent_id=None, **kwargs):
        if not _user_allowed():
            return Response(json.dumps({"error": "forbidden"}), status=403,
                            content_type="application/json")
        tenant = request.env["mumtaz.tenant"].browse(int(tenant_id or 0))
        if not tenant.exists() or not setup_intent_id:
            return Response(json.dumps({"error": "bad request"}), status=400,
                            content_type="application/json")
        client = request.env["mumtaz.stripe.client"].sudo()
        try:
            si = client._request("GET", f"setup_intents/{setup_intent_id}")
            pm_id = si.get("payment_method")
            if not pm_id:
                return Response(json.dumps({"error": "no payment method"}),
                                status=400, content_type="application/json")
            card = None
            try:
                pm = client._request("GET", f"payment_methods/{pm_id}")
                card = pm.get("card")
            except Exception:  # noqa: BLE001 - card detail is best-effort
                card = None
            tenant.sudo()._set_default_payment_method(pm_id, card=card)
        except StripeError as exc:
            _logger.warning("Card confirm failed for tenant %s: %s",
                            tenant_id, exc.detail)
            return Response(json.dumps({"error": exc.user_message}),
                            status=400, content_type="application/json")
        return Response(json.dumps({"success": True}),
                        content_type="application/json")

    # ── HTML rendering (self-contained, no asset bundle) ──────────────────
    def _render_error(self, message):
        from markupsafe import escape
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>Stripe Card Setup</title></head>
<body style="font-family:Arial,sans-serif;max-width:480px;margin:60px auto;padding:0 20px">
<h2>Card Setup Unavailable</h2>
<div style="background:#fdecea;border:1px solid #f5c6cb;color:#a33;padding:14px;border-radius:6px">
{escape(message)}</div>
</body></html>"""

    def _render_card_page(self, tenant, pk, client_secret):
        from markupsafe import escape
        return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Add Payment Method — {escape(tenant.name)}</title>
<script src="https://js.stripe.com/v3/"></script>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 480px; margin: 50px auto; padding: 0 20px; color:#333; }}
  h2 {{ margin-bottom: 4px; }}
  .sub {{ color:#888; font-size:13px; margin-bottom:24px; }}
  #card-element {{ border:1px solid #ccd; border-radius:6px; padding:12px; }}
  button {{ margin-top:18px; width:100%; padding:12px; border:0; border-radius:6px;
            background:#635bff; color:#fff; font-size:15px; cursor:pointer; }}
  button:disabled {{ opacity:.6; cursor:default; }}
  #msg {{ margin-top:14px; font-size:14px; }}
  .ok {{ color:#1a7f37; }} .err {{ color:#c00; }}
</style>
</head>
<body>
  <h2>Add Payment Method</h2>
  <div class="sub">{escape(tenant.name)} · charges run automatically once a card is saved.</div>
  <form id="card-form">
    <div id="card-element"></div>
    <button id="submit-btn" type="submit">Save Card</button>
    <div id="msg"></div>
  </form>
<script>
  var stripe = Stripe({json.dumps(pk)});
  var clientSecret = {json.dumps(client_secret)};
  var tenantId = {json.dumps(str(tenant.id))};
  var elements = stripe.elements();
  var card = elements.create('card');
  card.mount('#card-element');
  var form = document.getElementById('card-form');
  var btn = document.getElementById('submit-btn');
  var msg = document.getElementById('msg');
  form.addEventListener('submit', function(ev) {{
    ev.preventDefault();
    btn.disabled = true; msg.textContent = 'Saving…'; msg.className = '';
    stripe.confirmCardSetup(clientSecret, {{ payment_method: {{ card: card }} }})
      .then(function(result) {{
        if (result.error) {{
          msg.textContent = result.error.message; msg.className = 'err';
          btn.disabled = false; return;
        }}
        var si = result.setupIntent;
        var body = new URLSearchParams();
        body.append('tenant_id', tenantId);
        body.append('setup_intent_id', si.id);
        fetch('/mumtaz/stripe/card/confirm', {{ method:'POST', body: body }})
          .then(function(r) {{ return r.json(); }})
          .then(function(data) {{
            if (data.success) {{
              msg.textContent = '✓ Card saved successfully. You can close this tab.';
              msg.className = 'ok';
            }} else {{
              msg.textContent = data.error || 'Could not save card.'; msg.className = 'err';
              btn.disabled = false;
            }}
          }})
          .catch(function() {{
            msg.textContent = 'Network error saving card.'; msg.className = 'err';
            btn.disabled = false;
          }});
      }});
  }});
</script>
</body></html>"""
