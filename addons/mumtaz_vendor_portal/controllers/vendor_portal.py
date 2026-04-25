import logging

from odoo import http, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

_logger = logging.getLogger(__name__)


class VendorPortalController(CustomerPortal):

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_vendor_po(self, order_id):
        """Browse a PO and verify it belongs to the current portal user.

        Raises AccessError or MissingError consistent with Odoo portal patterns.
        """
        partner = request.env.user.partner_id.commercial_partner_id
        order = request.env["purchase.order"].sudo().browse(int(order_id)).exists()
        if not order:
            raise MissingError(_("This purchase order doesn't exist."))
        if order.partner_id.commercial_partner_id.id != partner.id:
            raise AccessError(_("You don't have access to this purchase order."))
        return order


    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        if 'vendor_po_count' in counters:
            values['vendor_po_count'] = request.env['purchase.order'].search_count([
                ('partner_id', 'child_of', partner.commercial_partner_id.id),
                ('state', 'in', ['purchase', 'done']),
            ])
        if 'vendor_rfq_count' in counters:
            values['vendor_rfq_count'] = request.env['purchase.order'].search_count([
                ('partner_id', 'child_of', partner.commercial_partner_id.id),
                ('state', 'in', ['draft', 'sent']),
            ])
        return values

    @http.route('/vendor', type='http', auth='user', website=True)
    def vendor_dashboard(self, **kwargs):
        partner = request.env.user.partner_id.commercial_partner_id

        po_domain = [
            ('partner_id', 'child_of', partner.id),
            ('state', 'in', ['purchase', 'done']),
        ]
        rfq_domain = [
            ('partner_id', 'child_of', partner.id),
            ('state', 'in', ['draft', 'sent']),
        ]
        bill_domain = [
            ('partner_id', 'child_of', partner.id),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
        ]

        pending_bills = request.env['account.move'].search(
            bill_domain + [('payment_state', '!=', 'paid')]
        )
        pending_amount = sum(pending_bills.mapped('amount_residual'))

        values = {
            'partner': partner,
            'po_count': request.env['purchase.order'].search_count(po_domain),
            'rfq_count': request.env['purchase.order'].search_count(rfq_domain),
            'bill_count': request.env['account.move'].search_count(bill_domain),
            'pending_amount': pending_amount,
            'recent_pos': request.env['purchase.order'].search(
                po_domain, limit=5, order='date_order desc'
            ),
            'recent_rfqs': request.env['purchase.order'].search(
                rfq_domain, limit=5, order='date_order desc'
            ),
        }
        return request.render('mumtaz_vendor_portal.portal_vendor_dashboard', values)

    @http.route('/vendor/purchase-orders', type='http', auth='user', website=True)
    def vendor_purchase_orders(self, page=1, **kwargs):
        partner = request.env.user.partner_id.commercial_partner_id
        domain = [
            ('partner_id', 'child_of', partner.id),
            ('state', 'in', ['purchase', 'done']),
        ]
        total = request.env['purchase.order'].search_count(domain)
        pager = portal_pager(
            url='/vendor/purchase-orders',
            total=total,
            page=page,
            step=10,
        )
        orders = request.env['purchase.order'].search(
            domain, limit=10, offset=pager['offset'], order='date_order desc'
        )
        return request.render(
            'mumtaz_vendor_portal.portal_vendor_po',
            {'orders': orders, 'pager': pager},
        )

    @http.route('/vendor/purchase-orders/<int:order_id>',
                type='http', auth='user', website=True)
    def vendor_purchase_order_detail(self, order_id, **kwargs):
        try:
            order = self._get_vendor_po(order_id)
        except (AccessError, MissingError) as exc:
            return request.render(
                'http_routing.404',
                {'message': str(exc)},
                status=404,
            )
        return request.render(
            'mumtaz_vendor_portal.portal_vendor_po_detail',
            {'order': order},
        )

    @http.route('/vendor/purchase-orders/<int:order_id>/acknowledge',
                type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def vendor_acknowledge_po(self, order_id, **kwargs):
        """Vendor confirms receipt of the PO. Posts a chatter message."""
        try:
            order = self._get_vendor_po(order_id)
        except (AccessError, MissingError):
            return request.redirect('/vendor/purchase-orders')

        # Idempotent: only post once per vendor user
        already = request.env['mail.message'].sudo().search_count([
            ('model',     '=', 'purchase.order'),
            ('res_id',    '=', order.id),
            ('author_id', '=', request.env.user.partner_id.id),
            ('subtype_id.internal', '=', False),
            ('body',      'ilike', 'acknowledged'),
        ])
        if not already:
            order.sudo().message_post(
                body=_(
                    "Vendor %s acknowledged this purchase order via the vendor portal.",
                    request.env.user.name,
                ),
                author_id=request.env.user.partner_id.id,
                message_type='comment',
            )
        return request.redirect(f'/vendor/purchase-orders/{order_id}')

    def _get_vendor_rfq(self, rfq_id):
        """Browse an open RFQ and verify it belongs to the current portal user."""
        partner = request.env.user.partner_id.commercial_partner_id
        rfq = request.env["purchase.order"].sudo().browse(int(rfq_id)).exists()
        if not rfq:
            raise MissingError(_("This RFQ doesn't exist."))
        if rfq.partner_id.commercial_partner_id.id != partner.id:
            raise AccessError(_("You don't have access to this RFQ."))
        if rfq.state not in ('draft', 'sent'):
            raise AccessError(_("This RFQ is no longer open for quotes."))
        return rfq

    @http.route('/vendor/rfq', type='http', auth='user', website=True)
    def vendor_rfq(self, page=1, **kwargs):
        partner = request.env.user.partner_id.commercial_partner_id
        domain = [
            ('partner_id', 'child_of', partner.id),
            ('state', 'in', ['draft', 'sent']),
        ]
        total = request.env['purchase.order'].search_count(domain)
        pager = portal_pager(
            url='/vendor/rfq',
            total=total,
            page=page,
            step=10,
        )
        rfqs = request.env['purchase.order'].search(
            domain, limit=10, offset=pager['offset'], order='date_order desc'
        )
        return request.render(
            'mumtaz_vendor_portal.portal_vendor_rfq',
            {'rfqs': rfqs, 'pager': pager},
        )

    @http.route('/vendor/rfq/<int:rfq_id>',
                type='http', auth='user', website=True)
    def vendor_rfq_detail(self, rfq_id, error=None, success=None, **kwargs):
        try:
            rfq = self._get_vendor_rfq(rfq_id)
        except (AccessError, MissingError) as exc:
            return request.render(
                'http_routing.404',
                {'message': str(exc)},
                status=404,
            )
        return request.render(
            'mumtaz_vendor_portal.portal_vendor_rfq_detail',
            {'rfq': rfq, 'error': error, 'success': success},
        )

    @http.route('/vendor/rfq/<int:rfq_id>/respond',
                type='http', auth='user', methods=['POST'],
                website=True, csrf=True)
    def vendor_rfq_respond(self, rfq_id, **post):
        try:
            rfq = self._get_vendor_rfq(rfq_id)
        except (AccessError, MissingError):
            return request.redirect('/vendor/rfq')

        notes         = (post.get('notes') or '').strip()
        valid_until   = (post.get('valid_until') or '').strip()
        delivery_days = (post.get('delivery_days') or '').strip()

        # Collect per-line quoted prices keyed by line id
        updated_lines = []
        for line in rfq.order_line:
            raw = (post.get(f'price_{line.id}') or '').strip()
            if raw:
                try:
                    quoted = float(raw)
                except ValueError:
                    return request.redirect(
                        f'/vendor/rfq/{rfq_id}?error=Invalid+price+on+line+"{line.name[:40]}"'
                    )
                if quoted < 0:
                    return request.redirect(
                        f'/vendor/rfq/{rfq_id}?error=Prices+cannot+be+negative.'
                    )
                updated_lines.append((line, quoted))

        if not updated_lines and not notes:
            return request.redirect(
                f'/vendor/rfq/{rfq_id}?error=Please+provide+at+least+one+quoted+price+or+a+note.'
            )

        # Build rich HTML chatter body
        rows = ['<p><strong>Vendor quote submitted by '
                f'{request.env.user.name}</strong></p>']
        if updated_lines:
            rows.append(
                '<table style="border-collapse:collapse;font-size:13px;">'
                '<tr>'
                '<th style="border:1px solid #cbd5e1;padding:5px 10px;text-align:left;">Product</th>'
                '<th style="border:1px solid #cbd5e1;padding:5px 10px;text-align:right;">Qty</th>'
                '<th style="border:1px solid #cbd5e1;padding:5px 10px;text-align:right;">Quoted Unit Price</th>'
                '</tr>'
            )
            for line, price in updated_lines:
                rows.append(
                    f'<tr>'
                    f'<td style="border:1px solid #e2e8f0;padding:5px 10px;">{line.name}</td>'
                    f'<td style="border:1px solid #e2e8f0;padding:5px 10px;text-align:right;">'
                    f'{line.product_qty:.2f} {line.product_uom.name}</td>'
                    f'<td style="border:1px solid #e2e8f0;padding:5px 10px;text-align:right;">'
                    f'{price:,.2f} {rfq.currency_id.name}</td>'
                    f'</tr>'
                )
            rows.append('</table>')
        if valid_until:
            rows.append(f'<p>Quote valid until: <strong>{valid_until}</strong></p>')
        if delivery_days:
            rows.append(f'<p>Estimated lead time: <strong>{delivery_days} day(s)</strong></p>')
        if notes:
            rows.append(f'<p>Notes: {notes}</p>')

        try:
            for line, price in updated_lines:
                line.sudo().write({'price_unit': price})
            rfq.sudo().message_post(
                body=''.join(rows),
                author_id=request.env.user.partner_id.id,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
            _logger.info(
                'Vendor portal: quote submitted on RFQ %s by user %s',
                rfq.name, request.env.user.id,
            )
        except Exception:
            _logger.exception('Vendor RFQ respond failed for RFQ %s', rfq_id)
            return request.redirect(
                f'/vendor/rfq/{rfq_id}?error=Failed+to+submit+quote.+Please+try+again.'
            )

        return request.redirect(
            f'/vendor/rfq/{rfq_id}?success=Your+quote+has+been+submitted+successfully.'
        )

    @http.route('/vendor/invoices', type='http', auth='user', website=True)
    def vendor_invoices(self, page=1, **kwargs):
        partner = request.env.user.partner_id.commercial_partner_id
        domain = [
            ('partner_id', 'child_of', partner.id),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
        ]
        total = request.env['account.move'].search_count(domain)
        pager = portal_pager(
            url='/vendor/invoices',
            total=total,
            page=page,
            step=10,
        )
        invoices = request.env['account.move'].search(
            domain, limit=10, offset=pager['offset'], order='invoice_date desc'
        )
        return request.render(
            'mumtaz_vendor_portal.portal_vendor_invoices',
            {'invoices': invoices, 'pager': pager},
        )

    # ── Invoice upload ──────────────────────────────────────────────────

    _MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
    _ALLOWED_EXT      = ('.pdf', '.xml', '.png', '.jpg', '.jpeg')

    @http.route('/vendor/invoices/upload',
                type='http', auth='user', website=True)
    def vendor_invoice_upload_form(self, error=None, success=None, **kwargs):
        partner = request.env.user.partner_id.commercial_partner_id
        # Confirmed POs without an invoice yet — the natural targets for upload
        po_domain = [
            ('partner_id', 'child_of', partner.id),
            ('state', 'in', ['purchase', 'done']),
            ('invoice_status', '!=', 'invoiced'),
        ]
        eligible_pos = request.env['purchase.order'].sudo().search(
            po_domain, limit=50, order='date_order desc',
        )
        return request.render(
            'mumtaz_vendor_portal.portal_vendor_invoice_upload',
            {
                'eligible_pos': eligible_pos,
                'error':        error,
                'success':      success,
            },
        )

    @http.route('/vendor/invoices/upload',
                type='http', auth='user', methods=['POST'],
                website=True, csrf=True)
    def vendor_invoice_upload_submit(self, **post):
        import base64

        partner = request.env.user.partner_id.commercial_partner_id

        po_id          = (post.get('po_id') or '').strip()
        invoice_ref    = (post.get('invoice_ref') or '').strip()
        invoice_date   = (post.get('invoice_date') or '').strip()
        amount         = (post.get('amount') or '').strip()
        attachment     = post.get('attachment')

        # ── Validate ─────────────────────────────────────────────────────
        if not po_id or not po_id.isdigit():
            return self.vendor_invoice_upload_form(error='Please select a purchase order.')
        if not invoice_ref:
            return self.vendor_invoice_upload_form(error='Invoice reference is required.')
        if not attachment or not attachment.filename:
            return self.vendor_invoice_upload_form(error='Please attach a PDF or XML invoice.')

        ext = '.' + (attachment.filename.rsplit('.', 1)[-1] or '').lower()
        if ext not in self._ALLOWED_EXT:
            return self.vendor_invoice_upload_form(
                error=f'Unsupported file type. Allowed: {", ".join(self._ALLOWED_EXT)}.'
            )

        file_bytes = attachment.read()
        if len(file_bytes) > self._MAX_UPLOAD_BYTES:
            return self.vendor_invoice_upload_form(
                error='File too large (max 10 MB).'
            )
        if not file_bytes:
            return self.vendor_invoice_upload_form(error='Empty file.')

        # ── Verify PO ownership ──────────────────────────────────────────
        try:
            po = self._get_vendor_po(int(po_id))
        except (AccessError, MissingError):
            return self.vendor_invoice_upload_form(
                error='Selected purchase order is not accessible.'
            )

        # Parse amount (optional — fall back to PO total if not provided)
        try:
            amount_val = float(amount) if amount else po.amount_total
        except ValueError:
            return self.vendor_invoice_upload_form(error='Invalid amount.')

        # ── Create draft vendor bill ─────────────────────────────────────
        try:
            bill = request.env['account.move'].sudo().create({
                'move_type':       'in_invoice',
                'partner_id':      partner.id,
                'invoice_date':    invoice_date or False,
                'ref':             invoice_ref,
                'company_id':      po.company_id.id,
                'currency_id':     po.currency_id.id,
                'invoice_origin':  po.name,
                'narration':       f'Uploaded by {request.env.user.name} via vendor portal.',
                'invoice_line_ids': [(0, 0, {
                    'name':       f'{po.name} — {invoice_ref}',
                    'quantity':   1.0,
                    'price_unit': amount_val,
                })],
            })

            # Attach the file
            request.env['ir.attachment'].sudo().create({
                'name':      attachment.filename,
                'datas':     base64.b64encode(file_bytes),
                'res_model': 'account.move',
                'res_id':    bill.id,
                'mimetype':  attachment.content_type or 'application/octet-stream',
            })

            bill.message_post(
                body=_(
                    'Vendor invoice <strong>%s</strong> uploaded by %s via the '
                    'vendor portal against PO <strong>%s</strong>.',
                    invoice_ref, request.env.user.name, po.name,
                ),
                author_id=request.env.user.partner_id.id,
                message_type='comment',
            )
            _logger.info(
                'Vendor portal: invoice %s uploaded for PO %s by user %s',
                invoice_ref, po.name, request.env.user.id,
            )
        except Exception as exc:
            _logger.exception('Vendor invoice upload failed')
            return self.vendor_invoice_upload_form(
                error=f'Failed to create draft bill: {exc}'
            )

        return self.vendor_invoice_upload_form(
            success=f'Invoice {invoice_ref} uploaded — your buyer has been notified.'
        )

    @http.route('/vendor/payments', type='http', auth='user', website=True)
    def vendor_payments(self, **kwargs):
        partner = request.env.user.partner_id.commercial_partner_id
        payments = request.env['account.payment'].search(
            [
                ('partner_id', 'child_of', partner.id),
                ('payment_type', '=', 'outbound'),
                ('state', '=', 'posted'),
            ],
            limit=20,
            order='date desc',
        )
        return request.render(
            'mumtaz_vendor_portal.portal_vendor_payments',
            {'payments': payments},
        )
