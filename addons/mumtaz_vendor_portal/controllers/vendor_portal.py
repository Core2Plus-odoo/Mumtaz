from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class VendorPortalController(CustomerPortal):

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
