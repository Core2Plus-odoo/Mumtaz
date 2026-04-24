"""REST API endpoints for Mumtaz E-Invoicing.

Provides JSON HTTP endpoints for:
- Submitting an invoice to the tax authority.
- Querying e-invoice status.
- Retrieving the QR code string.
- Cancelling a submitted e-invoice.

All endpoints require an authenticated Odoo session (auth='user').
For machine-to-machine access, use Odoo's API key authentication.
"""
import json
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


def _json_response(data: dict, status: int = 200) -> Response:
    """Helper to build a JSON HTTP response."""
    return Response(
        json.dumps(data, default=str),
        content_type='application/json',
        status=status,
    )


class EInvoiceAPIController(http.Controller):
    """HTTP controller exposing e-invoicing REST endpoints."""

    # -------------------------------------------------------------------------
    # Submit
    # -------------------------------------------------------------------------
    @http.route(
        '/api/v1/einvoice/submit/<int:move_id>',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def submit_einvoice(self, move_id, **kwargs):
        """Submit an invoice to the relevant tax authority.

        POST /api/v1/einvoice/submit/<move_id>

        Response 200:
            {
                "success": true,
                "einvoice_status": "accepted",
                "einvoice_number": "ZATCA-INV/2024/0001",
                "qr_code": "<base64 TLV>"
            }

        Response 404:  Invoice not found.
        Response 422:  Validation error (invoice not posted, wrong country, etc.).
        Response 500:  Unexpected server error.
        """
        invoice = request.env['account.move'].browse(move_id)
        if not invoice.exists():
            return _json_response({'error': 'Invoice not found.'}, status=404)

        # Access check
        try:
            invoice.check_access_rights('write')
            invoice.check_access_rule('write')
        except Exception:
            return _json_response({'error': 'Access denied.'}, status=403)

        try:
            invoice.action_submit_einvoice()
        except Exception as exc:
            _logger.warning('E-invoice submit failed for move %d: %s', move_id, exc)
            return _json_response({'error': str(exc)}, status=422)

        return _json_response({
            'success': True,
            'einvoice_status': invoice.einvoice_status,
            'einvoice_number': invoice.einvoice_number,
            'qr_code': invoice.einvoice_qr_code or None,
        })

    # -------------------------------------------------------------------------
    # Status
    # -------------------------------------------------------------------------
    @http.route(
        '/api/v1/einvoice/status/<int:move_id>',
        type='http',
        auth='user',
        methods=['GET'],
        csrf=False,
    )
    def get_einvoice_status(self, move_id, **kwargs):
        """Return the current e-invoice status of an invoice.

        GET /api/v1/einvoice/status/<move_id>

        Response 200:
            {
                "move_id": 42,
                "name": "INV/2024/0001",
                "einvoice_status": "accepted",
                "einvoice_number": "ZATCA-INV/2024/0001",
                "submission_date": "2024-01-15 09:30:00",
                "acceptance_date": "2024-01-15 09:30:05",
                "country_type": "ksa",
                "errors": null
            }
        """
        invoice = request.env['account.move'].browse(move_id)
        if not invoice.exists():
            return _json_response({'error': 'Invoice not found.'}, status=404)

        try:
            invoice.check_access_rights('read')
            invoice.check_access_rule('read')
        except Exception:
            return _json_response({'error': 'Access denied.'}, status=403)

        return _json_response({
            'move_id': invoice.id,
            'name': invoice.name,
            'einvoice_status': invoice.einvoice_status,
            'einvoice_number': invoice.einvoice_number or None,
            'einvoice_uuid': invoice.einvoice_uuid or None,
            'submission_date': str(invoice.einvoice_submission_date) if invoice.einvoice_submission_date else None,
            'acceptance_date': str(invoice.einvoice_acceptance_date) if invoice.einvoice_acceptance_date else None,
            'country_type': invoice.einvoice_country_type or None,
            'errors': invoice.einvoice_validation_errors or None,
        })

    # -------------------------------------------------------------------------
    # QR code
    # -------------------------------------------------------------------------
    @http.route(
        '/api/v1/einvoice/qr/<int:move_id>',
        type='http',
        auth='user',
        methods=['GET'],
        csrf=False,
    )
    def get_qr(self, move_id, **kwargs):
        """Return the TLV-encoded QR code string for an invoice.

        GET /api/v1/einvoice/qr/<move_id>

        Response 200:
            {
                "move_id": 42,
                "qr_code": "<base64 TLV string>",
                "qr_image": "<base64 PNG/SVG>"
            }
        """
        invoice = request.env['account.move'].browse(move_id)
        if not invoice.exists():
            return _json_response({'error': 'Invoice not found.'}, status=404)

        try:
            invoice.check_access_rights('read')
            invoice.check_access_rule('read')
        except Exception:
            return _json_response({'error': 'Access denied.'}, status=403)

        if not invoice.einvoice_qr_code:
            return _json_response(
                {'error': 'QR code not available. Submit the invoice first.'},
                status=404,
            )

        return _json_response({
            'move_id': invoice.id,
            'qr_code': invoice.einvoice_qr_code,
            'qr_image': invoice.einvoice_qr_image.decode('utf-8') if invoice.einvoice_qr_image else None,
        })

    # -------------------------------------------------------------------------
    # Cancel
    # -------------------------------------------------------------------------
    @http.route(
        '/api/v1/einvoice/cancel/<int:move_id>',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def cancel_einvoice(self, move_id, **kwargs):
        """Cancel a previously submitted e-invoice.

        POST /api/v1/einvoice/cancel/<move_id>

        Response 200:
            {
                "success": true,
                "einvoice_status": "cancelled"
            }
        """
        invoice = request.env['account.move'].browse(move_id)
        if not invoice.exists():
            return _json_response({'error': 'Invoice not found.'}, status=404)

        try:
            invoice.check_access_rights('write')
            invoice.check_access_rule('write')
        except Exception:
            return _json_response({'error': 'Access denied.'}, status=403)

        try:
            invoice.action_cancel_einvoice()
        except Exception as exc:
            _logger.warning('E-invoice cancel failed for move %d: %s', move_id, exc)
            return _json_response({'error': str(exc)}, status=422)

        return _json_response({
            'success': True,
            'einvoice_status': invoice.einvoice_status,
        })

    # -------------------------------------------------------------------------
    # Bulk status (list endpoint)
    # -------------------------------------------------------------------------
    @http.route(
        '/api/v1/einvoice/bulk_status',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def bulk_status(self, **kwargs):
        """Return e-invoice status for a list of invoice IDs.

        POST /api/v1/einvoice/bulk_status
        Body (JSON): {"move_ids": [1, 2, 3]}

        Response 200:
            {
                "results": [
                    {"move_id": 1, "einvoice_status": "accepted", ...},
                    ...
                ]
            }
        """
        try:
            body = request.httprequest.get_data(as_text=True)
            data = json.loads(body)
            move_ids = data.get('move_ids', [])
            if not isinstance(move_ids, list) or not move_ids:
                return _json_response({'error': 'move_ids must be a non-empty list.'}, status=400)
        except (json.JSONDecodeError, AttributeError) as exc:
            return _json_response({'error': f'Invalid JSON body: {exc}'}, status=400)

        invoices = request.env['account.move'].browse(move_ids).exists()

        results = []
        for inv in invoices:
            try:
                inv.check_access_rule('read')
                results.append({
                    'move_id': inv.id,
                    'name': inv.name,
                    'einvoice_status': inv.einvoice_status,
                    'einvoice_number': inv.einvoice_number or None,
                    'submission_date': str(inv.einvoice_submission_date) if inv.einvoice_submission_date else None,
                    'country_type': inv.einvoice_country_type or None,
                })
            except Exception:
                # Skip records the user cannot access
                pass

        return _json_response({'results': results})
