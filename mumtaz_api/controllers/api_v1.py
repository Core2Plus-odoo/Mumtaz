import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

# Origins allowed to call the public API (static website)
_ALLOWED_ORIGINS = [
    "https://mumtaz.digital",
    "https://www.mumtaz.digital",
    "http://localhost",
    "http://127.0.0.1",
]

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Requested-With",
    "Access-Control-Max-Age": "86400",
}


def _cors_response(data, status=200):
    """Return a JSON response with CORS headers."""
    resp = request.make_response(
        http.serialize_exception(data) if isinstance(data, Exception) else
        __import__('json').dumps(data),
        headers={**_CORS_HEADERS, "Content-Type": "application/json"},
    )
    resp.status_code = status
    return resp


def _build_crm_lead(vals: dict, lead_type: str) -> dict:
    """Map raw form values to crm.lead fields."""
    name = f"{vals.get('first_name', '')} {vals.get('last_name', '')}".strip() or vals.get('name', 'Unknown')
    company = vals.get('company', '') or vals.get('company_name', '')
    email = vals.get('email', '')
    role = vals.get('role', '') or vals.get('topic', '')
    notes = vals.get('message', '') or vals.get('notes', '')

    description_lines = [f"Source: Website / {lead_type}"]
    if role:
        description_lines.append(f"Role/Topic: {role}")
    if notes:
        description_lines.append(f"\nMessage:\n{notes}")

    return {
        'name': f"[Web] {name}" + (f" – {company}" if company else ""),
        'contact_name': name,
        'partner_name': company,
        'email_from': email,
        'description': "\n".join(description_lines),
        'type': 'lead',
        'tag_ids': [],
        'source_id': request.env['utm.source'].sudo().search([('name', '=', 'Website')], limit=1).id or False,
    }


class MumtazApiV1(http.Controller):

    # ── Preflight OPTIONS handler ──────────────────────────────────────
    @http.route([
        '/api/mumtaz/v1/demo',
        '/api/mumtaz/v1/contact',
        '/api/mumtaz/v1/health',
    ], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def api_preflight(self, **kw):
        resp = Response(status=204)
        for k, v in _CORS_HEADERS.items():
            resp.headers[k] = v
        return resp

    # ── Health check ───────────────────────────────────────────────────
    @http.route('/api/mumtaz/v1/health', type='http', auth='public', methods=['GET'], csrf=False)
    def api_health(self, **kw):
        return _cors_response({'status': 'ok', 'platform': 'Mumtaz', 'version': '1.0'})

    # ── Demo request ───────────────────────────────────────────────────
    @http.route('/api/mumtaz/v1/demo', type='http', auth='public', methods=['POST'], csrf=False)
    def api_demo_request(self, **kw):
        """Receive demo booking form data from mumtaz.digital and create a CRM lead."""
        try:
            vals = _build_crm_lead(kw, 'Demo Request')

            # Tag the lead as a demo request
            tag = request.env['crm.tag'].sudo().search([('name', 'ilike', 'Demo')], limit=1)
            if not tag:
                tag = request.env['crm.tag'].sudo().create({'name': 'Demo Request'})
            vals['tag_ids'] = [(4, tag.id)]

            # Set priority based on role
            role = kw.get('role', '')
            if role in ('bank', 'fintech', 'ecosystem'):
                vals['priority'] = '2'   # high — partner lead
                vals['description'] += '\n\n[PARTNER LEAD — high priority]'
            else:
                vals['priority'] = '1'   # normal

            lead = request.env['crm.lead'].sudo().create(vals)
            _logger.info("Demo request lead created: %s (id=%s)", lead.name, lead.id)

            # Enroll in nurture campaign if available
            try:
                campaign = request.env['lead.nurture.campaign'].sudo().search(
                    [('active', '=', True)], limit=1
                )
                if campaign and hasattr(lead, 'nurture_campaign_id'):
                    lead.sudo().write({
                        'nurture_campaign_id': campaign.id,
                        'nurture_stage': 'enrolled',
                    })
            except Exception:
                pass  # nurture module may not be installed

            return _cors_response({'success': True, 'lead_id': lead.id, 'message': 'Demo request received.'})
        except Exception as exc:
            _logger.exception("Demo API error: %s", exc)
            return _cors_response({'success': False, 'error': str(exc)}, status=500)

    # ── Contact form ───────────────────────────────────────────────────
    @http.route('/api/mumtaz/v1/contact', type='http', auth='public', methods=['POST'], csrf=False)
    def api_contact(self, **kw):
        """Receive contact form data and create a CRM lead."""
        try:
            vals = _build_crm_lead(kw, 'Contact Form')
            vals['priority'] = '0'

            tag = request.env['crm.tag'].sudo().search([('name', 'ilike', 'Website Contact')], limit=1)
            if not tag:
                tag = request.env['crm.tag'].sudo().create({'name': 'Website Contact'})
            vals['tag_ids'] = [(4, tag.id)]

            lead = request.env['crm.lead'].sudo().create(vals)
            _logger.info("Contact lead created: %s (id=%s)", lead.name, lead.id)
            return _cors_response({'success': True, 'lead_id': lead.id, 'message': 'Message received.'})
        except Exception as exc:
            _logger.exception("Contact API error: %s", exc)
            return _cors_response({'success': False, 'error': str(exc)}, status=500)
